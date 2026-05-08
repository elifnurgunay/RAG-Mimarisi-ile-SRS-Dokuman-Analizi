import random
import time
from typing import Callable, TypeVar

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RetryPolicy:
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 5.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def run(self, operation: Callable[[], T], operation_name: str = "operation") -> T:
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return operation()
            except Exception as exc:
                last_error = exc

                if not self._is_retryable(exc):
                    logger.error(
                        "Retry edilmeyen hata | operation=%s | hata=%s",
                        operation_name,
                        exc,
                    )
                    raise

                if attempt >= self.max_retries:
                    logger.error(
                        "Retry hakkı tükendi | operation=%s | attempt=%d | hata=%s",
                        operation_name,
                        attempt,
                        exc,
                    )
                    raise

                wait_time = self._calculate_wait_time(attempt)

                logger.warning(
                    "Retry bekleniyor | operation=%s | attempt=%d/%d | wait=%.1f sn | hata=%s",
                    operation_name,
                    attempt,
                    self.max_retries,
                    wait_time,
                    exc,
                )

                time.sleep(wait_time)

        raise last_error

    def _calculate_wait_time(self, attempt: int) -> float:
        wait_time = self.base_delay * (self.backoff_factor ** (attempt - 1))

        if self.jitter:
            wait_time += random.random()

        return wait_time

    def _is_retryable(self, exc: Exception) -> bool:
        message = str(exc).lower()

        retryable_signals = [
            "rate_limit",
            "rate limit",
            "429",
            "timeout",
            "temporarily unavailable",
            "connection",
            "server error",
            "503",
            "502",
            "504",
        ]

        return any(signal in message for signal in retryable_signals)