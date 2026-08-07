##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

from __future__ import annotations

import inspect
from functools import wraps
from typing import Callable, ParamSpec, TypeVar, cast

from pydantic import BaseModel, ValidationError, field_validator

from .vecdb_exception import VecDBException

P = ParamSpec("P")
R = TypeVar("R")
ResourceErrorFactory = Callable[[str], BaseException]


class ResourceName(BaseModel):
    resource_name: str

    @field_validator("resource_name", mode="after")
    @classmethod
    def validate_resource_name(cls, value: str) -> str:
        if value is None or len(value.strip()) == 0:
            raise ValueError("Input value cannot be None, empty, or blank")
        return value


def validate_resource_name(
    value: str,
    *,
    operation: str,
    parameter_name: str,
    error_factory: ResourceErrorFactory,
) -> str:
    """Validate a public resource name using the common error contract.

    The public facade exposes :class:`VecDBException` for both local and
    service validation failures.  ``original_exception`` retains the
    resource-specific SDK error so existing callers can distinguish table,
    model, and job-name validation failures without importing implementation
    details from the generated client.
    """
    try:
        return ResourceName(resource_name=value).resource_name
    except ValidationError as validation_error:
        error = error_factory(value)
        raise VecDBException.from_service_error(
            operation=operation,
            arguments={"kwargs": {parameter_name: value}},
            service_name="validation",
            error=error,
        ) from validation_error


def validate_resource_names(
    **error_factories: ResourceErrorFactory,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Validate named resource arguments before invoking a public method.

    Each keyword is a public method parameter and its value is the stable SDK
    error factory for that resource type. ``functools.wraps`` preserves the
    public method's documentation and introspectable signature.
    """

    def decorator(function: Callable[P, R]) -> Callable[P, R]:
        signature = inspect.signature(function)

        @wraps(function)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            arguments = signature.bind(*args, **kwargs)
            for parameter_name, error_factory in error_factories.items():
                if parameter_name not in arguments.arguments:
                    continue
                arguments.arguments[parameter_name] = validate_resource_name(
                    cast(str, arguments.arguments[parameter_name]),
                    operation=function.__name__,
                    parameter_name=parameter_name,
                    error_factory=error_factory,
                )
            return function(*arguments.args, **arguments.kwargs)

        return wrapper

    return decorator
