##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""Public response models returned by the Oracle VecDB SDK facade."""

from __future__ import annotations

import json
import pprint

from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Sequence,
    Union,
)

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from ..services.ords.models.query_vectors200_response import (
    QueryVectors200Response,
)

Number = Union[int, float]


class _VecDBModel(BaseModel):
    """Base model for handwritten public response types."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        protected_namespaces=(),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Return the response using the SDK's historical serialization API."""
        return self.model_dump(mode="python", by_alias=True, exclude_none=True)

    def to_json(self) -> str:
        """Return a JSON representation compatible with generated models."""
        return json.dumps(
            self.model_dump(mode="json", by_alias=True, exclude_none=True)
        )

    def to_str(self) -> str:
        """Return a readable representation compatible with generated models."""
        return pprint.pformat(self.to_dict())


class MessageResponse(_VecDBModel):
    """Simple confirmation response with a message payload."""

    message: Optional[str] = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        if isinstance(response, cls):
            return response
        if isinstance(response, dict):
            if "message" not in response:
                raise ValueError(
                    "Response is missing required field 'message'."
                )
            return cls(message=response["message"])
        message = getattr(response, "message", None)
        if message is None:
            raise ValueError("Response is missing required field 'message'.")
        return cls(message=message)


class DeleteVectorsResponse(MessageResponse):
    """Confirmation returned by ``delete_vectors``."""


class DropVectorTableResponse(MessageResponse):
    """Confirmation returned by ``drop_vector_table``."""


class DropIndexResponse(MessageResponse):
    """Confirmation returned by ``drop_index``."""


class DropModelResponse(_VecDBModel):
    """Confirmation returned by ``drop_model``."""

    dropped: Optional[str] = None
    message: Optional[str] = None

    @classmethod
    def from_internal(cls, response: Any) -> "DropModelResponse":
        if isinstance(response, cls):
            return response
        if isinstance(response, dict):
            return cls(
                dropped=response.get("dropped"),
                message=response.get("message"),
            )
        return cls(
            dropped=getattr(response, "dropped", None),
            message=getattr(response, "message", None),
        )


class IndexDescriptionResponse(_VecDBModel):
    """Stable SDK shape for index description responses."""

    index_status: Optional[str] = None

    @classmethod
    def from_internal(cls, response: Any) -> "IndexDescriptionResponse":
        if isinstance(response, cls):
            return response
        if isinstance(response, dict):
            return cls(
                index_status=response.get("index_status")
                or response.get("Index Status")
            )
        return cls(index_status=getattr(response, "index_status", None))


class IndexDetailsResponse(_VecDBModel):
    """Vector and metadata index details returned with a table description."""

    dense_idx_name: Optional[str] = None
    indexed_metadata_json_paths: Optional[List[str]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        protected_namespaces=(),
        extra="allow",
    )

    def __getitem__(self, key: str) -> Any:
        """Support dictionary-style access alongside attribute access."""
        return self.model_dump(mode="python", by_alias=True).get(key)

    @classmethod
    def from_internal(cls, response: Any) -> Optional[Self]:
        if response is None:
            return None
        if isinstance(response, cls):
            return response
        if isinstance(response, (list, tuple)):
            response = dict(response)
        if isinstance(response, dict):
            return cls.model_validate(response)
        for method in ("model_dump", "to_dict"):
            serializer = getattr(response, method, None)
            if callable(serializer):
                return cls.model_validate(serializer())
        return cls.model_validate(
            {
                "dense_idx_name": getattr(response, "dense_idx_name", None),
                "indexed_metadata_json_paths": getattr(
                    response, "indexed_metadata_json_paths", None
                ),
            }
        )


class QueryResultItem(_VecDBModel):
    """Single search hit returned by ``query``."""

    id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    vector: Optional[List[Number]] = None
    distance: Optional[Number] = None

    @classmethod
    def from_internal(cls, item: Any) -> "QueryResultItem":
        if isinstance(item, cls):
            return item
        if isinstance(item, dict):
            return cls.model_validate(item)

        data: Dict[str, Any] = {}
        for field_name in ("id", "metadata", "vector", "distance"):
            data[field_name] = getattr(item, field_name, None)
        return cls.model_validate(data)


class QueryResponse(_VecDBModel):
    """SDK search response with a stable collection wrapper."""

    items: List[QueryResultItem] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> QueryResultItem:
        return self.items[index]

    @property
    def results(self) -> List[QueryResultItem]:
        """Compatibility alias for callers expecting raw result semantics."""
        return self.items

    @classmethod
    def from_internal(cls, response: Any) -> "QueryResponse":
        if isinstance(response, cls):
            return response

        if isinstance(response, dict):
            raw_items = response.get("items")
            if raw_items is None:
                if "results" not in response:
                    raise ValueError(
                        "Query response is missing required field 'results'."
                    )
                raw_items = response["results"]
        elif isinstance(response, QueryVectors200Response):
            if response.results is None:
                raise ValueError(
                    "Query response is missing required field 'results'."
                )
            raw_items = response.results
        else:
            raw_items = getattr(response, "results", None)
            if raw_items is None:
                raw_items = getattr(response, "items", None)
            if raw_items is None and isinstance(response, Sequence):
                raw_items = response
            if raw_items is None:
                raise ValueError(
                    "Query response is missing required field 'results'."
                )

        return cls(
            items=[
                QueryResultItem.from_internal(item) for item in raw_items or []
            ]
        )


