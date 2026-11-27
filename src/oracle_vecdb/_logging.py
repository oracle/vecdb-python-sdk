##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""Private SDK operation logging controlled by VECDB_DEBUG."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
import logging
import os
import re
import secrets
import time
from typing import Any, Callable, Iterator, TypeVar, cast

_TRACE_ENABLED = False
_MAX_EVENTS = 256
_LEVELS = {
    "NOTSET": 0,
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}
_ALIASES = {"WARN": "WARNING", "FATAL": "CRITICAL"}
_OPERATIONS = frozenset(
    "describe_vector_database list_vector_tables create_vector_table "
    "describe_vector_table drop_vector_table update_vector_table_annotation "
    "generate_embedding upsert_vectors list_vectors delete_vectors load_vectors "
    "list_vector_load_jobs describe_vector_load_job get_vector_load_job_log "
    "query rerank create_index list_index_jobs describe_index_job "
    "get_index_job_log rebuild_index describe_index drop_index list_models "
    "load_model describe_model drop_model get_vecdb_oauth_token".split()
)
_ENUMS = {
    "event": frozenset(
        "operation.started operation.completed http.completed phase.completed "
        "batch.completed retry.scheduled retry.stopped diagnostics.suppressed".split()
    ),
    "operation": _OPERATIONS,
    "transport": frozenset({"ords"}),
    "phase": frozenset({"http_call", "deserialize", "retry_sleep"}),
    "outcome": frozenset({"success", "error", "cancelled"}),
    "retry_owner": frozenset({"ords_response_handler"}),
    "reason": frozenset(
        "already_normalized operation_not_retryable error_not_retryable "
        "retry_limit_zero retry_limit_exhausted transient_status".split()
    ),
    "transport_category": frozenset(
        "connect_timeout read_timeout timeout dns_failure connect_failure "
        "connection_reset socket_failure ssl_error certificate_error".split()
    ),
}
_INTS = frozenset(
    "schema_version attempt retry_number batch_count batch_index result_count "
    "suppressed_event_count".split()
)
_DURATIONS = frozenset({"elapsed_ms", "delay_ms", "sleep_elapsed_ms"})
_IDS = frozenset({"operation_id", "parent_operation_id"})
# Codes, never free-form messages. HTTP-unknown and arbitrary server codes omit.
_CODE = re.compile(
    r"(?:ORA-\d{5}|ORDS-\d{5}|HTTP-[1-5]\d{2}|TIMEOUT|DNS_FAILURE|"
    r"CONNECTION_FAILURE|CONNECTION_RESET|SOCKET_FAILURE|SSL_ERROR|CERTIFICATE_ERROR)\Z"
)
_F = TypeVar("_F", bound=Callable[..., Any])
_SDK_LOGGER = logging.getLogger("oracle_vecdb")
_LOGGERS = {
    name: logging.getLogger("oracle_vecdb." + name)
    for name in ("operations", "ords", "auth", "performance")
}


def _read_logging_environment() -> tuple[int | None, bool]:
    """Resolve the single logging switch; never echo invalid environment values."""
    value = os.getenv("VECDB_DEBUG", "").strip().upper()
    if not value:
        return None, False
    value = {
        "1": "DEBUG",
        "TRUE": "DEBUG",
        "YES": "DEBUG",
        "ON": "DEBUG",
        "0": "OFF",
        "FALSE": "OFF",
        "NO": "OFF",
    }.get(value, value)
    value = _ALIASES.get(value, value)
    if value == "TRACE":
        return logging.DEBUG, True
    if value == "OFF":
        return logging.CRITICAL + 1, False
    if value not in _LEVELS:
        raise ValueError(
            "VECDB_DEBUG must be a logging level, TRACE, OFF, or a boolean"
        )
    return _LEVELS[value], False


