"""Service-independent VecDB exception normalization.

Service adapters should inherit :class:`VecDBException` so generated
transport exceptions expose the same structured diagnostics regardless of the
underlying protocol or service implementation.
"""

from __future__ import annotations

import errno
import json
import re
import socket
import ssl
import traceback
from collections.abc import Mapping
from typing import Any, Dict, Optional, cast

from urllib3 import exceptions as urllib3_exceptions

_REDACTED = "<redacted>"
_CIRCULAR_REFERENCE = "<circular reference>"
_NESTED_DIAGNOSTIC_TRUNCATED = "<nested diagnostic truncated>"
_MAX_DIAGNOSTIC_DEPTH = 64
_MISSING = object()

_TRANSPORT_CONNECT_TIMEOUT = "connect_timeout"
_TRANSPORT_READ_TIMEOUT = "read_timeout"
_TRANSPORT_TIMEOUT = "timeout"
_TRANSPORT_DNS_FAILURE = "dns_failure"
_TRANSPORT_CONNECT_FAILURE = "connect_failure"
_TRANSPORT_CONNECTION_RESET = "connection_reset"
_TRANSPORT_SOCKET_FAILURE = "socket_failure"
_TRANSPORT_SSL_ERROR = "ssl_error"
_TRANSPORT_CERTIFICATE_ERROR = "certificate_error"

_TRANSPORT_TIMEOUT_CATEGORIES = {
    _TRANSPORT_CONNECT_TIMEOUT,
    _TRANSPORT_READ_TIMEOUT,
    _TRANSPORT_TIMEOUT,
}
_RETRYABLE_TRANSPORT_CATEGORIES = {
    _TRANSPORT_CONNECT_TIMEOUT,
    _TRANSPORT_READ_TIMEOUT,
    _TRANSPORT_TIMEOUT,
    _TRANSPORT_CONNECT_FAILURE,
    _TRANSPORT_CONNECTION_RESET,
    _TRANSPORT_SOCKET_FAILURE,
}
_TRANSPORT_ERROR_CODES = {
    _TRANSPORT_CONNECT_TIMEOUT: "TIMEOUT",
    _TRANSPORT_READ_TIMEOUT: "TIMEOUT",
    _TRANSPORT_TIMEOUT: "TIMEOUT",
    _TRANSPORT_DNS_FAILURE: "DNS_FAILURE",
    _TRANSPORT_CONNECT_FAILURE: "CONNECTION_FAILURE",
    _TRANSPORT_CONNECTION_RESET: "CONNECTION_RESET",
    _TRANSPORT_SOCKET_FAILURE: "SOCKET_FAILURE",
    _TRANSPORT_SSL_ERROR: "SSL_ERROR",
    _TRANSPORT_CERTIFICATE_ERROR: "CERTIFICATE_ERROR",
}
_TRANSPORT_GUIDANCE = {
    _TRANSPORT_DNS_FAILURE: (
        "The endpoint hostname could not be resolved.",
        "Verify the host name, DNS configuration, and network access.",
    ),
    _TRANSPORT_CONNECT_FAILURE: (
        "The SDK could not establish a network connection to the endpoint.",
        "Verify the endpoint and network access, then retry if the failure is transient.",
    ),
    _TRANSPORT_CONNECTION_RESET: (
        "The network connection was reset before the operation completed.",
        "Retry only when the operation is safe to repeat, and verify network stability if it persists.",
    ),
    _TRANSPORT_SOCKET_FAILURE: (
        "The network socket failed before the operation completed.",
        "Retry only when the operation is safe to repeat, and verify network stability if it persists.",
    ),
    _TRANSPORT_SSL_ERROR: (
        "TLS/SSL negotiation with the endpoint failed.",
        "Verify TLS settings, the CA bundle, and client certificate configuration.",
    ),
    _TRANSPORT_CERTIFICATE_ERROR: (
        "The endpoint certificate could not be validated.",
        "Verify the CA bundle, certificate chain, hostname, and client certificate configuration.",
    ),
}

# These names identify values that must not survive in an exception object.
# Keep exact identifiers such as ``request_id``, ``connection_id``, and
# ``query_id`` available while also recognizing sensitive composite names such
# as ``token_value`` inside otherwise safe nested request fields.
_SENSITIVE_VALUE_KEYS = {
    "authorization",
    "proxy_authorization",
    "cookie",
    "set_cookie",
    "x_api_key",
    "api_key",
    "apikey",
    "password",
    "passwd",
    "pwd",
    "secret",
    "client_secret",
    "token",
    "bearer_token",
    "oauth_token",
    "access_token",
    "refresh_token",
    "id_token",
    "credential",
    "credentials",
    "auth",
    "authentication",
    "header",
    "headers",
    "private_key",
    "username",
    "database",
    "database_name",
    "db",
    "schema",
    "schema_name",
    "connection",
    "connection_string",
    "dsn",
    "sql",
    "query",
    "query_by",
    "filter",
    "filters",
    "document",
    "documents",
    "metadata",
    "payload",
    "vector",
    "vectors",
    "embedding",
    "embeddings",
    "url",
}

_SENSITIVE_KEY_FRAGMENTS = {
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "header",
    "headers",
    "password",
    "passwd",
    "private_key",
    "pwd",
    "secret",
    "token",
}

_SAFE_ANNOTATION_KEYS = {
    "application",
    "department",
    "dimension",
    "metric",
    "owner",
    "tier",
    "updated",
    "version",
}

