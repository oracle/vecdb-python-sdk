"""Environment-controlled SDK logging, privacy and outcome regression tests."""

from contextlib import contextmanager
import http.client
import importlib
import inspect
import json
import logging
import os
import subprocess  # nosec B404 - fixed local Python test probes
import sys

import pytest
import urllib3

import oracle_vecdb
from oracle_vecdb import Configuration, OracleVecDB
import oracle_vecdb.client as client_module
import oracle_vecdb._logging as sdk_logging
from oracle_vecdb.data_types import QueryResponse, UpsertVectorsResponse
from oracle_vecdb.ords_response_handlers import ORDSResponseHandler
from oracle_vecdb.services.ords.rest import RESTResponse
from oracle_vecdb.vecdb_exception import VecDBException

URL = "https://example.invalid/ords/example/_/db-api/stable/vecdb/"


@pytest.fixture(autouse=True)
def clean_logging_environment(monkeypatch):
    for name in (
        "VECDB_DEBUG",
        "VECDB_REST_URL",
        "VECDB_USERNAME",
        "VECDB_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sdk_logging, "_TRACE_ENABLED", False)


@pytest.fixture
def trace_mode(monkeypatch):
    @contextmanager
    def enable():
        logger = logging.getLogger("oracle_vecdb")
        with monkeypatch.context() as patch:
            patch.setattr(logger, "level", logger.level)
            patch.setattr(logger, "handlers", logger.handlers[:])
            patch.setattr(
                sdk_logging, "_TRACE_ENABLED", sdk_logging._TRACE_ENABLED
            )
            patch.setenv("VECDB_DEBUG", "TRACE")
            sdk_logging._configure_logging()
            yield

    return enable


@pytest.fixture
def client(mocker):
    value = OracleVecDB(Configuration(rest_url=URL))
    service = mocker.Mock()
    service.describe_vector_database.return_value = object()
    service.query.return_value = QueryResponse(items=[])
    service.upsert_vectors.return_value = UpsertVectorsResponse(
        upserted_count=1
    )
    value._ords_service = service
    return value


def events(caplog, event=None):
    return [
        r.vecdb
        for r in caplog.records
        if hasattr(r, "vecdb") and (event is None or r.vecdb["event"] == event)
    ]


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, []),
        ("", []),
        ("OFF", []),
        ("0", []),
        ("1", ["INFO", "ERROR"]),
        ("DEBUG", ["INFO", "ERROR"]),
        ("TRACE", ["DEBUG", "INFO", "DEBUG", "ERROR"]),
        ("INFO", ["INFO", "ERROR"]),
        ("WARNING", ["ERROR"]),
        ("ERROR", ["ERROR"]),
        ("CRITICAL", []),
    ],
)
@pytest.mark.parametrize(
    "application_handler",
    ["none", "root_before", "root_after", "package_after"],
)
def test_environment_only_output_in_fresh_process(
    value, expected, application_handler
):
    # A fresh import exercises real logger setup, without pytest capture/handlers.
    probe = r"""
import http.client
import importlib
import logging
import sys
from types import SimpleNamespace
import urllib3
before = [(logging.getLogger(n).level, list(logging.getLogger(n).handlers))
          for n in ("", "urllib3", "http.client")]
wire = http.client.HTTPConnection.debuglevel
if sys.argv[1] == "root_before":
    logging.basicConfig(format="%(levelname)s %(message)s")
    before[0] = (logging.getLogger().level, list(logging.getLogger().handlers))
import oracle_vecdb
importlib.reload(oracle_vecdb)
if sys.argv[1] == "root_after":
    logging.basicConfig(format="%(levelname)s %(message)s")
    before[0] = (logging.getLogger().level, list(logging.getLogger().handlers))
if sys.argv[1] == "package_after":
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logging.getLogger("oracle_vecdb").addHandler(handler)
    logging.getLogger("oracle_vecdb").propagate = False
from oracle_vecdb import Configuration, OracleVecDB
client = OracleVecDB(Configuration(rest_url="https://example.invalid/ords/example/_/db-api/stable/vecdb/", access_token="private-token"))
client._ords_service = SimpleNamespace(describe_vector_database=lambda: object())
client.describe_vector_database()
def fail():
    raise ValueError("private-business-error")
client._ords_service.describe_vector_database = fail
try:
    client.describe_vector_database()
except ValueError:
    pass
assert before == [(logging.getLogger(n).level, list(logging.getLogger(n).handlers))
                  for n in ("", "urllib3", "http.client")]
assert http.client.HTTPConnection.debuglevel == wire
"""
    env = dict(os.environ)
    env.pop("VECDB_DEBUG", None)
    if value is not None:
        env["VECDB_DEBUG"] = value
    result = subprocess.run(  # nosec B603 - fixed local interpreter and probe
        [sys.executable, "-c", probe, str(application_handler)],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stderr.splitlines()
    # An application handler can capture failures even without the env switch.
    if application_handler != "none" and value in (None, ""):
        expected = ["ERROR"]
    assert [line.split()[0] for line in lines] == expected  # nosec B101
    assert "private" not in result.stderr  # nosec B101
    assert result.stdout == ""  # nosec B101


def test_one_terminal_per_call_including_lazy_and_validation_errors(
    client, caplog, mocker
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    client.describe_vector_database()
    with pytest.raises(Exception):
        client.query("TEST_TABLE", query_by={"text": "private"}, top_k=0)
    client._ords_service = None
    original = RuntimeError("private initialization failure")
    mocker.patch.object(
        client_module, "create_ords_service", side_effect=original
    )
    with pytest.raises(RuntimeError) as raised:
        client.describe_vector_database()
    assert raised.value is original  # nosec B101
    completed = events(caplog, "operation.completed")
    assert [e["outcome"] for e in completed] == [
        "success",
        "error",
        "error",
    ]  # nosec B101
    assert len({e["operation_id"] for e in completed}) == 3  # nosec B101
    assert sdk_logging._CURRENT_OPERATION.get() is None  # nosec B101
    assert "private" not in caplog.text  # nosec B101


def test_public_decorator_coverage_and_signatures():
    methods = [
        (name, method)
        for name, method in vars(OracleVecDB).items()
        if not name.startswith("_")
        and callable(method)
        and hasattr(method, "__wrapped__")
    ]
    assert len(methods) == 27  # nosec B101
    for name, method in methods:
        assert method.__module__ == "oracle_vecdb.client"  # nosec B101
        assert method.__name__ == name  # nosec B101
        assert inspect.signature(method) == inspect.signature(
            method.__wrapped__
        )  # nosec B101
        assert method.__doc__ == method.__wrapped__.__doc__  # nosec B101


def test_cancellation_context_cleanup(client, caplog):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    original = KeyboardInterrupt()
    client._ords_service.describe_vector_database.side_effect = original
    with pytest.raises(KeyboardInterrupt) as raised:
        client.describe_vector_database()
    assert raised.value is original  # nosec B101
    assert (
        events(caplog, "operation.completed")[0]["outcome"] == "cancelled"
    )  # nosec B101
    assert sdk_logging._CURRENT_OPERATION.get() is None  # nosec B101


def test_safe_fields_do_not_evaluate_objects_or_export_payloads(client, caplog):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")

    class Hostile:
        def __str__(self):
            pytest.fail("unsafe string conversion")

        __repr__ = __str__

    def emit():
        sdk_logging._log_event(
            "phase.completed",
            "ords",
            logging.DEBUG,
            phase="deserialize",
            outcome="success",
            elapsed_ms=Hostile(),
            error_code=Hostile(),
            query=Hostile(),
            result_count=True,
            client_id=Hostile(),
            http_status=700,
            transport_category="private\nvalue",
            slow=Hostile(),
        )
        return Hostile()

    client._ords_service.describe_vector_database.side_effect = emit
    client.describe_vector_database()
    for record in caplog.records:
        assert record.args == ()  # nosec B101
        assert record.exc_info is None  # nosec B101
        assert record.stack_info is None  # nosec B101
        assert all(
            type(v) in (str, int, float, bool) for v in record.vecdb.values()
        )  # nosec B101
        assert "query" not in record.vecdb  # nosec B101
        assert "private" not in record.getMessage()  # nosec B101
        assert len(record.getMessage()) <= 2048  # nosec B101
    assert sdk_logging._filter_log_fields(
        {
            "error_code": "ORA-12345",
            "http_status": 429,
            "attempt": -1,
            "event": "bad",
            "operation_id": "bad",
        }
    ) == {
        "error_code": "ORA-12345",
        "http_status": 429,
    }  # nosec B101


def test_safe_normalized_error_scalars_only(client, caplog):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    error = VecDBException.from_service_error(
        operation="query",
        arguments={"query_by": {"text": "canary-query"}},
        service_name="ORDSService",
        error=urllib3.exceptions.ReadTimeoutError(None, URL, "canary-timeout"),
    )
    client._ords_service.describe_vector_database.side_effect = error
    with pytest.raises(VecDBException):
        client.describe_vector_database()
    event = events(caplog, "operation.completed")[0]
    assert event["error_code"] == "TIMEOUT"  # nosec B101
    assert event["transport_category"] == "read_timeout"  # nosec B101
    assert "canary" not in caplog.text  # nosec B101
    assert "example.invalid" not in caplog.text  # nosec B101


@pytest.mark.parametrize("failure", ["handler", "filter", "formatter", "clock"])
def test_sink_and_clock_failures_preserve_outcome(
    client, caplog, monkeypatch, failure
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")

    class BrokenHandler(logging.Handler):
        def emit(self, record):
            if failure == "formatter":
                self.format(record)
            raise RuntimeError("canary-sink")

    class BrokenFormatter(logging.Formatter):
        def format(self, record):
            raise RuntimeError("canary-formatter")

    class BrokenFilter(logging.Filter):
        def filter(self, record):
            raise RuntimeError("canary-filter")

    handler = BrokenHandler()
    if failure == "formatter":
        handler.setFormatter(BrokenFormatter())
    if failure == "filter":
        handler.addFilter(BrokenFilter())
    logger = logging.getLogger("oracle_vecdb")
    logger.addHandler(handler)
    if failure == "clock":
        monkeypatch.setattr(
            sdk_logging.time,
            "perf_counter_ns",
            lambda: (_ for _ in ()).throw(ValueError("clock failed")),
        )
    try:
        expected = client._ords_service.describe_vector_database.return_value
        assert client.describe_vector_database() is expected  # nosec B101
        original = ValueError("original business failure")
        client._ords_service.describe_vector_database.side_effect = original
        with pytest.raises(ValueError) as raised:
            client.describe_vector_database()
        assert raised.value is original  # nosec B101
        assert sdk_logging._CURRENT_OPERATION.get() is None  # nosec B101
    finally:
        logger.removeHandler(handler)


def test_generated_response_read_deserialize_order(
    trace_mode, client, caplog, mocker
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    client._ords_service = None
    wire = mocker.Mock()
    wire.status, wire.reason = 200, "OK"
    wire.headers = {
        "content-type": "application/json",
        "Authorization": "canary-header",
    }
    wire.data = json.dumps(
        {"results": [{"id": "private-record", "distance": 0.1}]}
    ).encode()
    response = RESTResponse(wire)
    read = mocker.spy(response, "read")
    mocker.patch(
        "oracle_vecdb.services.ords.rest.RESTClientObject.request",
        return_value=response,
    )
    with trace_mode():
        result = client.query(
            "TEST_TABLE", query_by={"text": "canary-query"}, top_k=1
        )
    assert len(result) == 1  # nosec B101
    assert read.call_count == 1  # nosec B101
    assert response.data == wire.data  # nosec B101
    names = [e["event"] for e in events(caplog)]
    assert names == [
        "operation.started",
        "http.completed",
        "phase.completed",
        "operation.completed",
    ]  # nosec B101
    assert (
        events(caplog, "http.completed")[0]["http_status"] == 200
    )  # nosec B101
    assert (
        events(caplog, "operation.completed")[0]["result_count"] == 1
    )  # nosec B101
    assert "body_read" not in caplog.text  # nosec B101
    assert "canary" not in caplog.text  # nosec B101
    assert "private-record" not in caplog.text  # nosec B101
    assert "TEST_TABLE" not in caplog.text  # nosec B101


def test_transport_and_deserialization_failure_keep_one_outcome(
    trace_mode, client, caplog, mocker
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    client._ords_service = None
    mocker.patch(
        "oracle_vecdb.services.ords.rest.RESTClientObject.request",
        side_effect=urllib3.exceptions.SSLError("canary-tls"),
    )
    with trace_mode():
        with pytest.raises(VecDBException):
            client.query(
                "TEST_TABLE", query_by={"text": "canary-query"}, top_k=1
            )
    assert len(events(caplog, "operation.completed")) == 1  # nosec B101
    assert (
        events(caplog, "http.completed")[0]["outcome"] == "error"
    )  # nosec B101
    caplog.clear()
    transport = client.api_client
    with trace_mode(), sdk_logging._operation_logging_context("query"):
        with pytest.raises(ValueError):
            transport.deserialize(
                "{", "QueryVectors200Response", "application/json"
            )
    assert (
        events(caplog, "phase.completed")[0]["outcome"] == "error"
    )  # nosec B101
    assert "canary" not in caplog.text  # nosec B101


def test_late_read_failure_is_included_in_total(
    trace_mode, client, caplog, mocker
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    client._ords_service = None

    class Wire:
        status = 200
        reason = "OK"
        headers = {"content-type": "application/json"}

        @property
        def data(self):
            raise urllib3.exceptions.ReadTimeoutError(None, URL, "canary-read")

    mocker.patch(
        "oracle_vecdb.services.ords.rest.RESTClientObject.request",
        return_value=RESTResponse(Wire()),
    )
    with trace_mode():
        with pytest.raises(VecDBException):
            client.query(
                "TEST_TABLE", query_by={"text": "canary-query"}, top_k=1
            )
    assert (
        events(caplog, "http.completed")[0]["outcome"] == "success"
    )  # nosec B101
    assert (
        events(caplog, "operation.completed")[0]["outcome"] == "error"
    )  # nosec B101
    assert events(caplog, "phase.completed") == []  # nosec B101


def test_mixed_retries_report_actual_service_attempts_and_delays(
    trace_mode, client, caplog, monkeypatch
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    failures = [429, 555, 429]
    sleeps = []
    monkeypatch.setattr(
        "oracle_vecdb.ords_response_handlers.time.sleep", sleeps.append
    )

    class Error(Exception):
        def __init__(self, status):
            self.status = status
            self.headers = {"Retry-After": "1"}

    class Endpoint:
        config = client.config

        @ORDSResponseHandler
        def query(self, **kwargs):
            if failures:
                raise Error(failures.pop(0))
            return "result"

    client._ords_service = Endpoint()
    with trace_mode():
        assert (
            client.query("TEST_TABLE", query_by={"text": "canary"}, top_k=1)
            == "result"
        )  # nosec B101
    scheduled = events(caplog, "retry.scheduled")
    assert [e["attempt"] for e in scheduled] == [1, 2, 3]  # nosec B101
    assert [e["delay_ms"] for e in scheduled] == [1000, 0, 1000]  # nosec B101
    assert sleeps == [1, 1]  # nosec B101
    assert all(
        e["retry_owner"] == "ords_response_handler" for e in scheduled
    )  # nosec B101
    assert len({e["operation_id"] for e in events(caplog)}) == 1  # nosec B101
    assert len(events(caplog, "operation.completed")) == 1  # nosec B101
    assert all(
        "sleep_elapsed_ms" in e for e in events(caplog, "phase.completed")
    )  # nosec B101


def test_exhausted_retry_counters(client, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    monkeypatch.setattr(
        "oracle_vecdb.ords_response_handlers.time.sleep", lambda _: None
    )

    class Error(Exception):
        status = 429

    class Endpoint:
        config = client.config

        @ORDSResponseHandler
        def query(self, **kwargs):
            raise Error()

    client._ords_service = Endpoint()
    client.config.ords_settings.max_retry_count_error_429 = 1
    with pytest.raises(Error):
        client.query("TEST_TABLE", query_by={"text": "canary"}, top_k=1)
    stopped = events(caplog, "retry.stopped")[-1]
    assert stopped["reason"] == "retry_limit_exhausted"  # nosec B101
    assert stopped["attempt"] == 2  # nosec B101


def test_batch_aggregation_partial_failure_and_no_extra_serialization(
    trace_mode, client, caplog, mocker, monkeypatch
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    monkeypatch.setattr(client_module, "_MAX_UPSERT_BATCH_BYTES", 35)
    vectors = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    size = mocker.spy(client_module.json, "dumps")
    with trace_mode():
        result = client.upsert_vectors("TEST_TABLE", vectors)
    assert result.upserted_count == 2  # nosec B101
    assert len(events(caplog, "operation.completed")) == 1  # nosec B101
    terminal = events(caplog, "operation.completed")[0]
    assert terminal["batch_count"] == 2  # nosec B101
    assert terminal["result_count"] == 2  # nosec B101
    assert size.call_count == 6  # nosec B101
    caplog.clear()
    client._ords_service.upsert_vectors.side_effect = [
        UpsertVectorsResponse(upserted_count=2),
        ValueError("canary-batch"),
    ]
    with pytest.raises(ValueError):
        client.upsert_vectors("TEST_TABLE", vectors)
    terminal = events(caplog, "operation.completed")[0]
    assert terminal["batch_count"] == 1  # nosec B101
    assert terminal["result_count"] == 2  # nosec B101
    assert terminal["outcome"] == "error"  # nosec B101


def test_oauth_is_independent_and_excludes_credentials(
    client, caplog, mocker, trace_mode
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    pool = mocker.Mock()
    response = mocker.Mock(
        status=200,
        data=b'{"access_token":"canary-token","token_type":"bearer"}',
    )
    pool.request.return_value = response
    mocker.patch("oracle_vecdb.auth._build_pool", return_value=pool)
    with trace_mode(), sdk_logging._operation_logging_context("query"):
        result = oracle_vecdb.get_vecdb_oauth_token(
            client_id="canary-client",
            client_secret="example",  # nosec B106
            token_url=URL,
        )
    assert result["access_token"] == "canary-token"  # nosec B101
    completed = [
        e
        for e in events(caplog, "operation.completed")
        if e["operation"] == "get_vecdb_oauth_token"
    ]
    assert len(completed) == 1  # nosec B101
    assert "client_id" not in completed[0]  # nosec B101
    assert "parent_operation_id" not in completed[0]  # nosec B101
    assert completed[0]["operation"] == "get_vecdb_oauth_token"  # nosec B101
    assert "canary" not in caplog.text  # nosec B101
    assert "example" not in caplog.text  # nosec B101
    assert "example.invalid" not in caplog.text  # nosec B101
    response.release_conn.assert_called_once()
    pool.clear.assert_called_once()
    caplog.clear()
    pool.clear.side_effect = OSError("canary-cleanup")
    with pytest.raises(OSError):
        oracle_vecdb.get_vecdb_oauth_token(
            client_id="canary-client",
            client_secret="example",  # nosec B106
            token_url=URL,
        )
    assert (
        events(caplog, "operation.completed")[0]["outcome"] == "error"
    )  # nosec B101


def test_console_fallback_yields_to_application_handler(monkeypatch, capsys):
    logger = logging.getLogger("oracle_vecdb")
    monkeypatch.setattr(logger, "handlers", [logging.NullHandler()])
    monkeypatch.setattr(logger, "propagate", False)
    handler = sdk_logging._FallbackConsoleHandler()
    record = logger.makeRecord(
        "oracle_vecdb", logging.INFO, "", 0, "safe", (), None
    )
    assert handler.filter(record)  # nosec B101
    # Even a handler whose threshold drops this record takes ownership of output.
    application = logging.StreamHandler()
    application.setLevel(logging.ERROR)
    logger.addHandler(application)
    assert handler.filter(record) is False  # nosec B101
    # A failed console sink never triggers logging's raw traceback fallback.
    handler.handleError(record)
    assert capsys.readouterr() == ("", "")  # nosec B101


@pytest.mark.parametrize(
    "value,level,trace",
    [
        ("", None, False),
        ("  info  ", logging.INFO, False),
        ("1", logging.DEBUG, False),
        ("true", logging.DEBUG, False),
        ("YES", logging.DEBUG, False),
        ("on", logging.DEBUG, False),
        ("0", 51, False),
        ("false", 51, False),
        ("no", 51, False),
        ("off", 51, False),
        ("trace", logging.DEBUG, True),
        ("warn", logging.WARNING, False),
        ("fatal", logging.CRITICAL, False),
        ("ERROR", logging.ERROR, False),
        ("NOTSET", logging.NOTSET, False),
    ],
)
def test_environment_levels(monkeypatch, value, level, trace):
    monkeypatch.setenv("VECDB_DEBUG", value)
    assert sdk_logging._read_logging_environment() == (
        level,
        trace,
    )  # nosec B101


@pytest.mark.parametrize("value", ["invalid-private-value", "2", "10"])
def test_invalid_environment(monkeypatch, value):
    monkeypatch.setenv("VECDB_DEBUG", value)
    with pytest.raises(ValueError, match="VECDB_DEBUG") as error:
        sdk_logging._configure_logging()
    assert value not in str(error.value)  # nosec B101


def test_removed_policy_api_is_not_exposed(client):
    assert not hasattr(oracle_vecdb, "DiagnosticsOptions")  # nosec B101
    assert not hasattr(type(client), "diagnostics")  # nosec B101
    for target in (
        type(client.config).__init__,
        oracle_vecdb.get_vecdb_oauth_token,
    ):
        assert (
            "diagnostics" not in inspect.signature(target).parameters
        )  # nosec B101
    with pytest.raises(TypeError, match="diagnostics"):
        Configuration(rest_url=URL, diagnostics=object())


def test_configuration_does_not_configure_logging(monkeypatch):
    logger = logging.getLogger("oracle_vecdb")
    before = logger.level, list(logger.handlers), sdk_logging._TRACE_ENABLED
    monkeypatch.setenv("VECDB_DEBUG", "invalid")
    cfg = Configuration(rest_url=URL)
    assert (
        logger.level,
        logger.handlers,
        sdk_logging._TRACE_ENABLED,
    ) == before  # nosec B101
    assert not any("diagnostic" in key for key in vars(cfg))  # nosec B101


def test_quiet_default_and_no_global_mutation(capsys):
    names = (
        "",
        "internal",
        "urllib3",
        "oracle_vecdb",
        "http.client",
        "oracledb",
    )
    before = [
        (logging.getLogger(n).level, list(logging.getLogger(n).handlers))
        for n in names
    ]
    wire = http.client.HTTPConnection.debuglevel
    importlib.reload(oracle_vecdb)
    Configuration(rest_url=URL)
    assert before == [
        (logging.getLogger(n).level, list(logging.getLogger(n).handlers))
        for n in names
    ]  # nosec B101
    assert http.client.HTTPConnection.debuglevel == wire  # nosec B101
    assert capsys.readouterr() == ("", "")  # nosec B101


def test_quiet_logger_skips_instrumentation(monkeypatch):
    logger = logging.getLogger("oracle_vecdb.operations")
    monkeypatch.setattr(sdk_logging, "_LOGGERS", {"operations": logger})
    monkeypatch.setattr(logger, "handlers", [logging.NullHandler()])
    monkeypatch.setattr(logger, "propagate", False)
    assert not sdk_logging._is_logging_enabled("operations")  # nosec B101
    monkeypatch.setattr(logger, "propagate", True)
    monkeypatch.setattr(logger, "parent", None)
    assert not sdk_logging._is_logging_enabled("operations")  # nosec B101
    with sdk_logging._operation_logging_context("query"):
        assert sdk_logging._CURRENT_OPERATION.get() is None  # nosec B101


def test_nested_operations_share_fixed_event_budget(caplog, trace_mode):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    with trace_mode(), sdk_logging._operation_logging_context("query"):
        parent = sdk_logging._CURRENT_OPERATION.get().operation_id
        with sdk_logging._operation_logging_context("list_vectors"):
            for _ in range(300):
                sdk_logging._log_event(
                    "retry.stopped",
                    "ords",
                    logging.DEBUG,
                    reason="already_normalized",
                )
        sdk_logging._log_event(
            "retry.stopped", "ords", logging.DEBUG, reason="already_normalized"
        )
    assert len(events(caplog, "operation.completed")) == 2  # nosec B101
    child = events(caplog, "operation.completed")[0]
    assert child["parent_operation_id"] == parent  # nosec B101
    assert len(events(caplog, "diagnostics.suppressed")) == 1  # nosec B101
    assert len(events(caplog)) == 259  # nosec B101
    assert sdk_logging._CURRENT_OPERATION.get() is None  # nosec B101


def test_phase_clock_failure_preserves_result(
    client, caplog, trace_mode, monkeypatch
):
    caplog.set_level(logging.DEBUG, logger="oracle_vecdb")
    with trace_mode(), sdk_logging._operation_logging_context("query"):
        monkeypatch.setattr(
            sdk_logging.time,
            "perf_counter_ns",
            lambda: (_ for _ in ()).throw(RuntimeError("clock failed")),
        )
        with sdk_logging._log_phase("deserialize"):
            pass
    assert sdk_logging._CURRENT_OPERATION.get() is None  # nosec B101


def test_fallback_yields_to_child_application_handler(monkeypatch):
    package_logger = logging.getLogger("oracle_vecdb")
    child_logger = logging.getLogger("oracle_vecdb.operations")
    monkeypatch.setattr(package_logger, "handlers", [logging.NullHandler()])
    monkeypatch.setattr(package_logger, "propagate", False)
    monkeypatch.setattr(child_logger, "handlers", [logging.StreamHandler()])
    monkeypatch.setattr(child_logger, "propagate", True)
    record = child_logger.makeRecord(
        child_logger.name, logging.INFO, "", 0, "safe", (), None
    )
    assert not sdk_logging._FallbackConsoleHandler().filter(
        record
    )  # nosec B101


def test_off_suppresses_explicit_child_logger_levels(
    client, caplog, monkeypatch
):
    package_logger = logging.getLogger("oracle_vecdb")
    saved_level = package_logger.level
    monkeypatch.setenv("VECDB_DEBUG", "OFF")
    try:
        sdk_logging._configure_logging()
        caplog.set_level(logging.DEBUG, logger="oracle_vecdb.operations")
        client.describe_vector_database()
        assert events(caplog) == []  # nosec B101
        # Standard Python logging can re-enable output without client options.
        package_logger.setLevel(logging.INFO)
        client.describe_vector_database()
        assert len(events(caplog, "operation.completed")) == 1  # nosec B101
    finally:
        package_logger.setLevel(saved_level)


def test_ords_only_logger_configuration_logs_phases(client, caplog, trace_mode):
    with trace_mode():
        caplog.set_level(logging.CRITICAL, logger="oracle_vecdb")
        caplog.set_level(logging.DEBUG, logger="oracle_vecdb.ords")

        def deserialize():
            with sdk_logging._log_phase("deserialize"):
                return "result"

        client._ords_service.describe_vector_database.side_effect = deserialize
        assert client.describe_vector_database() == "result"  # nosec B101
    assert len(events(caplog, "phase.completed")) == 1  # nosec B101
    assert events(caplog, "operation.completed") == []  # nosec B101


def test_logger_eligibility_failure_preserves_sdk_outcome(client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("logger failure")

    monkeypatch.setattr(
        logging.getLogger("oracle_vecdb.operations"), "isEnabledFor", fail
    )
    expected = client._ords_service.describe_vector_database.return_value
    assert client.describe_vector_database() is expected  # nosec B101
    original = ValueError("business failure")
    client._ords_service.describe_vector_database.side_effect = original
    with pytest.raises(ValueError) as raised:
        client.describe_vector_database()
    assert raised.value is original  # nosec B101


@pytest.mark.parametrize("failed_tick", [0, 1])
def test_clock_failure_keeps_completion_summary(
    client, caplog, monkeypatch, failed_tick
):
    caplog.set_level(logging.INFO, logger="oracle_vecdb")
    ticks = 0

    def clock():
        nonlocal ticks
        tick = ticks
        ticks += 1
        if tick == failed_tick:
            raise RuntimeError("clock failure")
        return tick * 1_000_000

    monkeypatch.setattr(sdk_logging.time, "perf_counter_ns", clock)
    client.describe_vector_database()
    completed = events(caplog, "operation.completed")
    assert len(completed) == 1  # nosec B101
    assert completed[0]["outcome"] == "success"  # nosec B101
    assert "elapsed_ms" not in completed[0]  # nosec B101


def test_all_public_sdk_methods_log_completion(client, caplog):
    caplog.set_level(logging.INFO, logger="oracle_vecdb")
    methods = {
        name
        for name, method in vars(OracleVecDB).items()
        if not name.startswith("_") and inspect.isfunction(method)
    }
    assert methods == sdk_logging._OPERATIONS - {
        "get_vecdb_oauth_token"
    }  # nosec B101
    for name in sorted(methods):
        caplog.clear()
        # Missing arguments exercise validation; no-argument calls use the mock service.
        try:
            getattr(client, name)()
        except (
            Exception
        ):  # nosec B110 - validation errors are expected in this coverage check
            pass
        completed = events(caplog, "operation.completed")
        assert len(completed) == 1, name  # nosec B101
        assert completed[0]["operation"] == name  # nosec B101
