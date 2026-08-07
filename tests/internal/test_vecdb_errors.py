##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

from io import StringIO
import contextlib

import pytest

from oracle_vecdb.vecdb_errors import (
    InsecureConnectionError,
    InvalidIndexJobNameFormatError,
    InvalidHostFormatError,
    InvalidLoadJobNameFormatError,
    InvalidModelNameFormatError,
    InvalidTableNameFormatError,
    VecDBError,
)


def test_vecdb_error_message_helpers():
    err = VecDBError("boom")
    err.cause = "Cause"
    err.action = "Action"
    err.excep = RuntimeError("detail")

    assert "boom" in err.get_error()  # nosec B101
    assert "detail" in err.get_error()  # nosec B101
    assert "Cause" in err.get_error_cause_action()  # nosec B101
    assert "Action" in err.get_error_cause_action()  # nosec B101
    assert "detail" in err.get_error_cause_action()  # nosec B101


def test_vecdb_error_print_error_includes_stack():
    err = VecDBError("boom")
    buf = StringIO()
    with contextlib.redirect_stderr(buf):
        err.print_error(printstack=True)

    output = buf.getvalue()
    assert "boom" in output  # nosec B101


def test_vecdb_error_print_error_uses_stderr_by_default(capsys):
    err = VecDBError("boom")

    err.print_error(printstack=False, printstdout=False)

    captured = capsys.readouterr()
    assert "boom" in captured.err  # nosec B101
    assert captured.out == ""  # nosec B101


def test_vecdb_error_print_error_supports_stdout(capsys):
    err = VecDBError("boom")

    err.print_error(printstack=False, printstdout=True)

    captured = capsys.readouterr()
    assert "boom" in captured.out  # nosec B101
    assert captured.err == ""  # nosec B101


def test_vecdb_error_print_error_suppresses_nested_exception_text(capsys):
    err = VecDBError("boom")
    err.excep = RuntimeError("hidden detail")

    err.print_error(printstack=False, printstdout=False)

    captured = capsys.readouterr()
    assert "boom" in captured.err  # nosec B101
    assert (
        "Additional exception context suppressed." in captured.err
    )  # nosec B101
    assert "hidden detail" not in captured.err  # nosec B101
    assert captured.out == ""  # nosec B101


def test_vecdb_error_print_oerr(capsys):
    err = VecDBError("boom")
    err.cause = "Cause"
    err.action = "Action"

    err.print_oerr()
    captured = capsys.readouterr()
    assert "boom" in captured.out  # nosec B101
    assert "Cause" in captured.out  # nosec B101
    assert "Action" in captured.out  # nosec B101


def test_vecdb_error_print_oerr_without_cause_or_action_avoids_none(capsys):
    err = VecDBError("boom")

    err.print_oerr()
    captured = capsys.readouterr()

    assert "boom" in captured.out  # nosec B101
    assert "None" not in captured.out  # nosec B101


def test_invalid_host_format_error_derives_messages():
    err = InvalidHostFormatError("http://bad")

    assert "VECDB-002" in err.get_error()  # nosec B101
    assert "Action:" in err.action  # nosec B101


def test_insecure_connection_error_advises_https():
    err = InsecureConnectionError("http://bad")

    assert "VECDB-001" in err.get_error()  # nosec B101
    assert "HTTPS is required" in err.get_error()  # nosec B101


def test_error_messages_fallback_to_english_for_requested_locale():
    err = InsecureConnectionError("http://bad", locale="es")

    assert err.locale == "es"  # nosec B101
    assert "Insecure REST URL" in err.get_error()  # nosec B101
    assert "VECDB-001" in err.get_error()  # nosec B101


def test_error_messages_fallback_to_english_for_unknown_locale():
    err = InvalidTableNameFormatError("bad table", locale="fr-FR")

    assert "Invalid table name format" in err.get_error()  # nosec B101
    assert "VECDB-003" in err.get_error()  # nosec B101


@pytest.mark.parametrize(
    "error_cls,value,code",
    [
        (InvalidTableNameFormatError, "bad table", "VECDB-003"),
        (InvalidModelNameFormatError, "bad model", "VECDB-004"),
        (InvalidLoadJobNameFormatError, "bad load job", "VECDB-005"),
        (InvalidIndexJobNameFormatError, "bad index job", "VECDB-006"),
    ],
)
def test_resource_name_errors_include_codes_causes_and_actions(
    error_cls, value, code
):
    err = error_cls(value)

    message = err.get_error_cause_action()

    assert code in message  # nosec B101
    assert value in message  # nosec B101
    assert "Cause:" in message  # nosec B101
    assert "Action:" in message  # nosec B101