class RerankResultItem(_VecDBModel):
    """Single rerank score returned by ``rerank``."""

    index: int
    score: Number

    @classmethod
    def from_internal(cls, item: Any) -> "RerankResultItem":
        if isinstance(item, cls):
            return item
        if isinstance(item, dict):
            return cls.model_validate(item)
        return cls.model_validate(
            {
                "index": getattr(item, "index", None),
                "score": getattr(item, "score", None),
            }
        )


class RerankResponse(_VecDBModel):
    """SDK rerank response with a stable collection wrapper."""

    items: List[RerankResultItem] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, index: int) -> RerankResultItem:
        return self.items[index]

    @classmethod
    def from_internal(cls, response: Iterable[Any]) -> "RerankResponse":
        return cls(
            items=[
                RerankResultItem.from_internal(item) for item in response or []
            ]
        )


def _value(response: Any, name: str, default: Any = None) -> Any:
    if isinstance(response, dict):
        if name in response:
            return response[name]
        # Preserve OpenAPI aliases used on generated ORDS models.
        aliases = {"has_more": "hasMore", "error": "error#"}
        return response.get(aliases.get(name, name), default)
    value = getattr(response, name, default)
    if value is default:
        aliases = {"has_more": "hasMore", "error": "error#"}
        alias = aliases.get(name)
        if alias:
            value = getattr(response, alias, default)
    return default if callable(value) else value


class DatabaseSummaryResponse(_VecDBModel):
    total_tables: Optional[int] = None
    total_vectors: Optional[int] = None
    total_models: Optional[int] = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        values = {name: _value(response, name) for name in cls.model_fields}
        values["items"] = values.get("items") or []
        return cls(**values)


class VectorTableResponse(_VecDBModel):
    table_name: Optional[str] = None
    comment: Optional[str] = None
    annotations: Optional[Dict[str, Any]] = None
    vector_type: Optional[str] = None
    vector_table_type: Optional[str] = None
    embed_params: Any = None
    index_params: Any = None
    owner: Optional[str] = None
    indexes: Optional[IndexDetailsResponse] = None
    status: Optional[str] = None
    stats: Any = None
    created: Any = None
    updated: Any = None
    table_params: Any = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        values = {name: _value(response, name) for name in cls.model_fields}
        values["indexes"] = IndexDetailsResponse.from_internal(
            values["indexes"]
        )
        return cls(**values)


class _PagedResponse(_VecDBModel):
    items: List[Any] = Field(default_factory=list)
    has_more: Optional[bool] = None
    limit: Optional[int] = None
    offset: Optional[int] = None
    count: Optional[int] = None
    links: Optional[List[Any]] = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        values = {name: _value(response, name) for name in cls.model_fields}
        values["items"] = values.get("items") or []
        return cls(**values)


class VectorTableCollectionResponse(_PagedResponse):
    pass


class ModelCollectionResponse(_PagedResponse):
    pass


class JobCollectionResponse(_PagedResponse):
    pass


class VectorCollectionResponse(_VecDBModel):
    items: List[Any] = Field(default_factory=list)
    limit: Optional[int] = None
    offset: Optional[int] = None
    count: Optional[int] = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        values = {name: _value(response, name) for name in cls.model_fields}
        values["items"] = values.get("items") or []
        return cls(**values)


class EmbeddingResponse(_VecDBModel):
    data: List[Any] = Field(default_factory=list)

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        return cls(data=_value(response, "data", []) or [])


class UpsertVectorsResponse(_VecDBModel):
    upserted_count: Optional[int] = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        return cls(upserted_count=_value(response, "upserted_count"))


class JobResponse(_VecDBModel):
    job_name: Optional[str] = None
    job_creator: Optional[str] = None
    job_type: Optional[str] = None
    operation: Optional[str] = None
    state: Optional[str] = None
    start_date: Optional[str] = None
    links: Optional[List[Any]] = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        return cls(
            **{name: _value(response, name) for name in cls.model_fields}
        )


class JobLogResponse(_VecDBModel):
    log_date: Optional[str] = None
    job_name: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    additional_info: Optional[str] = None
    actual_start_date: Optional[str] = None
    run_duration: Optional[str] = None
    links: Optional[List[Any]] = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        values = {name: _value(response, name) for name in cls.model_fields}
        # ORDS represents a successful log error value as numeric 0 in some
        # service versions, although the public response field is textual.
        # Normalize all scalar text fields at this boundary so the generated
        # service models cannot leak that representation into Pydantic.
        for name in (
            "log_date",
            "job_name",
            "status",
            "error",
            "additional_info",
            "actual_start_date",
            "run_duration",
        ):
            if values[name] is not None and not isinstance(values[name], str):
                values[name] = str(values[name])
        return cls(**values)


class ModelResponse(_VecDBModel):
    model_name: Optional[str] = None
    algorithm: Optional[str] = None
    mining_function: Optional[str] = None
    creation_date: Optional[str] = None
    attributes: Any = None

    @classmethod
    def from_internal(cls, response: Any) -> Self:
        return cls(
            **{name: _value(response, name) for name in cls.model_fields}
        )


__all__ = [
    "DatabaseSummaryResponse",
    "DeleteVectorsResponse",
    "DropIndexResponse",
    "DropModelResponse",
    "DropVectorTableResponse",
    "EmbeddingResponse",
    "IndexDescriptionResponse",
    "JobCollectionResponse",
    "JobLogResponse",
    "JobResponse",
    "MessageResponse",
    "ModelCollectionResponse",
    "ModelResponse",
    "QueryResponse",
    "QueryResultItem",
    "RerankResponse",
    "RerankResultItem",
    "UpsertVectorsResponse",
    "VectorCollectionResponse",
    "VectorTableCollectionResponse",
    "VectorTableResponse",
]
