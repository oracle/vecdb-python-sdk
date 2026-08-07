##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""API response object."""

from __future__ import annotations
from typing import Optional, Generic, Mapping, TypeVar
from pydantic import Field, StrictInt, StrictBytes, BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    API response object
    """

    status_code: StrictInt = Field(description="HTTP status code")
    headers: Optional[Mapping[str, str]] = Field(
        None, description="HTTP headers"
    )
    data: T = Field(description="Deserialized data given the data type")
    raw_data: StrictBytes = Field(description="Raw data (HTTP response body)")

    model_config = {"arbitrary_types_allowed": True}
