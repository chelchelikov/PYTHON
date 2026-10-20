"""API Gateway — единая точка входа: маршрутизация, Retry, Circuit Breaker, health."""

import asyncio
import os

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.logging_setup import setup_logging
from app.resilience import CircuitBreaker, ServiceUnavailable, TransientHTTPError, retry

SERVICE_NAME = "gateway"
HOP_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}
# Сбоем самого сервиса считаются только сетевые ошибки и 502/504. Ответ 500/503 от живого
# сервиса (например, order-service, у которого недоступно меню) передаётся клиенту как есть,
# чтобы отказ одного сервиса не размыкал Circuit Breaker соседних (каскадный отказ).
GATEWAY_FAILURES = {502, 504}


class Backend:
    def __init__(self, name: str, url: str, prefix: str, breaker: CircuitBreaker) -> None:
        self.name = name
        self.url = url.rstrip("/")
        self.prefix = prefix
        self.breaker = breaker


def default_backends() -> dict[str, Backend]:
    timeout = float(os.getenv("CB_RECOVERY_TIMEOUT", "15"))
    config = {
        "menu": ("menu-service", os.getenv("MENU_SERVICE_URL", "http://localhost:8001"), "dishes"),
        "orders": (
            "order-service",
            os.getenv("ORDER_SERVICE_URL", "http://localhost:8002"),
            "orders",
        ),
        "deliveries": (
            "delivery-service",
            os.getenv("DELIVERY_SERVICE_URL", "http://localhost:8003"),
            "deliveries",
        ),
    }
    return {
        key: Backend(name, url, prefix, CircuitBreaker(name, recovery_timeout=timeout))
        for key, (name, url, prefix) in config.items()
    }


def create_app(
    backends: dict[str, Backend] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    retry_delay: float = 0.2,
) -> FastAPI:
    backends = backends or default_backends()
    app = FastAPI(
        title="Restaurant API Gateway", description="Шлюз к сервисам меню, заказов и доставки"
    )
    app.state.backends = backends
    log = setup_logging(app, SERVICE_NAME)

    async def send(
        backend: Backend,
        method: str,
        path: str,
        request_id: str,
        params=None,
        body: bytes | None = None,
        headers=None,
    ) -> httpx.Response:
        async def once() -> httpx.Response:
            async with httpx.AsyncClient(
                base_url=backend.url, timeout=3.0, transport=transport
            ) as client:
                response = await client.request(
                    method,
                    path,
                    params=params,
                    content=body,
                    headers={**(headers or {}), "X-Request-ID": request_id},
                )
            if response.status_code in GATEWAY_FAILURES:
                raise TransientHTTPError(f"HTTP {response.status_code}")
            return response

        # GET безопасно повторять; POST/PUT/DELETE — нет (можно создать заказ дважды)
        attempts = 3 if method == "GET" else 1

        async def guarded() -> httpx.Response:
            return await retry(once, attempts=attempts, delay=retry_delay, name=backend.name)

        return await backend.breaker.call(guarded)

    async def proxy(key: str, request: Request, rest: str = "") -> Response:
        backend = backends[key]
        path = f"/{backend.prefix}" + (f"/{rest}" if rest else "")
        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
        try:
            response = await send(
                backend,
                request.method,
                path,
                request.state.request_id,
                params=request.query_params,
                body=await request.body(),
                headers=headers,
            )
        except ServiceUnavailable as error:
            log.error("%s недоступен: %s", backend.name, error)
            return JSONResponse(
                {
                    "detail": str(error),
                    "service": backend.name,
                    "circuit": backend.breaker.state.value,
                },
                status_code=503,
            )
        return Response(
            content=response.content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
        )

    @app.get("/api/orders/{order_id}/full", tags=["composition"])
    async def order_with_delivery(order_id: int, request: Request):
        """Композиция: заказ из Order Service + доставка из Delivery Service."""
        rid = request.state.request_id
        try:
            order = await send(backends["orders"], "GET", f"/orders/{order_id}", rid)
        except ServiceUnavailable as error:
            return JSONResponse({"detail": str(error)}, status_code=503)
        if order.status_code != 200:
            return Response(order.content, order.status_code, media_type="application/json")
        result = {"order": order.json(), "delivery": None}
        try:
            delivery = await send(
                backends["deliveries"], "GET", f"/deliveries/by-order/{order_id}", rid
            )
            if delivery.status_code == 200:
                result["delivery"] = delivery.json()
        except ServiceUnavailable:
            result["delivery"] = "delivery-service недоступен"  # частичный ответ
        return result

    # Прокси-маршруты регистрируются последними, иначе {rest:path} перехватит /full
    for key, backend in backends.items():

        def make_routes(key: str, prefix: str, tag: str) -> None:
            methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]

            async def collection(request: Request):
                return await proxy(key, request)

            async def item(rest: str, request: Request):
                return await proxy(key, request, rest)

            app.add_api_route(
                f"/api/{prefix}", collection, methods=methods, name=f"{key}_collection", tags=[tag]
            )
            app.add_api_route(
                f"/api/{prefix}/{{rest:path}}",
                item,
                methods=methods,
                name=f"{key}_item",
                tags=[tag],
            )

        make_routes(key, backend.prefix, backend.name)

    @app.get("/health", tags=["health"])
    async def health(request: Request):
        async def check(backend: Backend) -> tuple[str, dict]:
            try:
                async with httpx.AsyncClient(
                    base_url=backend.url, timeout=2.0, transport=transport
                ) as client:
                    response = await client.get("/health")
                state = "healthy" if response.status_code == 200 else "unhealthy"
            except httpx.HTTPError:
                state = "unavailable"
            return backend.name, {"status": state, "circuit": backend.breaker.state.value}

        results = dict(await asyncio.gather(*(check(b) for b in backends.values())))
        overall = (
            "healthy" if all(r["status"] == "healthy" for r in results.values()) else "degraded"
        )
        return {"status": overall, "gateway": "healthy", "services": results}

    return app


app = create_app()