_RAW_KEY_VALUE_PATTERN = re.compile(
    r"(?P<key_prefix>[\"']?)(?P<key>[A-Za-z][A-Za-z0-9_.-]*)"
    r"(?P<key_suffix>[\"']?)(?P<before_separator>\s*)"
    r"(?P<separator>[:=])(?P<after_separator>\s*)"
    r"(?:(?P<value_quote>[\"'])(?P<quoted_value>[^\"']*)"
    r"(?P=value_quote)|(?P<bare_value>[^,\s}\]]+))"
)
_VECTOR_ID_NULL_GUIDANCE = (
    "The vector ID is missing or exceeds the vector table's ID-column limit."
)
_VECTOR_ID_NULL_ACTION = (
    "Verify that each vector ID complies with the vector table's documented "
    "ID-column limit. Alternatively, create the table with "
    'table_params={"auto_generate_id": True}.'
)


def _normalized_key(value: Any) -> str:
    text = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", str(value))
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _is_sensitive_key(value: Any) -> bool:
    normalized = _normalized_key(value)
    return normalized in _SENSITIVE_VALUE_KEYS or any(
        normalized == fragment
        or normalized.startswith(f"{fragment}_")
        or normalized.endswith(f"_{fragment}")
        or f"_{fragment}_" in normalized
        for fragment in _SENSITIVE_KEY_FRAGMENTS
    )


def _safe_string(value: Any) -> str:
    """Return a string for diagnostics without trusting ``str``/``repr``."""
    if isinstance(value, str):
        return value
    rendered = _MISSING
    try:
        rendered = str(value)
    except Exception:  # pragma: no cover - exercised by hostile objects
        rendered = _MISSING
    if isinstance(rendered, str):
        return rendered
    rendered = _MISSING
    try:
        rendered = repr(value)
    except Exception:  # pragma: no cover - exercised by hostile objects
        rendered = _MISSING
    if isinstance(rendered, str):
        return rendered
    try:
        type_name = type(value).__name__
    except Exception:  # pragma: no cover - type() is normally infallible
        type_name = "object"
    return f"<unprintable {type_name}>"


def _safe_attribute(value: Any, name: str, default: Any = None) -> Any:
    """Read a third-party attribute without allowing it to mask an error."""
    try:
        return getattr(value, name)
    except Exception:  # pragma: no cover - exercised by hostile objects
        return default


def _exception_chain(error: Optional[BaseException]) -> list[BaseException]:
    """Return an exception and its wrapped causes without retaining them."""
    if error is None:
        return []
    pending = [error]
    seen: set[int] = set()
    chain: list[BaseException] = []
    while pending:
        current = pending.pop(0)
        if not isinstance(current, BaseException) or id(current) in seen:
            continue
        seen.add(id(current))
        chain.append(current)
        for attribute in (
            "reason",
            "original_error",
            "__cause__",
            "__context__",
        ):
            nested = _safe_attribute(current, attribute)
            if isinstance(nested, BaseException) and id(nested) not in seen:
                pending.append(nested)
        arguments = _safe_attribute(current, "args", ())
        if isinstance(arguments, tuple):
            for argument in arguments:
                if (
                    isinstance(argument, BaseException)
                    and id(argument) not in seen
                ):
                    pending.append(argument)
    return chain


def _has_errno(error: BaseException, values: set[int]) -> bool:
    """Return whether a transport error exposes one of the given errnos."""
    value = _safe_attribute(error, "errno")
    try:
        return value in values
    except (TypeError, ValueError):
        return False


