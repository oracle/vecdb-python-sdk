import json
from types import SimpleNamespace

import pytest
from oracle_vecdb import VecDBException
from oracle_vecdb.services.ords.exceptions import ApiException
from oracle_vecdb.vecdb_exception import guidance_for_status


class ServiceError(Exception):
    """Generic transport error fixture; tests must not depend on ORDS classes."""

    def __init__(
        self, status=None, reason=None, body=None, data=None, headers=None
    ):
        self.status = status
        self.reason = reason
        self.body = body
        self.data = data
        self.headers = headers


def _response(status, reason="Not Found"):
    return SimpleNamespace(
        status=status,
        reason=reason,
        data=b'{"code":"TABLE_NOT_FOUND","message":"Table DOCS does not exist",'
        b'"type":"tag:oracle.com,2020:error/NotFound"}',
        headers={"Content-Type": "application/problem+json"},
    )


def test_service_error_wrapper_preserves_ords_details():
    original = ServiceError(
        status=404,
        reason="Not Found",
        body='{"code":"NotFound","message":"Table missing",'
        '"type":"tag:oracle.com,2020:error/NotFound",'
        '"instance":"tag:oracle.com,2020:ecid/test",'
        '"diagnosticTrace":"diag",'
        '"stackTrace":"stack"}',
    )
    error = VecDBException.from_service_error(
        "describe_vector_table",
        {"kwargs": {"name": "DOCS"}},
        "ORDSService",
        original,
    )

    assert "Operation - describe_vector_table" in str(error)  # nosec B101
    assert "Request Data/Parameters - {'kwargs': {'name': 'DOCS'}}" in str(
        error
    )  # nosec B101
    assert "Exception from ORDSService -" in str(error)  # nosec B101
    assert "ServiceError: (404)" in str(error)  # nosec B101
    assert 'ServiceError: (404)\n{\n    "code": "NotFound",' in str(
        error
    )  # nosec B101
    assert '"message": "Table missing"' in str(error)  # nosec B101
    assert error.status == 404  # nosec B101
    assert error.code == "NotFound"  # nosec B101
    assert error.message == "Table missing"  # nosec B101
    assert error.type == "tag:oracle.com,2020:error/NotFound"  # nosec B101
    assert error.instance == "tag:oracle.com,2020:ecid/test"  # nosec B101
    assert error.traceback  # nosec B101
    serialized = vars(error)
    assert serialized["status"] == 404  # nosec B101
    assert serialized["code"] == "NotFound"  # nosec B101
    assert serialized["message"] == "Table missing"  # nosec B101
    assert (
        serialized["type"] == "tag:oracle.com,2020:error/NotFound"
    )  # nosec B101
    assert (
        serialized["instance"] == "tag:oracle.com,2020:ecid/test"
    )  # nosec B101
    assert serialized["diagnosticTrace"] == "diag"  # nosec B101
    assert serialized["stackTrace"] == "stack"  # nosec B101
    assert serialized["traceback"]  # nosec B101
    assert '"diagnosticTrace"' not in str(error)  # nosec B101
    assert "Reason: Not Found" not in str(error)  # nosec B101
    assert "Traceback" not in str(error)  # nosec B101
    assert "Traceback" in error.format(include_trace=True)  # nosec B101
    assert "Diagnostic trace:\ndiag" in error.format(
        include_trace=True
    )  # nosec B101
    assert "Service stack trace:\nstack" in error.format(
        include_trace=True
    )  # nosec B101
    assert error.get_traceback()  # nosec B101


def test_service_error_uses_captured_original_class_name():
    error = VecDBException.from_service_error(
        "operation",
        {},
        "OtherService",
        ServiceError(
            status=404,
            reason="Not Found",
            body='{"code":"OTHER","message":"Other failure"}',
        ),
    )

    assert "ServiceError: (404)" in str(error)  # nosec B101
    assert '"message": "Other failure"' in str(error)  # nosec B101


