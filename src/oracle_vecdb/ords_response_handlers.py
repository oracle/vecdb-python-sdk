"""Small response handlers shared by the ORDS service facade."""

from datetime import timezone
from email.utils import parsedate_to_datetime
from functools import wraps
import logging
import math
import secrets
import time
from types import MethodType
from typing import Any, Callable

from .vecdb_exception import VecDBException
from ._logging import _log_event, _log_phase


class ORDSResponseHandler:
    """Callable wrapper for extensible ORDS response handling."""

    # Classify every decorated ORDS operation explicitly. Unknown operations
    # fail closed until their retry behavior is reviewed.
    _RETRY_CLASSIFICATIONS = {
        "describe_vector_database": "safe",
        "list_vector_tables": "safe",
        "create_vector_table": "non-idempotent",
        "describe_vector_table": "safe",
        "drop_vector_table": "non-idempotent",
        "update_vector_table_annotation": "non-idempotent",
        "generate_embedding": "safe",
        "upsert_vectors": "non-idempotent",
        "list_vectors": "safe",
        "delete_vectors": "non-idempotent",
        "load_vectors": "non-idempotent",
        "list_vector_load_jobs": "safe",
        "describe_vector_load_job": "safe",
        "get_vector_load_job_log": "safe",
        "query": "safe",
        "rerank": "safe",
        "create_index": "non-idempotent",
        "list_index_jobs": "safe",
        "describe_index_job": "safe",
        "get_index_job_log": "safe",
        "rebuild_index": "non-idempotent",
        "describe_index": "safe",
        "drop_index": "non-idempotent",
        "list_models": "safe",
        "load_model": "non-idempotent",
        "describe_model": "safe",
        "drop_model": "non-idempotent",
    }
    _RETRYABLE_CLASSIFICATIONS = frozenset({"safe", "idempotent"})

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
            self._log_retry_decision("already_normalized")
            raise
        except Exception as error:
            return self._handle_exception(error, *args, **kwargs)

    def _handle_exception(
        self, error: Exception, *args: Any, **kwargs: Any
    ) -> Any:
        if self._is_555(error):
            if not self._is_retryable_operation():
                self._log_retry_decision("operation_not_retryable")
                raise error
            return self.handle_555(error, *args, **kwargs)
        if self._is_429(error):
            if not self._is_retryable_operation():
                self._log_retry_decision("operation_not_retryable")
                raise error
            return self.handle_429(error, *args, **kwargs)
        self._log_retry_decision("error_not_retryable")
        raise error

    def _operation_retry_classification(self) -> str:
        return self._RETRY_CLASSIFICATIONS.get(
            self.function.__name__, "unclassified"
        )

    def _is_retryable_operation(self) -> bool:
        return (
            self._operation_retry_classification()
            in self._RETRYABLE_CLASSIFICATIONS
        )

    def _log_retry_decision(self, reason: str, **values: Any) -> None:
        _log_event(
            "retry.stopped",
            "ords",
            logging.DEBUG,
            reason=reason,
            retry_owner="ords_response_handler",
            **values,
        )

    def handle_555(self, error: Exception, *args: Any, **kwargs: Any) -> Any:
        """Retry transient ORDS 555/ORDS-25001 responses."""
        return self._retry(error, *args, **kwargs)

    def handle_429(self, error: Exception, *args: Any, **kwargs: Any) -> Any:
        """Retry ORDS HTTP 429 responses in the public service facade."""
        return self._retry(error, *args, **kwargs)

    def _retry(
        self,
        error: Exception,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Keep each status's retry budget across the entire operation."""
        limits = {
            555: self._max_retries(args, "max_retry_count_error_555"),
            429: self._max_retries(args, "max_retry_count_error_429"),
        }
        attempts = {555: 0, 429: 0}
        latest_error = error
        while True:
            if self._is_555(latest_error):
                status = 555
            elif self._is_429(latest_error):
                status = 429
            else:
                self._log_retry_decision("error_not_retryable")
                raise latest_error

            retry_number = attempts[status]
            max_retries = limits[status]
            if retry_number >= max_retries:
                self._log_retry_decision(
                    (
                        "retry_limit_zero"
                        if max_retries == 0
                        else "retry_limit_exhausted"
                    ),
                    attempt=1 + sum(attempts.values()),
                    http_status=status,
                )
                raise latest_error

            self._sleep_before_retry(
                latest_error,
                retry_number,
                args,
                attempt=1 + sum(attempts.values()),
            )
            # A status change must not replenish a consumed retry budget.
            attempts[status] += 1
            try:
                return self.function(*args, **kwargs)
            except VecDBException:
                # The exception is already normalized and must not be retried
                # or wrapped a second time.
                self._log_retry_decision("already_normalized")
                raise
            except Exception as next_error:
                latest_error = next_error

    @classmethod
    def _sleep_before_retry(
        cls,
        error: Exception,
        retry_number: int,
        args: tuple[Any, ...],
        *,
        attempt: int = 1,
    ) -> None:
        """Honor Retry-After and otherwise use bounded jittered backoff."""
        if not cls._is_429(error):
            _log_event(
                "retry.scheduled",
                "ords",
                logging.DEBUG,
                reason="transient_status",
                retry_owner="ords_response_handler",
                attempt=attempt,
                retry_number=attempt,
                http_status=555,
                delay_ms=0.0,
            )
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

        _log_event(
            "retry.scheduled",
            "ords",
            logging.DEBUG,
            reason="transient_status",
            retry_owner="ords_response_handler",
            attempt=attempt,
            retry_number=attempt,
            http_status=429,
            delay_ms=retry_after * 1000,
        )
        with _log_phase("retry_sleep") as observation:
            time.sleep(retry_after)
            observation["delay_ms"] = retry_after * 1000

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
