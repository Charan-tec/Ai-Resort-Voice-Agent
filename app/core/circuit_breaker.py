import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional
from app.core.logging import logger


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while the circuit is open."""
    pass


class CircuitBreaker:
    """Production circuit breaker protecting external service calls."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 2,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: Optional[float] = None
        self._half_open_calls: int = 0
        self._lock = asyncio.Lock()

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        async with self._lock:
            now = time.monotonic()

            if self.state == CircuitState.OPEN:
                if self.last_failure_time and (now - self.last_failure_time) > self.recovery_timeout:
                    logger.warning(f"CircuitBreaker [{self.name}]: Transitioning from OPEN to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    raise CircuitBreakerOpenException(
                        f"CircuitBreaker [{self.name}] is OPEN. Requests blocked until timeout expires."
                    )

            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenException(
                        f"CircuitBreaker [{self.name}] is HALF_OPEN testing capacity reached."
                    )
                self._half_open_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._on_success()
            return result

        except Exception as exc:
            await self._on_failure(exc)
            raise exc

    async def _on_success(self):
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.half_open_max_calls:
                    logger.info(f"CircuitBreaker [{self.name}]: Service healthy. Transitioning to CLOSED.")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    async def _on_failure(self, exc: Exception):
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            logger.error(
                f"CircuitBreaker [{self.name}]: Recorded failure ({self.failure_count}/{self.failure_threshold}): {exc}"
            )

            if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
                if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                    logger.critical(f"CircuitBreaker [{self.name}]: Trip threshold reached! Transitioning to OPEN.")
                    self.state = CircuitState.OPEN
                    self.success_count = 0