@pytest.mark.parametrize(
    "canary",
    [
        "Authorization: Basic dXNlcjpwYXNz",
        "Authorization: Bearer demo-do-not-log",
        "Proxy-Authorization: Basic cHJveHk6cGFzcw==",
        "Cookie: session=do-not-log",
        "Set-Cookie: session=do-not-log; HttpOnly",
        "X-API-Key: demo-do-not-log",
    ],
)
@pytest.mark.parametrize("json_payload", [False, True])
def test_service_exception_traceback_redacts_credentials_for_logging(
    canary, json_payload
):
    body = (
        json.dumps(
            {
                "code": "AUTH_FAILURE",
                "message": canary,
                "diagnosticTrace": canary,
                "stackTrace": canary,
            }
        )
        if json_payload
        else canary
    )
    original = ApiException(status=401, reason=canary, body=body)
    header_name, header_value = canary.split(": ", 1)
    original.headers = {header_name: header_value}
    error = VecDBException.from_service_error(
        "query",
        {},
        "ORDSService",
        original,
    )

    # This is the supported value for explicit diagnostic logging.
    assert canary not in error.message  # nosec B101
    assert header_value not in error.get_traceback()  # nosec B101
    assert canary not in error.get_traceback()  # nosec B101
    assert "<redacted>" in error.get_traceback()  # nosec B101
    assert canary not in error.format(include_trace=True)  # nosec B101


def test_service_error_preserves_dynamic_ords_response_fields():
    error = VecDBException.from_service_error(
        "create_vector_table",
        {"kwargs": {"name": "DOCS"}},
        "ORDSService",
        ServiceError(
            status=400,
            reason="Bad Request",
            body='{"code":"UserDefinedResourceError",'
            '"title":"User Defined Resource Error",'
            '"message":"The request could not be processed",'
            '"o:errorCode":"ORDS-25001",'
            '"action":"Verify the URI and payload",'
            '"type":"tag:oracle.com,2020:error/UserDefinedResourceError",'
            '"instance":"tag:oracle.com,2020:ecid/test"}',
        ),
    )

    rendered = str(error)
    assert '"code": "UserDefinedResourceError"' in rendered  # nosec B101
    assert (
        '"title": "User Defined Resource Error"' not in rendered
    )  # nosec B101
    assert '"o:errorCode": "ORDS-25001"' in rendered  # nosec B101
    assert '"action": "Verify the URI and payload"' in rendered  # nosec B101
    assert (
        '"type": "tag:oracle.com,2020:error/UserDefinedResourceError"'
        not in rendered
    )  # nosec B101
    assert (
        '"instance": "tag:oracle.com,2020:ecid/test"' in rendered
    )  # nosec B101


def test_service_error_wrapper_omits_vectors_from_arguments():
    error = VecDBException.from_service_error(
        "upsert_vectors",
        {"kwargs": {"vectors": [{"dense_vector": [1.0] * 1000}]}},
        "ORDSService",
        ServiceError(status=404, reason="Not Found"),
    )

    assert "<redacted>" in str(error)  # nosec B101
    assert "1.0" not in str(error)  # nosec B101


def test_service_error_redacts_signed_urls_and_credentials():
    error = VecDBException.from_service_error(
        "load_vectors",
        {
            "args": (
                "DOCS",
                "https://object.example/export.json?X-Auth-Token=demo-redaction-secret",
            ),
            "kwargs": {
                "table_name": "DOCS",
                "url": "https://object.example/input.json?signature=secret",
                "params": {"credential": "credential-secret"},
                "headers": {"Authorization": "Bearer bearer-secret"},
            },
        },
        "ORDSService",
        ServiceError(status=404, reason="Not Found"),
    )

    rendered = str(error)
    assert "demo-redaction-secret" not in rendered  # nosec B101
    assert "credential-secret" not in rendered  # nosec B101
    assert "bearer-secret" not in rendered  # nosec B101
    assert "DOCS" in rendered  # nosec B101


def test_service_error_redacts_search_text_and_renders_safe_arguments():
    error = VecDBException.from_service_error(
        "query",
        {
            "args": (),
            "kwargs": {
                "table_name": "DOCS",
                "query_by": {"text": "LEAKS_CANARY"},
                "query": "LEAKS_CANARY",
                "comment": "Safe table description",
                "annotations": {
                    "tier": "gold",
                    "token": "ANNOTATION_SECRET",  # nosec B105
                },
                "table_params": {"auto_generate_id": True},
            },
        },
        "ORDSService",
        ServiceError(status=404, reason="Not Found"),
    )

    rendered = str(error)
    assert "LEAKS_CANARY" not in rendered  # nosec B101
    assert "table_name': 'DOCS'" in rendered  # nosec B101
    assert "query_by': '<redacted>'" in rendered  # nosec B101
    assert "query': '<redacted>'" in rendered  # nosec B101
    assert "comment': 'Safe table description'" in rendered  # nosec B101
    assert "'tier': 'gold'" in rendered  # nosec B101
    assert "'auto_generate_id': True" in rendered  # nosec B101
    assert "ANNOTATION_SECRET" not in rendered  # nosec B101