class _FallbackConsoleHandler(logging.StreamHandler):
    """Fallback console output only while the application has no handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        logger: logging.Logger | None = logging.getLogger(record.name)
        while logger is not None:
            if any(
                not isinstance(
                    handler, (logging.NullHandler, _FallbackConsoleHandler)
                )
                for handler in logger.handlers
            ):
                return False
            if not logger.propagate:
                break
            logger = logger.parent
        return super().filter(record)

    def handleError(self, record: logging.LogRecord) -> None:
        return


def _configure_logging() -> None:
    """Configure only the package namespace, once at import (reload-safe)."""
    global _TRACE_ENABLED
    level, _TRACE_ENABLED = _read_logging_environment()
    logger = logging.getLogger("oracle_vecdb")
    if not any(
        type(handler) is logging.NullHandler for handler in logger.handlers
    ):
        logger.addHandler(logging.NullHandler())
    if level is None:
        return
    logger.setLevel(level)
    if level <= logging.CRITICAL and not any(
        isinstance(handler, _FallbackConsoleHandler)
        for handler in logger.handlers
    ):
        handler = _FallbackConsoleHandler()
        handler.setFormatter(
            logging.Formatter("%(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)


@dataclass
class _LogEventBudget:
    remaining: int
    suppressed: int = 0


@dataclass
class _OperationLogContext:
    operation: str
    operation_id: str
    parent_id: str | None
    budget: _LogEventBudget
    root: bool
    started: int | None
    batch_count: int = 0
    result_count: int | None = None


_CURRENT_OPERATION: ContextVar[_OperationLogContext | None] = ContextVar(
    "vecdb_operation", default=None
)


def _filter_log_fields(values: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in values.items():
        if key in _ENUMS:
            if type(value) is str and value in _ENUMS[key]:
                safe[key] = value
        elif key in _IDS:
            if type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value):
                safe[key] = value
        elif key in _INTS:
            if type(value) is int and 0 <= value <= 2**63 - 1:
                safe[key] = value
        elif key in _DURATIONS:
            if type(value) in (int, float) and 0 <= value <= 1e15:
                safe[key] = value
        elif key == "http_status":
            if type(value) is int and 100 <= value <= 599:
                safe[key] = value
        elif (
            key == "error_code"
            and type(value) is str
            and len(value) <= 128
            and _CODE.fullmatch(value)
        ):
            safe[key] = value
    return safe


def _log_event(
    event: str,
    channel: str,
    level: int,
    *,
    terminal: bool = False,
    **values: Any,
) -> None:
    """Write an allowlisted SDK log event without changing business outcomes."""
    try:
        state = _CURRENT_OPERATION.get()
        if state is None or _SDK_LOGGER.level > logging.CRITICAL:
            return
        logger = _LOGGERS[channel]
        if not logger.isEnabledFor(level):
            return
        if not terminal:
            if state.budget.remaining <= 0:
                state.budget.suppressed += 1
                return
            state.budget.remaining -= 1
        safe = _filter_log_fields(
            {
                **values,
                "schema_version": 1,
                "event": event,
                "operation": state.operation,
                "transport": "ords",
                "operation_id": state.operation_id,
                "parent_operation_id": state.parent_id,
            }
        )
        message = " ".join(f"{key}={value}" for key, value in safe.items())[
            :2048
        ]
        logger.log(
            level,
            message,
            extra={"vecdb": safe},
        )
    except Exception:
        # Logging is best-effort. No raw exceptions or recursive fallback sink.
        return


def _error_log_fields(error: BaseException) -> dict[str, Any]:
    try:
        # Only stored scalars; do not invoke arbitrary error properties/str/repr.
        data = object.__getattribute__(error, "__dict__")
        return _filter_log_fields(
            {
                "http_status": data.get("status"),
                "error_code": data.get("error_code"),
                "transport_category": data.get("transport_category"),
            }
        )
    except Exception:
        return {}


def _is_logging_enabled(channel: str) -> bool:
    """Check reachable output across the loggers used by this operation."""
    try:
        if _SDK_LOGGER.level > logging.CRITICAL:
            return False
        loggers = (
            (_LOGGERS["auth"],)
            if channel == "auth"
            else tuple(
                logger for name, logger in _LOGGERS.items() if name != "auth"
            )
        )
        for operation_logger in loggers:
            if not any(
                operation_logger.isEnabledFor(level)
                for level in (logging.DEBUG, logging.INFO, logging.ERROR)
            ):
                continue
            logger: logging.Logger | None = operation_logger
            while logger is not None:
                if any(
                    not isinstance(h, logging.NullHandler)
                    for h in logger.handlers
                ):
                    return True
                if not logger.propagate:
                    break
                logger = logger.parent
    except Exception:
        # Logger failures must not prevent execution of the SDK call.
        return False
    return False


def _logging_timestamp_ns() -> int | None:
    try:
        return time.perf_counter_ns()
    except Exception:
        return None


def _elapsed_ms(started: int | None) -> float | None:
    if started is None:
        return None
    ended = _logging_timestamp_ns()
    return (ended - started) / 1e6 if ended is not None else None


@contextmanager
def _operation_logging_context(
    name: str, *, independent: bool = False
) -> Iterator[None]:
    """Correlate operation events and log a completion summary on exit."""
    channel = "auth" if independent else "operations"
    token = None
    try:
        if not _is_logging_enabled(channel):
            state = None
        else:
            parent = None if independent else _CURRENT_OPERATION.get()
            state = _OperationLogContext(
                name,
                secrets.token_hex(16),
                parent.operation_id if parent else None,
                parent.budget if parent else _LogEventBudget(_MAX_EVENTS),
                parent is None,
                _logging_timestamp_ns(),
            )
        token = _CURRENT_OPERATION.set(state)
    except Exception:
        state = None
        token = _CURRENT_OPERATION.set(None)
    error: BaseException | None = None
    try:
        if state and _TRACE_ENABLED:
            _log_event("operation.started", channel, logging.DEBUG)
        yield
    except BaseException as exc:
        error = exc
        raise
    finally:
        try:
            if state is not None:
                elapsed = _elapsed_ms(state.started)
                if state.root and state.budget.suppressed:
                    _log_event(
                        "diagnostics.suppressed",
                        "performance",
                        logging.DEBUG,
                        terminal=True,
                        suppressed_event_count=state.budget.suppressed,
                    )
                _log_event(
                    "operation.completed",
                    channel,
                    (
                        logging.ERROR
                        if isinstance(error, Exception)
                        else (
                            logging.DEBUG if error is not None else logging.INFO
                        )
                    ),
                    terminal=True,
                    outcome=(
                        "success"
                        if error is None
                        else (
                            "error"
                            if isinstance(error, Exception)
                            else "cancelled"
                        )
                    ),
                    elapsed_ms=elapsed,
                    batch_count=(
                        state.batch_count
                        if state.operation == "upsert_vectors"
                        else None
                    ),
                    result_count=state.result_count,
                    **(_error_log_fields(error) if error is not None else {}),
                )
        except (
            Exception
        ):  # nosec B110 - logging must preserve business outcomes
            pass  # Best-effort completion must preserve the business outcome.
        finally:
            if token is not None:
                _CURRENT_OPERATION.reset(token)


def _logging_wrapper(function: _F) -> _F:
    """Wrap an SDK call with operation outcome and duration logging."""
    independent = function.__name__ == "get_vecdb_oauth_token"
    channel = "auth" if independent else "operations"

    @wraps(function)
    def call(*args: Any, **kwargs: Any) -> Any:
        if _CURRENT_OPERATION.get() is None and not _is_logging_enabled(
            channel
        ):
            return function(*args, **kwargs)
        with _operation_logging_context(
            function.__name__, independent=independent
        ):
            result = function(*args, **kwargs)
            _record_result_count(result)
            return result

    return cast(_F, call)


@contextmanager
def _log_phase(name: str) -> Iterator[dict[str, Any]]:
    """Log duration and outcome of an HTTP, deserialization or retry phase."""
    values: dict[str, Any] = {}
    try:
        state = _CURRENT_OPERATION.get()
        enabled = (
            state is not None
            and _TRACE_ENABLED
            and _LOGGERS["ords"].isEnabledFor(logging.DEBUG)
        )
        started = _logging_timestamp_ns() if enabled else None
    except Exception:
        enabled, started = False, None
    outcome = "success"
    try:
        yield values
    except BaseException:
        outcome = "error"
        raise
    finally:
        try:
            if enabled:
                elapsed = _elapsed_ms(started)
                _log_event(
                    (
                        "http.completed"
                        if name == "http_call"
                        else "phase.completed"
                    ),
                    "ords",
                    logging.DEBUG,
                    phase=name,
                    outcome=outcome,
                    elapsed_ms=elapsed,
                    sleep_elapsed_ms=elapsed if name == "retry_sleep" else None,
                    **values,
                )
        except (
            Exception
        ):  # nosec B110 - logging must preserve business outcomes
            pass  # Logging failures never replace results.


def _record_http_status(values: dict[str, Any], response: Any) -> None:
    try:
        values["http_status"] = object.__getattribute__(
            response, "__dict__"
        ).get("status")
    except Exception:
        return


def _record_result_count(response: Any) -> None:
    try:
        state = _CURRENT_OPERATION.get()
        if state is None or state.operation == "upsert_vectors":
            return
        # Only SDK response models and their stored list, not arbitrary objects.
        from .data_types.responses import _VecDBModel

        if isinstance(response, _VecDBModel):
            items = object.__getattribute__(response, "__dict__").get("items")
            if type(items) is list:
                state.result_count = len(items)
    except Exception:
        return


def _record_upsert_result(response: Any) -> None:
    try:
        if _CURRENT_OPERATION.get() is None:
            return
        if type(response) is dict:
            count = response.get("upserted_count")
        else:
            count = object.__getattribute__(response, "__dict__").get(
                "upserted_count"
            )
        _record_upsert_batch(count)
    except Exception:
        _record_upsert_batch(None)


def _record_upsert_batch(count: Any) -> None:
    try:
        state = _CURRENT_OPERATION.get()
        if state is not None:
            state.batch_count += 1
            if type(count) is int and count >= 0:
                state.result_count = (state.result_count or 0) + count
            if _TRACE_ENABLED:
                _log_event(
                    "batch.completed",
                    "operations",
                    logging.DEBUG,
                    batch_index=state.batch_count,
                    result_count=count,
                )
    except Exception:
        return
