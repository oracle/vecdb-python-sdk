"""Small response handlers shared by the ORDS service facade."""

from functools import wraps
from types import MethodType
from typing import Any, Callable

from .vecdb_exception import VecDBException


class ORDSResponseHandler:
    """Callable wrapper for extensible ORDS response handling."""

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
            return self.handle_555(error, *args, **kwargs)
        if self._is_429(error):
            return self.handle_429(error, *args, **kwargs)
        raise error

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
        for _ in range(max_retries):
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