def test_generic_vecdb_exception_can_be_reused_by_another_service():
    error = VecDBException(
        status=422,
        data={
            "code": "INVALID_VECTOR",
            "detail": "Vector dimension is invalid",
        },
    )

    assert error.error_code == "INVALID_VECTOR"  # nosec B101
    assert "VECDB-INVALID_VECTOR" in str(error)  # nosec B101
    assert "OpenAPI field constraints" in str(error)  # nosec B101


def test_exception_handles_non_json_response_and_status_guidance():
    error = VecDBException(status="unknown", body="not-json")

    assert "unclassified error" in str(error)  # nosec B101
    assert guidance_for_status(200)[0].startswith(
        "The service returned"
    )  # nosec B101
    assert guidance_for_status(None)[0].startswith(
        "The service returned"
    )  # nosec B101


def test_exception_response_payload_supports_bytes_and_invalid_text():
    assert VecDBException._response_payload(  # nosec B101
        b'{"message":"decoded"}', None
    ) == {"message": "decoded"}
    assert (
        VecDBException._response_payload("not-json", None) is None
    )  # nosec B101


def test_not_found_payload_without_code_is_stable():
    error = VecDBException.from_service_error(
        "drop_vector_table",
        {},
        "ORDSService",
        ServiceError(
            status=404,
            reason="Not Found",
            body='{"message":"ORA-00942: table or view does not exist"}',
        ),
    )

    assert '"code": null' not in str(error)  # nosec B101
    assert '"message": "ORA-00942: table or view does not exist"' in str(
        error
    )  # nosec B101


def test_protocol_error_preserves_original_details():
    class ProtocolError(Exception):
        pass

    error = VecDBException.from_service_error(
        "upsert_vectors",
        {},
        "ORDSService",
        ProtocolError("connection reset by peer"),
    )

    assert "ProtocolError: (None)" in str(error)  # nosec B101
    assert "connection reset by peer" in str(error)  # nosec B101


def test_nested_harness_context_does_not_replace_not_found_message():
    error = VecDBException.from_service_error(
        "drop_vector_table",
        {},
        "ORDSService",
        ServiceError(
            status=404,
            reason="Not Found",
            body='{"code":"NotFound","message":"Operation - nested",'
            '"type":"tag:oracle.com,error","instance":"test"}',
        ),
    )

    assert "Operation - nested" not in str(error)  # nosec B101
    assert "Reason: Not Found" in str(error)  # nosec B101


def test_bad_request_preserves_ora_20000_prefix():
    error = VecDBException.from_service_error(
        "load_model",
        {},
        "ORDSService",
        ServiceError(
            status=400,
            reason="Bad Request",
            body='{"code":"BadRequest","message":"An unexpected error '
            "with the following message occurred: ORA-20000: ORA-65114: "
            'space usage in container is too high",'
            '"type":"tag:oracle.com,error","instance":"test"}',
        ),
    )

    assert "ORA-20000: ORA-65114" in str(error)  # nosec B101


def test_exception_reinitializes_missing_compatibility_fields():
    error = VecDBException(status=400, reason="bad request")
    del error.error_code

    error._customize_error()

    assert error.error_code == "HTTP-400"  # nosec B101


def test_wrapped_exception_exposes_standard_attributes_for_all_error_shapes():
    class LocalError(Exception):
        def __init__(self):
            self.error_code = "LOCAL-001"
            self.error_message = "Local validation failed"
            super().__init__(self.error_message)

    error = VecDBException.from_service_error(
        "validate", {"kwargs": {"name": "bad"}}, "validation", LocalError()
    )

    for attribute in (
        "status",
        "reason",
        "body",
        "data",
        "headers",
        "operation",
        "arguments",
        "service_name",
        "error_code",
        "error_message",
        "error_type",
        "error_instance",
        "cause",
        "action",
        "original_exception",
        "original_exception_type",
        "original_exception_type_name",
        "exception_type",
        "service_trace",
        "diagnostic_trace",
        "stack_trace",
        "code",
        "message",
        "type",
        "instance",
        "traceback",
    ):
        assert hasattr(error, attribute), attribute  # nosec B101

    assert error.error_code == "LOCAL-001"  # nosec B101
    assert error.error_message == "Local validation failed"  # nosec B101
    assert error.code == "LocalError"  # nosec B101
    assert error.exception_type == "LocalError"  # nosec B101
    assert error.original_exception_type is LocalError  # nosec B101
