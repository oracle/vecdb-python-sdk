"""Service-independent VecDB exception normalization.

Service adapters should inherit :class:`VecDBException` so generated
transport exceptions expose the same structured diagnostics regardless of the
underlying protocol or service implementation.
"""

from __future__ import annotations

import json
import re
import traceback
from typing import Any, Dict, Optional


class VecDBException(Exception):
    """Base exception with normalized service error details."""

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
        self.reason = reason
        self.body = body
        self.data = data
        self.headers = headers
        self.operation = operation
        self.arguments = arguments
        self.service_name = service_name
        self.service_error = service_error
        self.service_error_class_name = service_error_class_name
        self.original_exception = service_error
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
            "status": getattr(error, "status", None),
            "reason": getattr(error, "reason", None),
            "body": getattr(error, "body", None),
            "data": getattr(error, "data", None),
            "headers": getattr(error, "headers", None),
            "operation": operation,
            "arguments": cls._sanitize_arguments(arguments),
            "service_name": service_name,
            "service_error": error,
            "service_error_class_name": type(error).__name__,
            "service_trace": "".join(
                traceback.format_exception(
                    type(error), error, error.__traceback__
                )
            ),
        }
        try:
            return wrapper_type(**values)
        except TypeError:
            # Some third-party validation exceptions cannot be subclassed or
            # constructed with normal Exception arguments. The ORDS adapter
            # normally excludes those before calling this method, but retain
            # a safe fallback for other service adapters.
            return cls(**values)

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
        sensitive_keys = (
            "auth",
            "credential",
            "document",
            "filter",
            "header",
            "metadata",
            "password",
            "payload",
            "secret",
            "token",
            "url",
            "vector",
        )

        def sanitize(
            value: Any, key: str = "", safe_context: bool = False
        ) -> Any:
            key_lower = key.lower()
            if any(term in key_lower for term in sensitive_keys):
                return "<redacted>"
            is_safe_key = safe_context or key_lower in safe_keys
            if isinstance(value, dict):
                if not is_safe_key and key_lower not in {"", "args", "kwargs"}:
                    return "<redacted>"
                return {
                    item_key: sanitize(item_value, str(item_key), is_safe_key)
                    for item_key, item_value in value.items()
                }
            if isinstance(value, (list, tuple)):
                if not is_safe_key and key_lower not in {"", "args", "kwargs"}:
                    return "<redacted>"
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
            return value if is_safe_key else "<redacted>"

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

        if not self.error_message:
            self.error_message = str(
                self.reason or self.body or original or "Request failed"
            ).strip()
        self.error_message = self._redact_diagnostic_text(self.error_message)
        if not self.error_code:
            match = re.search(r"ORA-\d{5}", str(self.body or ""), re.I)
            self.error_code = match.group(0).upper() if match else None

        status = self.status if self.status is not None else "unknown"
        self.error_code = str(self.error_code or f"HTTP-{status}")
        self.cause, self.action = guidance_for_status(self.status)
        self._sync_exception_fields()

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

    def format(self, *, include_trace: bool = False) -> str:
        """Format the error; include the traceback only when requested."""
        if self.service_error is not None:
            original = self._format_service_error()
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
            return self._redact_diagnostic_text(message)

        message = f"({getattr(self, 'status', None)}) {self.vecdb_message}"
        if getattr(self, "cause", None):
            message += f"\nCause: {self.cause}"
        if getattr(self, "action", None):
            message += f"\nAction: {self.action}"
        return self._redact_diagnostic_text(message)

    def _format_service_error(self) -> str:
        """Render the original ORDS error once, without generated duplication."""
        error = self.service_error
        name = self.service_error_class_name or type(error).__name__
        status = getattr(error, "status", None)
        body = getattr(error, "body", None)
        data = getattr(error, "data", None)
        reason = getattr(error, "reason", None)
        message = f"{name}: ({status})"
        if type(error).__module__.split(".", 1)[0] == "pydantic_core":
            errors = getattr(error, "errors", None)
            if callable(errors):
                try:
                    safe_errors = [
                        {
                            field: issue[field]
                            for field in ("loc", "msg", "type")
                            if field in issue
                        }
                        for issue in errors()
                    ]
                    return (
                        message
                        + "\n"
                        + json.dumps(
                            {
                                "title": getattr(error, "title", name),
                                "errors": safe_errors,
                            },
                            indent=4,
                            default=str,
                        )
                    )
                except (TypeError, ValueError):
                    # Fall through to the generic formatter if a third-party
                    # validation error exposes an incompatible errors() API.
                    pass
        payload = self._response_payload(body, data)
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
            message += "\n" + json.dumps(response_body, indent=4)
        elif reason:
            message += f"\nReason: {reason}"
        else:
            details = str(error)
            if error is not None and not details and error.args:
                details = " ".join(str(value) for value in error.args)
            if details:
                message += f"\n{details}"
        return message

    @staticmethod
    def _response_payload(body: Any, data: Any) -> Any:
        for candidate in (body, data):
            payload = candidate
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8", errors="replace")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (TypeError, ValueError):
                    continue
            if not isinstance(payload, dict):
                for method in ("model_dump", "to_dict"):
                    serializer = getattr(payload, method, None)
                    if callable(serializer):
                        payload = serializer()
                        break
            if isinstance(payload, dict):
                return payload
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
            r"credential|password|x-amz-signature|x-amz-credential)=)"
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
        return redacted

    def is_original_exception(
        self, exception_type: type[BaseException]
    ) -> bool:
        """Return whether the wrapped exception is an instance of ``exception_type``."""
        return isinstance(self.original_exception, exception_type)

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
