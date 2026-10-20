"""Журнал: время, сервис, request id, метод, путь, статус, длительность."""

import logging
import time
import uuid

from fastapi import FastAPI, Request


def setup_logging(app: FastAPI, service_name: str) -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    log = logging.getLogger(service_name)

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request_id=%s %s %s error", request_id, request.method, request.url.path)
            raise
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

    return log
