"""Stable SDK errors backed by an external English message catalog."""

from __future__ import annotations

import sys
import traceback
from typing import Any, Mapping, Optional

from .error_messages import ERROR_MESSAGES


def _locale_catalog(locale: Optional[str]) -> Mapping[str, Mapping[str, str]]:
    """Return the catalog for a locale, falling back to English."""
    del locale  # English is currently the only shipped catalog.
    return ERROR_MESSAGES


class VecDBError(Exception):
    """Base SDK error with stable code and localized display text."""

    def __init__(
        self,
        message: str,
        *,
        error_code: Optional[str] = None,
        locale: Optional[str] = None,
        params: Optional[Mapping[str, Any]] = None,
    ):
        self.error_code = error_code
        self.locale = locale or "en"
        self.params = dict(params or {})
        self.cause = ""
        self.action = ""
        if error_code:
            template = _locale_catalog(locale).get(error_code)
            if template:
                message = template["message"].format(**self.params)
                self.cause = "Cause: " + template["cause"].format(**self.params)
                self.action = "Action: " + template["action"].format(
                    **self.params
                )
        super().__init__(message)
        self.msg = f"{error_code}: {message}" if error_code else message
        self.args = (self.msg,)
        self.excep = None

    def print_error(self, printstack=True, printstdout=False):
        stream = sys.stdout if printstdout else sys.stderr
        print(self.msg, file=stream)
        if self.excep:
            print("Additional exception context suppressed.", file=stream)
        if printstack:
            traceback.print_exc(file=stream)

    def get_error_cause_action(self) -> str:
        return "\n".join(
            filter(None, (self.get_error(), self.cause, self.action))
        )

    def get_error(self) -> str:
        return self.msg + (("\n" + str(self.excep)) if self.excep else "")

    def print_oerr(self):
        print(self.msg)
        if self.cause:
            print(self.cause)
        if self.action:
            print(self.action)


class InsecureConnectionError(VecDBError):
    def __init__(self, host, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-001",
            locale=locale,
            params={"rest_url": host},
        )


class InvalidHostFormatError(VecDBError):
    def __init__(self, host, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-002",
            locale=locale,
            params={"rest_url": host},
        )


class InvalidTableNameFormatError(VecDBError):
    def __init__(self, table_name, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-003",
            locale=locale,
            params={"table_name": table_name},
        )


class InvalidModelNameFormatError(VecDBError):
    def __init__(self, model_name, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-004",
            locale=locale,
            params={"model_name": model_name},
        )


class InvalidLoadJobNameFormatError(VecDBError):
    def __init__(self, load_job_name, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-005",
            locale=locale,
            params={"load_job_name": load_job_name},
        )


class InvalidIndexJobNameFormatError(VecDBError):
    def __init__(self, index_job_name, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-006",
            locale=locale,
            params={"index_job_name": index_job_name},
        )


class VectorPayloadTooLargeError(VecDBError):
    def __init__(self, payload_size: int, maximum_size: int, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-007",
            locale=locale,
            params={"payload_size": payload_size, "maximum_size": maximum_size},
        )


class InvalidVectorsError(VecDBError):
    def __init__(self, *, locale=None):
        super().__init__("", error_code="VECDB-008", locale=locale)


class ResourceNotFoundError(VecDBError):
    def __init__(self, resource_name, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-009",
            locale=locale,
            params={"resource_name": resource_name},
        )


class InvalidLoadJobLogError(VecDBError):
    def __init__(self, load_job_name, state, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-010",
            locale=locale,
            params={"load_job_name": load_job_name, "state": state},
        )


class InvalidIndexJobLogError(VecDBError):
    def __init__(self, index_job_name, state, *, locale=None):
        super().__init__(
            "",
            error_code="VECDB-011",
            locale=locale,
            params={"index_job_name": index_job_name, "state": state},
        )