def _transport_classification(
    error: Optional[BaseException],
) -> tuple[Optional[str], Optional[str]]:
    """Classify a transport exception and return its category and source type."""
    nodes = _exception_chain(error)
    if not nodes:
        return None, None

    rendered_nodes = [(_safe_string(node).lower(), node) for node in nodes]

    def first_node(predicate: Any) -> Optional[BaseException]:
        return next((node for node in nodes if predicate(node)), None)

    def source_type(node: Optional[BaseException]) -> Optional[str]:
        return type(node).__name__ if node is not None else None

    certificate_markers = (
        "certificate verify failed",
        "certificate validation failed",
        "unable to get local issuer",
        "hostname mismatch",
        "certificate is not yet valid",
    )
    certificate_node = first_node(
        lambda node: isinstance(node, ssl.SSLCertVerificationError)
    )
    if certificate_node is not None:
        return _TRANSPORT_CERTIFICATE_ERROR, source_type(certificate_node)
    certificate_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if any(marker in text for marker in certificate_markers)
        ),
        None,
    )
    if certificate_text_node is not None:
        # A generated ApiException often contains the certificate text while
        # retaining the concrete urllib3 SSL exception as its cause. Prefer
        # that cause as the diagnostic type without losing the category.
        ssl_node = first_node(
            lambda node: isinstance(
                node, (ssl.SSLError, urllib3_exceptions.SSLError)
            )
        )
        return _TRANSPORT_CERTIFICATE_ERROR, source_type(
            ssl_node or certificate_text_node
        )

    ssl_node = first_node(
        lambda node: isinstance(
            node, (ssl.SSLError, urllib3_exceptions.SSLError)
        )
    )
    if ssl_node is not None:
        return _TRANSPORT_SSL_ERROR, source_type(ssl_node)
    ssl_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if "sslerror" in type(node).__name__.lower() or "tls" in text
        ),
        None,
    )
    if ssl_text_node is not None:
        return _TRANSPORT_SSL_ERROR, source_type(ssl_text_node)

    dns_markers = (
        "failed to resolve",
        "name or service not known",
        "nodename nor servname",
        "temporary failure in name resolution",
        "getaddrinfo failed",
    )
    dns_node = first_node(
        lambda node: isinstance(
            node, (socket.gaierror, urllib3_exceptions.NameResolutionError)
        )
    )
    if dns_node is not None:
        return _TRANSPORT_DNS_FAILURE, source_type(dns_node)
    dns_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if "nameresolutionerror" in type(node).__name__.lower()
            or any(marker in text for marker in dns_markers)
        ),
        None,
    )
    if dns_text_node is not None:
        return _TRANSPORT_DNS_FAILURE, source_type(dns_text_node)

    read_timeout_node = first_node(
        lambda node: isinstance(node, urllib3_exceptions.ReadTimeoutError)
    )
    if read_timeout_node is not None:
        return _TRANSPORT_READ_TIMEOUT, source_type(read_timeout_node)
    read_timeout_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if "readtimeout" in type(node).__name__.lower()
            or "read timed out" in text
        ),
        None,
    )
    if read_timeout_text_node is not None:
        return _TRANSPORT_READ_TIMEOUT, source_type(read_timeout_text_node)

    reset_node = first_node(lambda node: isinstance(node, ConnectionResetError))
    if reset_node is not None:
        return _TRANSPORT_CONNECTION_RESET, source_type(reset_node)
    reset_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if "connection reset" in text or "connectionreseterror" in text
        ),
        None,
    )
    if reset_text_node is not None:
        return _TRANSPORT_CONNECTION_RESET, source_type(reset_text_node)

    connect_failure_node = first_node(
        lambda node: isinstance(
            node,
            (
                urllib3_exceptions.NewConnectionError,
                ConnectionRefusedError,
                urllib3_exceptions.ProxyError,
            ),
        )
        or _has_errno(
            node,
            {errno.ECONNREFUSED, errno.ENETUNREACH, errno.EHOSTUNREACH},
        )
    )
    if connect_failure_node is not None:
        return _TRANSPORT_CONNECT_FAILURE, source_type(connect_failure_node)
    connect_failure_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if "connection refused" in text or "failed to establish" in text
        ),
        None,
    )
    if connect_failure_text_node is not None:
        return _TRANSPORT_CONNECT_FAILURE, source_type(
            connect_failure_text_node
        )

    connect_timeout_node = first_node(
        lambda node: isinstance(node, urllib3_exceptions.ConnectTimeoutError)
    )
    if connect_timeout_node is not None:
        return _TRANSPORT_CONNECT_TIMEOUT, source_type(connect_timeout_node)
    connect_timeout_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if "connecttimeout" in type(node).__name__.lower()
            or "connect timed out" in text
            or "connection timeout" in text
        ),
        None,
    )
    if connect_timeout_text_node is not None:
        return _TRANSPORT_CONNECT_TIMEOUT, source_type(
            connect_timeout_text_node
        )

    socket_markers = (
        "broken pipe",
        "connection aborted",
        "remote end closed connection",
        "connection broken",
    )
    socket_node = first_node(
        lambda node: isinstance(
            node,
            (
                BrokenPipeError,
                ConnectionAbortedError,
                ConnectionError,
                urllib3_exceptions.ProtocolError,
            ),
        )
        or _has_errno(node, {errno.EPIPE, errno.ECONNABORTED, errno.ENOTCONN})
    )
    if socket_node is not None:
        return _TRANSPORT_SOCKET_FAILURE, source_type(socket_node)
    socket_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if any(marker in text for marker in socket_markers)
        ),
        None,
    )
    if socket_text_node is not None:
        return _TRANSPORT_SOCKET_FAILURE, source_type(socket_text_node)

    timeout_node = first_node(
        lambda node: isinstance(
            node, (TimeoutError, urllib3_exceptions.TimeoutError)
        )
    )
    if timeout_node is not None:
        return _TRANSPORT_TIMEOUT, source_type(timeout_node)
    timeout_text_node = next(
        (
            node
            for text, node in rendered_nodes
            if "timed out" in text or "timeout=" in text
        ),
        None,
    )
    if timeout_text_node is not None:
        return _TRANSPORT_TIMEOUT, source_type(timeout_text_node)

    return None, None


def _is_timeout_exception(error: Optional[BaseException]) -> bool:
    """Return whether an exception represents a client-side timeout."""
    category, _ = _transport_classification(error)
    return category in _TRANSPORT_TIMEOUT_CATEGORIES


class _SanitizedServiceError(Exception):
    """Safe, displayable copy of a transport exception."""

    def __init__(self, class_name: str, **fields: Any) -> None:
        self.class_name = class_name
        for name, value in fields.items():
            setattr(self, name, value)
        super().__init__(self._safe_text(fields.get("reason")))

    @staticmethod
    def _safe_text(value: Any) -> str:
        if value is None:
            return ""
        return _safe_string(value)

    def __str__(self) -> str:
        return self._safe_text(getattr(self, "reason", None))


