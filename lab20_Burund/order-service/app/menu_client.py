"""HTTP-клиент Menu Service с Retry и Circuit Breaker."""

import httpx

from app.resilience import CircuitBreaker, TransientHTTPError, retry


class MenuClient:
    def __init__(
        self,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 2.0,
        attempts: int = 3,
        delay: float = 0.2,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.transport = transport
        self.timeout = timeout
        self.attempts = attempts
        self.delay = delay
        self.breaker = breaker or CircuitBreaker("menu-service")

    async def _get(self, path: str, params: dict, request_id: str | None):
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout, transport=self.transport
        ) as client:
            response = await client.get(
                path, params=params, headers={"X-Request-ID": request_id or ""}
            )
        if response.status_code >= 500:
            raise TransientHTTPError(f"HTTP {response.status_code}")
        response.raise_for_status()
        return response.json()

    async def get_dishes(self, dish_ids: list[int], request_id: str | None = None) -> list[dict]:
        params = {"ids": ",".join(map(str, dish_ids))}

        async def attempt():
            return await retry(
                lambda: self._get("/dishes", params, request_id),
                attempts=self.attempts,
                delay=self.delay,
                name="menu-service",
            )

        return await self.breaker.call(attempt)
