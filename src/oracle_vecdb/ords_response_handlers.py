"""Small response handlers shared by the ORDS service facade."""

from functools import wraps
from email.utils import parsedate_to_datetime
from datetime import timezone
import math
import secrets
import time
from types import MethodType
from typing import Any, Callable

from .vecdb_exception import VecDBException


class ORDSResponseHandler:
    """Callable wrapper for extensible ORDS response handling."""

    # Some read-only operations use POST because their request filters are
    # JSON bodies. Keep retry policy semantic and fail closed for new methods.
    _RETRY_SAFE_OPERATIONS = frozenset(
        {
            "describe_vector_database",
            "list_vector_tables",
            "describe_vector_table",
            "generate_embedding",
            "list_vectors",
            "list_vector_load_jobs",
            "describe_vector_load_job",
            "get_vector_load_job_log",
            "query",
            "rerank",
            "list_index_jobs",
            "describe_index_job",
            "get_index_job_log",
            "describe_index",
            "list_models",
            "describe_model",
        }
    )

    def __init__(self, function: Callable[..., Any]) -> None:
        self.function = function
        wraps(function)(self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.handle_errors(*args, **kwargs)

    def __get__(self, instance: Any, owner: Any) -> Any:
        if instance is None:
            return self
        return MethodType(self, instance)

    def handle_errors(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the public method and dispatch supported ORDS errors."""
        try:
            return self.function(*args, **kwargs)
        except VecDBException:
            # The handwritten ORDS adapter has already added operation and
            # argument context. Do not retry or wrap it a second time.
            raise
        except Exception as error:
            return self._handle_exception(error, *args, **kwargs)

    def _handle_exception(
        self, error: Exception, *args: Any, **kwargs: Any
    ) -> Any:
        if self._is_555(error):
            if not self._is_retry_safe_operation():
                raise error
            return self.handle_555(error, *args, **kwargs)
        if self._is_429(error):
            if not self._is_retry_safe_operation():
                raise error
            return self.handle_429(error, *args, **kwargs)
        raise error

    def _is_retry_safe_operation(self) -> bool:
        return self.function.__name__ in self._RETRY_SAFE_OPERATIONS

    def handle_555(self, error: Exception, *args: Any, **kwargs: Any) -> Any:
        """Retry transient ORDS 555/ORDS-25001 responses."""
        return self._retry(
            error,
            self._max_retries(args, "max_retry_count_error_555"),
            self._is_555,
            *args,
            **kwargs,
        )

    def handle_429(self, error: Exception, *args: Any, **kwargs: Any) -> Any:
        """Retry ORDS HTTP 429 responses in the public service facade."""
        return self._retry(
            error,
            self._max_retries(args, "max_retry_count_error_429"),
            self._is_429,
            *args,
            **kwargs,
        )

    def _retry(
        self,
        error: Exception,
        max_retries: int,
        retryable: Callable[[Exception], bool],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Retry one error type and redispatch a different subsequent error."""
        latest_error = error
        for retry_number in range(max_retries):
            self._sleep_before_retry(latest_error, retry_number, args)
            try:
                return self.function(*args, **kwargs)
            except VecDBException:
                # The exception is already normalized and must not be retried
                # or wrapped a second time.
                raise
            except Exception as next_error:
                if retryable(next_error):
                    latest_error = next_error
                    continue
                return self._handle_exception(next_error, *args, **kwargs)
        raise latest_error

    @classmethod
    def _sleep_before_retry(
        cls, error: Exception, retry_number: int, args: tuple[Any, ...]
    ) -> None:
        """Honor Retry-After and otherwise use bounded jittered backoff."""
        if not cls._is_429(error):
            return

        max_delay = cls._max_retry_delay(args)
        retry_after = cls._retry_after_seconds(error)
        if retry_after is None:
            upper_bound = min(max_delay, float(2**retry_number))
            retry_after = secrets.SystemRandom().uniform(0.0, upper_bound)
        else:
            # Retry-After is server-controlled input; cap it before reaching
            # the blocking sleep so a malformed or hostile response cannot
            # stall the caller indefinitely.
            retry_after = min(retry_after, max_delay)

        time.sleep(retry_after)

    @staticmethod
    def _retry_after_seconds(error: Exception) -> float | None:
        headers = getattr(error, "headers", None)
        if not headers:
            return None

        retry_after = None
        if hasattr(headers, "get"):
            retry_after = headers.get("Retry-After")
            if retry_after is None:
                retry_after = headers.get("retry-after")
        if retry_after is None:
            return None

        value = str(retry_after).strip()
        try:
            delay = float(value)
        except (TypeError, ValueError):
            delay = None
        if delay is not None and math.isfinite(delay) and delay >= 0:
            return delay

        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        delay = retry_at.timestamp() - time.time()
        return max(0.0, delay) if math.isfinite(delay) else None

    @staticmethod
    def _is_555(error: Exception) -> bool:
        return (
            getattr(error, "status", None) in (555, "555")
            or "ORDS-25001" in str(error).upper()
        )

    @staticmethod
    def _is_429(error: Exception) -> bool:
        return getattr(error, "status", None) in (429, "429")

    @staticmethod
    def _max_retries(args: tuple[Any, ...], setting_name: str) -> int:
        service = args[0] if args else None
        settings = getattr(
            getattr(service, "config", None), "ords_settings", None
        )
        return max(0, int(getattr(settings, setting_name, 3)))

    @staticmethod
    def _max_retry_delay(args: tuple[Any, ...]) -> float:
        service = args[0] if args else None
        settings = getattr(
            getattr(service, "config", None), "ords_settings", None
        )
        max_delay = getattr(settings, "max_retry_delay", 1.0)
        try:
            max_delay = float(max_delay)
        except (OverflowError, TypeError, ValueError):
            return 0.0
        return max(0.0, max_delay) if math.isfinite(max_delay) else 0.0
