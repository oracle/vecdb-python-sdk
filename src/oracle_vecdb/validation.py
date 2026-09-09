##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

from __future__ import annotations

import inspect
from collections.abc import Mapping
from copy import deepcopy
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar, cast

from pydantic import BaseModel, StrictStr, ValidationError, field_validator

from .default_settings import DefaultSettings
from .parameter_validation import validate_operation_arguments
from .vecdb_exception import VecDBException
from .vecdb_errors import (
    DefaultSettingsParameterMismatchError,
    InvalidParameterCombinationError,
)

P = ParamSpec("P")
R = TypeVar("R")
ResourceErrorFactory = Callable[[str], BaseException]


def _merge_default_mapping(
    defaults: Mapping[str, Any], supplied: Mapping[str, Any]
) -> dict[str, Any]:
    """Merge nested defaults without mutating either input mapping.

    Values from ``supplied`` take precedence, including an explicit ``None``.
    Nested mappings are merged recursively so callers can override one option
    while retaining DefaultSettings values for sibling options.
    """
    result = deepcopy(dict(defaults))
    for key, supplied_value in supplied.items():
        default_value = result.get(key)
        if isinstance(default_value, Mapping) and isinstance(
            supplied_value, Mapping
        ):
            result[key] = _merge_default_mapping(default_value, supplied_value)
        else:
            result[key] = deepcopy(supplied_value)
    return result


def set_default_arguments(
    function: Callable[P, R],
) -> Callable[P, R]:
    """Apply verified DefaultSettings defaults to omitted public arguments.

    Explicit caller values, including ``None``, always take precedence.
    Dictionary values are merged recursively so a caller can override one
    nested option without discarding unspecified DefaultSettings defaults.
    """
    signature = inspect.signature(function)
    defaults = DefaultSettings.get_default_args_for(function.__name__)
    unknown_parameters = set(defaults).difference(signature.parameters)
    if unknown_parameters:
        error = DefaultSettingsParameterMismatchError(
            function_name=function.__name__,
            parameter_names=sorted(unknown_parameters),
        )
        raise VecDBException.from_service_error(
            operation=function.__name__,
            arguments={
                "kwargs": {"parameter_names": sorted(unknown_parameters)}
            },
            service_name="common_spec",
            error=error,
        ) from error

    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        arguments = signature.bind(*args, **kwargs)
        for parameter_name, default in defaults.items():
            if parameter_name not in arguments.arguments:
                # ``bind`` records only arguments supplied by the caller.
                # Insert a private copy only when this parameter was omitted.
                arguments.arguments[parameter_name] = deepcopy(default)
            elif isinstance(default, Mapping) and isinstance(
                arguments.arguments[parameter_name], Mapping
            ):
                # For nested option dictionaries, retain unspecified DefaultSettings
                # values while giving every caller-provided key precedence.
                arguments.arguments[parameter_name] = _merge_default_mapping(
                    default,
                    arguments.arguments[parameter_name],
                )

        # Apply any future operation-aware defaults after the public arguments
        # have been bound and unconditional defaults materialized.  Index
        # distribution is deliberately validated as explicitly supplied.
        arguments.arguments.update(
            DefaultSettings.apply_operation_aware_defaults(
                function.__name__,
                arguments.arguments,
            )
        )
        return function(*arguments.args, **arguments.kwargs)

    return wrapper


def validate_common_spec_arguments(
    function: Callable[P, R],
) -> Callable[P, R]:
    """Validate PL/SQL-derived argument dependencies before delegation.

    This decorator is transport-neutral: it protects the common facade before
    either ORDS or a future native SDK receives the request.  It deliberately
    validates only deterministic request rules; database-state checks remain
    the responsibility of PL/SQL.
    """
    signature = inspect.signature(function)

    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        arguments = signature.bind(*args, **kwargs)
        try:
            validate_operation_arguments(function.__name__, arguments.arguments)
        except (ValidationError, ValueError, TypeError) as validation_error:
            error = InvalidParameterCombinationError(
                parameter_name="request parameters",
                detail=str(validation_error),
            )
            # Do not attach the full nested request: it may contain credentials,
            # signed URLs, query text, or other sensitive application data.
            raise VecDBException.from_service_error(
                operation=function.__name__,
                arguments={"kwargs": {"request": "<redacted>"}},
                service_name="validation",
                error=error,
            ) from validation_error
        return function(*arguments.args, **arguments.kwargs)

    return wrapper


class ResourceName(BaseModel):
    """Conservative resource-name checks shared by public SDK methods.

    Character, case, and length rules belong to the configured Oracle Database:
    they can vary with the database version and identifier configuration.  The
    SDK therefore rejects only values that are not safe, meaningful text for a
    resource identifier on every supported transport.
    """

    resource_name: StrictStr

    @field_validator("resource_name", mode="after")
    @classmethod
    def validate_resource_name(cls, value: str) -> str:
        if value is None or len(value.strip()) == 0:
            raise ValueError("Input value cannot be None, empty, or blank")
        if "\x00" in value or '"' in value:
            raise ValueError(
                "Input value cannot contain NUL or double-quote characters"
            )
        return value


def validate_resource_name(
    value: str,
    *,
    operation: str,
    parameter_name: str,
    error_factory: ResourceErrorFactory,
) -> str:
    """Apply only transport-safe validation to a public resource name.

    The public facade exposes :class:`VecDBException` for both local and
    service validation failures.  ``original_exception_type`` and
    ``is_original_exception()`` retain the resource-specific SDK error
    category so existing callers can distinguish table, model, and job-name
    validation failures without retaining the original error payload.

    Database-specific grammar, including other allowed punctuation, case,
    Unicode, and length, is deliberately delegated to the Oracle Database.
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
