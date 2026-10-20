"""Retry и Circuit Breaker для межсервисных HTTP-вызовов."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum
from typing import TypeVar

import httpx

T = TypeVar("T")
log = logging.getLogger("resilience")


class ServiceUnavailable(Exception):
    """Сервис недоступен: повторы исчерпаны или Circuit Breaker разомкнут."""


class TransientHTTPError(Exception):
    """Ответ 5xx — временная ошибка, запрос можно повторить."""


RETRYABLE = (httpx.TransportError, httpx.TimeoutException, TransientHTTPError)


async def retry[T](
    call: Callable[[], Awaitable[T]],
    attempts: int = 3,
    delay: float = 0.2,
    backoff: float = 2.0,
    name: str = "request",
) -> T:
    """Повторяет вызов при временной ошибке с экспоненциальной задержкой."""
    current_delay = delay
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except RETRYABLE as error:
            if attempt == attempts:
                log.error(
                    "%s: попытка %s/%s неудачна, повторы исчерпаны: %s",
                    name,
                    attempt,
                    attempts,
                    error,
                )
                raise ServiceUnavailable(f"{name}: сервис недоступен ({error})") from error
            log.warning(
                "%s: попытка %s/%s неудачна (%s), повтор через %.1f с",
                name,
                attempt,
                attempts,
                error,
                current_delay,
            )
            await asyncio.sleep(current_delay)
            current_delay *= backoff
    raise AssertionError("unreachable")


class State(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 10.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.clock = clock
        self.failures = 0
        self.opened_at = 0.0
        self._state = State.CLOSED

    @property
    def state(self) -> State:
        if self._state == State.OPEN and self.clock() - self.opened_at >= self.recovery_timeout:
            self._state = State.HALF_OPEN
            log.info("CircuitBreaker[%s]: OPEN -> HALF_OPEN, пробный запрос", self.name)
        return self._state

    async def call(self, func: Callable[[], Awaitable[T]]) -> T:
        if self.state == State.OPEN:
            raise ServiceUnavailable(
                f"{self.name}: Circuit Breaker разомкнут (OPEN), запрос не отправлен"
            )
        try:
            result = await func()
        except ServiceUnavailable:
            self._on_failure()
            raise
        self._on_success()
        return result

    def _on_success(self) -> None:
        if self._state != State.CLOSED:
            log.info("CircuitBreaker[%s]: сервис восстановлен -> CLOSED", self.name)
        self.failures = 0
        self._state = State.CLOSED

    def _on_failure(self) -> None:
        self.failures += 1
        if self._state == State.HALF_OPEN or self.failures >= self.failure_threshold:
            self._state = State.OPEN
            self.opened_at = self.clock()
            log.error("CircuitBreaker[%s]: -> OPEN после %s ошибок", self.name, self.failures)