class VecDBException(Exception):
    """Base exception with normalized service error details."""

    # Keep the public exception concise by default. Integration tests can
    # enable this when the complete ORDSErrorResponse is needed for triage.
    include_full_ords_response = False

    def __init__(
        self,
        status: Any = None,
        reason: Optional[str] = None,
        *,
        body: Optional[str] = None,
        data: Optional[Any] = None,
        headers: Optional[Any] = None,
        operation: Optional[str] = None,
        arguments: Optional[Any] = None,
        service_name: Optional[str] = None,
        service_error: Optional[BaseException] = None,
        service_error_class_name: Optional[str] = None,
        service_trace: Optional[str] = None,
        diagnostic_trace: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> None:
        self.status = status
        self.reason = self._redact_value(reason)
        self.body = self._redact_value(body)
        self.data = self._redact_value(data)
        self.headers = self._redact_value(headers)
        self.operation = operation
        self.arguments = self._sanitize_arguments(arguments)
        self.service_name = service_name
        (
            self.transport_category,
            self.transport_error_type,
        ) = _transport_classification(service_error)
        self.retryable: Optional[bool] = (
            self.transport_category in _RETRYABLE_TRANSPORT_CATEGORIES
            if self.transport_category is not None
            else None
        )
        self.service_error = self._safe_service_error(service_error)
        self.service_error_class_name = service_error_class_name
        # Keep only a sanitized snapshot. Retaining the transport exception
        # would also retain its raw response, headers, and args.
        self.original_exception = self.service_error
        self.original_exception_type = (
            type(service_error) if service_error is not None else None
        )
        self.original_exception_type_name = (
            type(service_error).__name__ if service_error is not None else None
        )
        # Public category for callers that need to distinguish validation,
        # type, and transport failures without inspecting original_exception.
        self.exception_type = self.original_exception_type_name
        # Transport exceptions can embed Authorization values and signed URLs
        # in their rendered tracebacks. Never retain those values in a public
        # diagnostic field that callers may reasonably send to a log sink.
        self.service_trace = self._redact_diagnostic_text(service_trace)
        self.diagnostic_trace = self._redact_diagnostic_text(diagnostic_trace)
        self.stack_trace = self._redact_diagnostic_text(stack_trace)
        self.error_code: Optional[str] = None
        self.error_message: Optional[str] = None
        self.error_type: Optional[str] = None
        self.error_instance: Optional[str] = None
        self.cause: Optional[str] = None
        self.action: Optional[str] = None
        self._customize_error()
        # ``from_service_error`` may construct a compatibility subclass that
        # also inherits a generated ``ApiException``. Calling ``super()``
        # would invoke that class with ``vecdb_message`` as its first
        # positional argument; generated ApiException treats that argument as
        # ``status`` and replaces the original HTTP status. Initialise the
        # built-in exception directly to retain the normalized fields.
        Exception.__init__(self, self.vecdb_message)

    @classmethod
    def from_service_error(
        cls,
        operation: str,
        arguments: Any,
        service_name: str,
        error: BaseException,
    ) -> "VecDBException":
        """Wrap a transport/service exception at a handwritten adapter boundary."""
        # Keep compatibility with callers that still catch the generated
        # ORDS exception class, while exposing the common VecDB wrapper type.
        wrapper_type = cls
        if not isinstance(error, cls):
            try:
                wrapper_type = type(
                    "VecDBException",
                    (cls, type(error)),
                    {"__module__": cls.__module__},
                )
            except TypeError:
                wrapper_type = cls
        values = {
            "status": _safe_attribute(error, "status"),
            "reason": _safe_attribute(error, "reason"),
            "body": _safe_attribute(error, "body"),
            "data": _safe_attribute(error, "data"),
            "headers": _safe_attribute(error, "headers"),
            "operation": operation,
            "arguments": cls._sanitize_arguments(arguments),
            "service_name": service_name,
            "service_error": error,
            "service_error_class_name": type(error).__name__,
            "service_trace": "",
        }
        try:
            values["service_trace"] = "".join(
                traceback.format_exception(
                    type(error), error, error.__traceback__
                )
            )
        except Exception:  # pragma: no cover - exercised by hostile objects
            values["service_trace"] = _safe_string(error)
        try:
            return wrapper_type(**values)
        except TypeError:
            # Some third-party validation exceptions cannot be subclassed or
            # constructed with normal Exception arguments. The ORDS adapter
            # normally excludes those before calling this method, but retain
            # a safe fallback for other service adapters.
            return cls(**values)

    @staticmethod
    def _safe_service_error(
        error: Optional[BaseException],
    ) -> Optional[BaseException]:
        if error is None or isinstance(error, _SanitizedServiceError):
            return error
        fields = {}
        for name in (
            "status",
            "reason",
            "body",
            "data",
            "headers",
            "error_code",
            "error_message",
            "error_type",
            "error_instance",
        ):
            field = _safe_attribute(error, name, _MISSING)
            if field is not _MISSING:
                fields[name] = VecDBException._redact_value(field)
        if "reason" not in fields:
            fields["reason"] = VecDBException._redact_value(_safe_string(error))
        snapshot = _SanitizedServiceError(type(error).__name__, **fields)
        # Preserve the useful ``isinstance`` compatibility promised by the
        # old public attribute without keeping the original object alive.
        try:
            safe_type = type(
                f"Sanitized{type(error).__name__}",
                (_SanitizedServiceError, type(error)),
                {"__module__": __name__},
            )
            safe_error = cast(Any, safe_type).__new__(safe_type)
            safe_error.__dict__.update(snapshot.__dict__)
            Exception.__init__(safe_error, str(snapshot))
            return safe_error
        except TypeError:
            if type(error).__module__.split(".", 1)[0] == "pydantic_core":
                safe_type = type(
                    "SanitizedValidationError",
                    (_SanitizedServiceError, ValueError),
                    {"__module__": __name__},
                )
                safe_error = cast(Any, safe_type).__new__(safe_type)
                safe_error.__dict__.update(snapshot.__dict__)
                Exception.__init__(safe_error, str(snapshot))
                return safe_error
            return snapshot

    @staticmethod
    def _redact_value(
        value: Any,
        key: str = "",
        _seen: Optional[set[int]] = None,
        _depth: int = 0,
    ) -> Any:
        """Recursively remove secrets from values retained for diagnostics."""
        if _is_sensitive_key(key):
            return _REDACTED
        if _seen is None:
            _seen = set()
        if _depth >= _MAX_DIAGNOSTIC_DEPTH:
            return _NESTED_DIAGNOSTIC_TRUNCATED
        if isinstance(value, Mapping):
            value_id = id(value)
            if value_id in _seen:
                return _CIRCULAR_REFERENCE
            _seen.add(value_id)
            sanitized_mapping: Dict[Any, Any] = {}
            try:
                for item_key, item in value.items():
                    safe_key = (
                        item_key
                        if type(item_key) in (str, int, float, bool)
                        or item_key is None
                        else _safe_string(item_key)
                    )
                    sanitized_mapping[safe_key] = VecDBException._redact_value(
                        item,
                        _safe_string(safe_key),
                        _seen,
                        _depth + 1,
                    )
            except Exception:  # pragma: no cover - hostile mappings
                sanitized_mapping["<unavailable>"] = (
                    "<mapping value unavailable>"
                )
            finally:
                _seen.discard(value_id)
            return sanitized_mapping
        if isinstance(value, (list, tuple)):
            value_id = id(value)
            if value_id in _seen:
                return _CIRCULAR_REFERENCE
            _seen.add(value_id)
            try:
                sanitized_collection = [
                    VecDBException._redact_value(item, "", _seen, _depth + 1)
                    for item in value
                ]
            except Exception:  # pragma: no cover - hostile collections
                sanitized_collection = ["<collection value unavailable>"]
            finally:
                _seen.discard(value_id)
            return (
                tuple(sanitized_collection)
                if isinstance(value, tuple)
                else sanitized_collection
            )
        if isinstance(value, (bytes, bytearray, memoryview)):
            try:
                value = bytes(value).decode("utf-8", errors="replace")
            except Exception:  # pragma: no cover - hostile byte containers
                return "<unreadable bytes>"
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError, RecursionError):
                parsed = None
            if isinstance(parsed, (dict, list)):
                sanitized = VecDBException._redact_value(parsed)
                return VecDBException._safe_json(sanitized)
            return VecDBException._redact_diagnostic_text(value)
        for serializer_name in ("model_dump", "to_dict"):
            serializer = _safe_attribute(value, serializer_name)
            if callable(serializer):
                value_id = id(value)
                if value_id in _seen:
                    return _CIRCULAR_REFERENCE
                _seen.add(value_id)
                serialized = _MISSING
                try:
                    serialized = serializer()
                    if serialized is not _MISSING:
                        return VecDBException._redact_value(
                            serialized, key, _seen, _depth + 1
                        )
                except Exception:  # pragma: no cover - hostile serializers
                    serialized = _MISSING
                finally:
                    _seen.discard(value_id)
        return VecDBException._redact_diagnostic_text(_safe_string(value))

    @staticmethod
    def _sanitize_arguments(arguments: Any) -> Any:
        """Retain only safe resource identifiers in request diagnostics."""
        safe_keys = {
            "name",
            "table_name",
            "model_name",
            "index_name",
            "job_name",
            "comment",
            "annotations",
            "table_params",
            "embed_params",
            "index_params",
            "vector_index_params",
            "debug_flags",
        }
        normalized_safe_keys = {
            _normalized_key(safe_key) for safe_key in safe_keys
        }
        normalized_safe_annotation_keys = {
            _normalized_key(annotation_key)
            for annotation_key in _SAFE_ANNOTATION_KEYS
        }

        def sanitize(
            value: Any, key: str = "", safe_context: bool = False
        ) -> Any:
            key_normalized = _normalized_key(key)
            if _is_sensitive_key(key):
                return _REDACTED
            is_safe_key = safe_context or key_normalized in normalized_safe_keys
            if key_normalized == "annotations":
                # Do not propagate safe_context into arbitrary annotation extensions.
                if value is None:
                    return None
                if not isinstance(value, Mapping):
                    return _REDACTED
                return {
                    item_key: (
                        VecDBException._redact_value(item_value, str(item_key))
                        if isinstance(item_value, (str, int, float, bool))
                        else _REDACTED
                    )
                    for item_key, item_value in value.items()
                    if _normalized_key(item_key)
                    in normalized_safe_annotation_keys
                }
            if isinstance(value, Mapping):
                if not is_safe_key and key_normalized not in {
                    "",
                    "args",
                    "kwargs",
                }:
                    return _REDACTED
                return {
                    item_key: sanitize(item_value, str(item_key), is_safe_key)
                    for item_key, item_value in value.items()
                }
            if isinstance(value, (list, tuple)):
                if not is_safe_key and key_normalized not in {
                    "",
                    "args",
                    "kwargs",
                }:
                    return _REDACTED
                sanitized = [
                    sanitize(item, safe_context=is_safe_key) for item in value
                ]
                return (
                    tuple(sanitized) if isinstance(value, tuple) else sanitized
                )
            if isinstance(value, str) and (
                value.startswith(("http://", "https://")) or "?" in value
            ):
                return "<redacted>"
            # Positional arguments have no reliable semantic key and may be
            # URLs, credentials, or payloads.
            return value if is_safe_key else _REDACTED

        return sanitize(arguments)

    def _customize_error(self) -> None:
        # Generated compatibility constructors may initialize only transport
        # fields before calling this hook. Use setattr/getattr defensively so
        # formatting the original service error can never raise a secondary
        # AttributeError.
        for name, default in (
            ("error_code", None),
            ("error_message", None),
            ("error_type", None),
            ("error_instance", None),
            ("cause", None),
            ("action", None),
            ("diagnostic_trace", None),
            ("stack_trace", None),
        ):
            if not hasattr(self, name):
                setattr(self, name, default)

        payload = self._response_payload(self.body, self.data)

        if isinstance(payload, dict):
            self.error_code = (
                payload.get("code")
                or payload.get("error_code")
                or payload.get("ora_code")
            )
            self.error_message = (
                payload.get("message")
                or payload.get("detail")
                or payload.get("error_description")
            )
            self.error_type = payload.get("type") or self.error_type
            self.error_instance = payload.get("instance") or self.error_instance
            self.diagnostic_trace = self._redact_diagnostic_text(
                payload.get("diagnosticTrace") or self.diagnostic_trace
            )
            self.stack_trace = self._redact_diagnostic_text(
                payload.get("stackTrace") or self.stack_trace
            )

        # Local SDK errors and third-party exceptions may not provide an HTTP
        # body, but they can still expose the same stable fields. Preserve
        # those fields so every wrapped exception has one consistent contract.
        original = self.service_error
        if original is not None:
            self.error_code = self.error_code or getattr(
                original, "error_code", None
            )
            self.error_message = self.error_message or getattr(
                original, "error_message", None
            )
            self.error_type = self.error_type or getattr(
                original, "error_type", None
            )
            self.error_instance = self.error_instance or getattr(
                original, "error_instance", None
            )

        transport_category = getattr(self, "transport_category", None)
        timeout_error = transport_category in _TRANSPORT_TIMEOUT_CATEGORIES
        if transport_category:
            self.error_code = self.error_code or _TRANSPORT_ERROR_CODES.get(
                transport_category
            )
        if timeout_error:
            detail = self._redact_diagnostic_text(
                _safe_string(original)
            ).strip()
            operation = self.operation or "the request"
            self.error_code = self.error_code or "TIMEOUT"
            self.error_message = (
                f"Request timed out while executing '{operation}'. "
                "Increase Configuration.timeout and retry."
            )
            if detail and detail.lower() not in {
                "timeout",
                "timed out",
            }:
                self.error_message += f" Details: {detail}"
        elif transport_category and not self.error_message:
            detail = self._redact_diagnostic_text(
                _safe_string(original)
            ).strip()
            operation = self.operation or "the request"
            category_label = transport_category.replace("_", " ")
            self.error_message = (
                f"Network {category_label} while executing '{operation}'."
            )
            if detail:
                self.error_message += f" Details: {detail}"
        elif not self.error_message:
            self.error_message = _safe_string(
                self.reason or self.body or original or "Request failed"
            ).strip()
        self.error_message = self._redact_diagnostic_text(self.error_message)
        if not self.error_code:
            match = re.search(r"ORA-\d{5}", _safe_string(self.body), re.I)
            self.error_code = match.group(0).upper() if match else None

        status = self.status if self.status is not None else "unknown"
        self.error_code = str(self.error_code or f"HTTP-{status}")
        if timeout_error:
            self.cause = (
                "The configured HTTP request timeout elapsed before the "
                "operation completed."
            )
            self.action = (
                "Increase Configuration.timeout for slow operations, then "
                "retry."
            )
        elif transport_category in _TRANSPORT_GUIDANCE:
            self.cause, self.action = _TRANSPORT_GUIDANCE[transport_category]
        else:
            self.cause, self.action = guidance_for_status(self.status)
        self._has_operation_guidance = False
        if self.operation == "upsert_vectors":
            guidance = self.vector_id_null_guidance(
                self.body,
                self.data,
                self.error_message,
                self.reason,
            )
            if guidance:
                self.cause, self.action = guidance
                self._has_operation_guidance = True
        self._sync_exception_fields()

    @staticmethod
    def vector_id_null_guidance(*details: Any) -> Optional[tuple[str, str]]:
        """Return guidance for an ID-column ORA-01400 failure."""
        text = " ".join(str(value or "") for value in details)
        if not re.search(r"ORA-01400", text, re.IGNORECASE):
            return None
        if not re.search(
            r"cannot\s+insert\s+NULL\s+into\s*\([^)]*\bID\b",
            text,
            re.IGNORECASE,
        ):
            return None
        return _VECTOR_ID_NULL_GUIDANCE, _VECTOR_ID_NULL_ACTION

    def _sync_exception_fields(self) -> None:
        """Expose concrete ORDSErrorResponse field names for diagnostics."""
        self.code = self.error_code
        # ``code`` historically exposed the service payload code. Preserve
        # that behavior for transport errors, but expose the concrete local
        # exception category for normalized validation errors, e.g.
        # ``ValidationError`` or ``ValueError``.
        local_exception_types = {
            "TypeError",
            "ValueError",
            "ValidationError",
        }
        if self.exception_type and (
            self.service_name == "validation"
            or self.exception_type in local_exception_types
        ):
            self.code = self.exception_type
        self.message = self.error_message
        self.type = self.error_type
        self.instance = self.error_instance
        self.diagnosticTrace = self.diagnostic_trace
        self.stackTrace = self.stack_trace
        self.traceback = self.service_trace or ""

    @property
    def vecdb_message(self) -> str:
        return f"VECDB-{getattr(self, 'error_code', 'HTTP-unknown')}: {getattr(self, 'error_message', 'Request failed')}"

    def format(
        self,
        *,
        include_trace: bool = False,
        include_full_ords_response: Optional[bool] = None,
    ) -> str:
        """Format the error with optional service diagnostics.

        ``include_full_ords_response`` overrides the class-level setting for
        one formatting call. When omitted, the class-level setting controls
        whether all fields returned by ORDS are rendered.
        """
        if include_full_ords_response is None:
            include_full_ords_response = bool(
                getattr(self, "include_full_ords_response", False)
            )
        if self.service_error is not None:
            original = self._format_service_error(
                include_full_ords_response=include_full_ords_response
            )
            message = (
                f"\nOperation - {self.operation}\n"
                f"Request Data/Parameters - {self.arguments}\n"
                f"Exception from {self.service_name} -\n"
                f"{original}"
            )
            if include_trace and self.service_trace:
                message += f"\nTraceback:\n{self.get_traceback()}"
            if include_trace and self.diagnostic_trace:
                message += (
                    "\nDiagnostic trace:\n"
                    f"{self._redact_diagnostic_text(self.diagnostic_trace)}"
                )
            if include_trace and self.stack_trace:
                message += (
                    "\nService stack trace:\n"
                    f"{self._redact_diagnostic_text(self.stack_trace)}"
                )
            if getattr(self, "_has_operation_guidance", False):
                message += f"\nCause: {self.cause}\nAction: {self.action}"
            return self._redact_diagnostic_text(message)

        message = f"({getattr(self, 'status', None)}) {self.vecdb_message}"
        if getattr(self, "cause", None):
            message += f"\nCause: {self.cause}"
        if getattr(self, "action", None):
            message += f"\nAction: {self.action}"
        return self._redact_diagnostic_text(message)

    def _format_service_error(
        self, *, include_full_ords_response: bool = False
    ) -> str:
        """Render the original ORDS error once, without generated duplication."""
        error = self.service_error
        name = self.service_error_class_name or _safe_string(
            type(error).__name__
        )
        status = _safe_attribute(error, "status")
        body = _safe_attribute(error, "body")
        data = _safe_attribute(error, "data")
        reason = _safe_attribute(error, "reason")
        message = f"{name}: ({_safe_string(status)})"
        if self.error_code == "TIMEOUT":
            return f"{name}: client-side request timeout\nReason: {self.error_message}"
        if type(error).__module__.split(".", 1)[0] == "pydantic_core":
            errors = getattr(error, "errors", None)
            if callable(errors):
                formatted_validation_details = None
                try:
                    safe_errors = [
                        {
                            field: issue[field]
                            for field in ("loc", "msg", "type")
                            if field in issue
                        }
                        for issue in errors()
                    ]
                    formatted_validation_details = self._safe_json(
                        {
                            "title": _safe_attribute(error, "title", name),
                            "errors": safe_errors,
                        },
                        indent=4,
                    )
                except Exception:
                    formatted_validation_details = None
                if formatted_validation_details is not None:
                    return message + "\n" + formatted_validation_details
        payload = self._response_payload(body, data)
        if include_full_ords_response and isinstance(payload, dict):
            return (
                message
                + "\n"
                + self._safe_json(self._redact_value(payload), indent=4)
            )

        response_message = (
            payload.get("message") if isinstance(payload, dict) else None
        )
        # A test harness may serialize a previous VecDBException into the
        # response payload. That nested diagnostic is not an ORDS response
        # message and must not replace the original service details.
        if isinstance(response_message, str) and (
            response_message.startswith("Operation -")
            or response_message.startswith("VecDB integration test data:")
        ):
            response_message = None
        if response_message:
            # Keep only the SDK's stable response fields and preserve
            # service-specific fields (for example ``o:errorCode`` or
            # ``action``) without maintaining a growing allowlist. ``type``
            # and ``title`` are known ORDS fields but are intentionally not
            # repeated in the concise VecDB response body.
            static_fields = {
                "code",
                "message",
                "type",
                "instance",
                "title",
                "detail",
                "diagnosticTrace",
                "stackTrace",
            }
            response_body: Dict[str, Any] = {}
            for field in ("code", "message"):
                if field == "message":
                    response_body[field] = response_message
                elif payload.get(field) is not None:
                    response_body[field] = payload[field]
            response_body.update(
                {
                    field: value
                    for field, value in payload.items()
                    if field not in static_fields
                }
            )
            if payload.get("instance") is not None:
                response_body["instance"] = payload["instance"]
            message += "\n" + self._safe_json(response_body, indent=4)
        elif reason:
            message += f"\nReason: {_safe_string(reason)}"
        else:
            details = _safe_string(error)
            if error is not None and not details and error.args:
                details = " ".join(_safe_string(value) for value in error.args)
            if details:
                message += f"\n{details}"
        return message

    @staticmethod
    def _safe_json_default(value: Any) -> str:
        """Convert an unsupported JSON value without raising while logging."""
        return VecDBException._redact_diagnostic_text(_safe_string(value))

    @staticmethod
    def _safe_json(value: Any, *, indent: Optional[int] = None) -> str:
        """Serialize diagnostics with a final non-throwing text fallback."""
        try:
            return json.dumps(
                value,
                indent=indent,
                default=VecDBException._safe_json_default,
            )
        except Exception:  # pragma: no cover - defensive final fallback
            return VecDBException._redact_diagnostic_text(_safe_string(value))

    @staticmethod
    def _response_payload(body: Any, data: Any) -> Any:
        for candidate in (body, data):
            payload = candidate
            if isinstance(payload, (bytes, bytearray, memoryview)):
                decoded_payload = _MISSING
                try:
                    decoded_payload = bytes(payload).decode(
                        "utf-8", errors="replace"
                    )
                except Exception:  # pragma: no cover - hostile byte containers
                    decoded_payload = _MISSING
                payload = decoded_payload
            if payload is not _MISSING and isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (TypeError, ValueError, RecursionError):
                    payload = _MISSING
            if payload is not _MISSING and not isinstance(payload, Mapping):
                for method in ("model_dump", "to_dict"):
                    serializer = _safe_attribute(payload, method)
                    if callable(serializer):
                        serialized_payload = _MISSING
                        try:
                            serialized_payload = serializer()
                        except (
                            Exception
                        ):  # pragma: no cover - hostile serializers
                            serialized_payload = _MISSING
                        if isinstance(serialized_payload, Mapping):
                            payload = serialized_payload
                            break
            if payload is not _MISSING and isinstance(payload, Mapping):
                return VecDBException._redact_value(payload)
        return None

    def get_traceback(self) -> str:
        """Return a redacted service traceback for explicit diagnostics."""
        return self._redact_diagnostic_text(self.service_trace) or ""

    @staticmethod
    def _redact_diagnostic_text(value: Any) -> Any:
        """Redact credentials from text intended for diagnostics or logs."""
        if not isinstance(value, str):
            return value

        redacted = re.sub(r"(?i)(bearer\s+)[^\s\"',]+", r"\1<redacted>", value)
        redacted = re.sub(
            r"(?i)((?:proxy-)?authorization\s*=\s*(?:basic|bearer)\s+)"
            r"[^\s\"',]+",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)((?:proxy-)?authorization\s*:\s*(?:basic|bearer)\s+)"
            r"[^\s\"',]+",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)((?:x[-_])?api[-_]?key\s*:\s*)[^\s\"',]+",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)((?:set-)?cookie\s*:\s*)[^\s;,\"']+",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([\"'](?:(?:proxy-)?authorization|(?:set-)?cookie|"
            r"(?:x[-_])?api[-_]?key)[\"']\s*:\s*[\"'])[^\"']*",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([?&](?:access[_-]?token|token|secret|signature|"
            r"credential|password|api[_-]?key|x-amz-signature|"
            r"x-amz-credential)=)"
            r"[^&#\s\"']+",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([\"'](?:access[_-]?token|token|secret|signature|"
            r"credential|password|(?:proxy-)?authorization|(?:set-)?cookie|"
            r"(?:x[-_])?api[-_]?key)[\"']\s*:\s*[\"'])[^\"']*",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([\"']?(?:password|passwd|pwd|secret|token|credential|"
            r"username|auth|api[-_]?key)[\"']?"
            r"\s*[:=]\s*[\"']?)[^\s,;\"'}]+",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(input_value\s*=\s*)(?:'[^']*'|\"[^\"]*\"|[^,\]\n]+)",
            r"\1<redacted>",
            redacted,
        )
        redacted = re.sub(
            r"(?i)([\"'](?:password|passwd|pwd|secret|token|credential|"
            r"authorization|proxy[-_]authorization|cookie|set[-_]cookie|"
            r"(?:x[-_])?api[-_]?key|username|database|database[-_]name|"
            r"schema|schema[-_]name|connection|connection[-_]string|dsn|"
            r"sql|query|query[-_]by|filter|filters|document|documents|"
            r"metadata|payload|vector|vectors|embedding|embeddings|url)"
            r"[\"']\s*:\s*)([\"'])[^\"']*\2",
            r"\1\2<redacted>\2",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(\b(?:database|database[-_]name|schema|schema[-_]name|"
            r"connection[-_]string|dsn)\s*[:=]\s*[\"']?)[^\s,;\"']+",
            r"\1<redacted>",
            redacted,
        )

        def redact_raw_key_value(match: re.Match[str]) -> str:
            key = match.group("key")
            raw_value = (
                match.group("quoted_value") or match.group("bare_value") or ""
            )
            if _normalized_key(key) in {
                "authorization",
                "proxy_authorization",
            } and raw_value.lower() in {"basic", "bearer"}:
                return match.group(0)
            if not _is_sensitive_key(key):
                return match.group(0)
            value_quote = match.group("value_quote") or ""
            return (
                f"{match.group('key_prefix')}{key}{match.group('key_suffix')}"
                f"{match.group('before_separator')}{match.group('separator')}"
                f"{match.group('after_separator')}{value_quote}"
                f"{_REDACTED}{value_quote}"
            )

        redacted = _RAW_KEY_VALUE_PATTERN.sub(redact_raw_key_value, redacted)
        # Unstructured transport errors have no field name to guide the
        # recursive redactor. Remove opaque values that explicitly identify
        # themselves as secrets, while preserving ordinary diagnostics such
        # as request IDs, ORA codes, and connection failures.
        redacted = re.sub(
            r"(?i)\b(?:(?:[a-z0-9.-]+[_-])?(?:secret|password|passwd|"
            r"credential|api[-_]?key)[_-][a-z0-9.-]+|"
            r"(?:[a-z0-9.-]+[_-])token(?:[_-][a-z0-9.-]+)?|"
            r"token[_-][a-z0-9.-]+)\b",
            "<redacted>",
            redacted,
        )
        return redacted

    def is_original_exception(
        self, exception_type: type[BaseException]
    ) -> bool:
        """Return whether the wrapped exception is an instance of ``exception_type``."""
        return self.original_exception_type is not None and issubclass(
            self.original_exception_type, exception_type
        )

    def __str__(self) -> str:
        return self.format()


def guidance_for_status(status: Any) -> tuple[str, str]:
    """Return service-neutral cause/action guidance for an HTTP status."""
    guidance = {
        400: (
            "The request violates the VecDB API schema or database rules.",
            "Check arguments, resource names, dimensions, filters, and parameters.",
        ),
        401: (
            "The service rejected the credentials.",
            "Refresh the bearer token or verify the configured username and password.",
        ),
        403: (
            "The principal is not authorized for this operation.",
            "Verify schema privileges and access to the requested resource.",
        ),
        404: (
            "The requested resource or service route was not found.",
            "Verify the endpoint and table, model, index, or job name.",
        ),
        409: (
            "The request conflicts with the current resource or job state.",
            "Inspect the existing resource or job before retrying.",
        ),
        422: (
            "The service could not process the supplied entity.",
            "Validate the request against the SDK/OpenAPI field constraints.",
        ),
        429: (
            "The service rate-limited the request.",
            "Wait and retry using the configured retry policy.",
        ),
    }
    try:
        numeric_status = int(status)
    except (TypeError, ValueError):
        return (
            "The service returned an unclassified error.",
            "Inspect the endpoint and response, then retry if appropriate.",
        )
    if numeric_status in guidance:
        return guidance[numeric_status]
    if 500 <= numeric_status <= 599:
        return (
            "The service or database failed while processing the request.",
            "Retry transient failures; provide the VecDB error code if the problem persists.",
        )
    return (
        "The service returned an unexpected HTTP status.",
        "Check the endpoint and response before retrying.",
    )


__all__ = ["VecDBException", "guidance_for_status"]
