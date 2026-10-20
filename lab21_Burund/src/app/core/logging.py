import logging
import time
import uuid

from fastapi import FastAPI, Request

log = logging.getLogger("restaurant")


def setup_logging(app: FastAPI, level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        log.info(
            "request_id=%s %s %s status=%s duration=%.0fms",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response
