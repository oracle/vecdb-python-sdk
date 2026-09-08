"""Transport-neutral validation for PL/SQL parameter dependencies.

The public facade accepts Python mappings that become JSON for either ORDS or
the future native SDK.  This module validates deterministic request shape,
enums, ranges, and cross-field dependencies before a transport is selected.
Database-state checks (for example, whether a table exists) remain in PL/SQL.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)


class IndexOrganization(str, Enum):
    """Organizations accepted by ``validate_index_params`` in PL/SQL."""

    PARTITIONS = "PARTITIONS"
    INMEMORY_GRAPH = "INMEMORY GRAPH"


class DistributeMethod(str, Enum):
    """Values accepted by the PL/SQL distribute-method validation."""

    ROWID_RANGE = "ROWID RANGE"
    SIMILARITY = "SIMILARITY"
    PARTITION = "PARTITION"
    SUBPARTITION = "SUBPARTITION"
    DISTRIBUTE = "DISTRIBUTE"
    AUTO = "AUTO"


class QuantizationType(str, Enum):
    NONE = "NONE"
    SCALAR = "SCALAR"


class IndexType(str, Enum):
    VECTOR = "vector"
    METADATA = "metadata"
    ALL = "all"


class DistanceMetric(str, Enum):
    MANHATTAN = "MANHATTAN"
    HAMMING = "HAMMING"
    DOT = "DOT"
    COSINE = "COSINE"
    EUCLIDEAN = "EUCLIDEAN"
    EUCLIDEAN_SQUARED = "EUCLIDEAN_SQUARED"
    JACCARD = "JACCARD"
    L2_SQUARED = "L2_SQUARED"


class _StrictModel(BaseModel):
    """Mirror PL/SQL JSON schemas by rejecting unknown object keys."""

    # JSON inputs represent enums as strings.  Model-wide strict mode would
    # incorrectly require callers to construct Python Enum instances, so enum
    # membership is validated normally while object shape stays strict.
    model_config = ConfigDict(extra="forbid")


class TableParams(_StrictModel):
    auto_generate_id: bool | None = None


class EmbedParams(_StrictModel):
    model: str = Field(min_length=1, max_length=128)
    embed_metadata_jsonpath: str = Field(min_length=1, max_length=128)


class DistributeParams(_StrictModel):
    distribute_method: DistributeMethod
    service_name: str | None = Field(default=None, min_length=1, max_length=128)


class MetadataIndexParams(_StrictModel):
    auto_index: bool | None = None
    include_paths: list[str] | None = None
    exclude_paths: list[str] | None = None

    @model_validator(mode="after")
    def validate_metadata_paths(self) -> "MetadataIndexParams":
        # PL/SQL supports only non-empty dot paths or "*" for metadata MVIs.
        # Array syntax such as ``tags[*]`` is explicitly rejected there.
        for parameter_name, paths in (
            ("include_paths", self.include_paths),
            ("exclude_paths", self.exclude_paths),
        ):
            for path in paths or []:
                if not path.strip() or "[" in path or "]" in path:
                    raise ValueError(
                        f"metadata_index_params.{parameter_name} must contain "
                        "non-empty paths without array syntax"
                    )

        # A wildcard on both sides gives no unambiguous metadata-index policy,
        # so PL/SQL rejects this before index reconciliation begins.
        if "*" in (self.include_paths or []) and "*" in (
            self.exclude_paths or []
        ):
            raise ValueError(
                "metadata_index_params.include_paths and exclude_paths "
                "cannot both contain '*'"
            )
        return self


class VectorIndexParams(_StrictModel):
    auto_index: bool | None = None
    organization: IndexOrganization | None = None
    distance_metric: DistanceMetric | None = None
    accuracy: int | None = Field(default=None, ge=0, le=100)
    quantization_type: QuantizationType | None = None
    compression_ratio: int | None = None
    online_build: bool | None = None
    distribute_params: DistributeParams | None = None
    advanced_params: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_dependencies(self) -> "VectorIndexParams":
        # PL/SQL uses PARTITIONS when organization is omitted.  Cross-field
        # validation must use that effective value, not merely the raw input.
        organization = self.organization or IndexOrganization.PARTITIONS

        # When distribute_params is not present reject the request as
        # it would otherwise reach PL/SQL without a valid method.
        if (
            organization == IndexOrganization.INMEMORY_GRAPH
            and self.distribute_params is None
        ):
            raise ValueError(
                "vector_index_params.distribute_params cannot be None for "
                "organization 'INMEMORY GRAPH'; it must contain a valid "
                "distribute_method. Valid values are: "
                + ", ".join(f"'{method.value}'" for method in DistributeMethod)
            )

        # Distribution is implemented by the HNSW / INMEMORY GRAPH path.  IVF
        # PARTITIONS indexes must not receive a distribute_params object.
        if (
            self.distribute_params is not None
            and organization != IndexOrganization.INMEMORY_GRAPH
        ):
            raise ValueError(
                "vector_index_params.distribute_params is supported only for "
                "organization 'INMEMORY GRAPH'"
            )

        # Online index construction is likewise an HNSW-only capability.
        if (
            self.online_build is True
            and organization != IndexOrganization.INMEMORY_GRAPH
        ):
            raise ValueError(
                "vector_index_params.online_build is supported only for "
                "organization 'INMEMORY GRAPH'"
            )

        # SCALAR quantization and its compression ratio are a pair in PL/SQL:
        # neither setting is meaningful without the other.
        if self.quantization_type == QuantizationType.SCALAR:
            if self.compression_ratio is None:
                raise ValueError(
                    "vector_index_params.compression_ratio is required when "
                    "quantization_type is 'SCALAR'"
                )
            if self.compression_ratio not in {2, 4, 8}:
                raise ValueError(
                    "vector_index_params.compression_ratio must be one of 2, 4, or 8"
                )
        elif self.compression_ratio is not None:
            raise ValueError(
                "vector_index_params.compression_ratio requires "
                "quantization_type 'SCALAR'"
            )

        # advanced_params has two disjoint schemas.  Selecting IVF exposes
        # only partitions; selecting HNSW exposes graph-construction controls.
        if self.advanced_params is not None:
            if organization == IndexOrganization.PARTITIONS:
                _validate_ivf_advanced_params(self.advanced_params)
            else:
                _validate_hnsw_advanced_params(self.advanced_params)
        return self


class IndexParams(_StrictModel):
    vector_index_params: VectorIndexParams | None = None
    metadata_index_params: MetadataIndexParams | None = None
    parallel_creation: int | None = Field(default=None, ge=1)


class IndexActionParams(IndexParams):
    """The rebuild action adds the PL/SQL-only ``index_type`` selector."""

    index_type: IndexType | None = None


class LegacyIndexParams(_StrictModel):
    """Older flat vector-index request shape still accepted by PL/SQL."""

    indexing: str | None = None
    organization: IndexOrganization | None = None
    distance_metric: DistanceMetric | None = None
    distance: DistanceMetric | None = None
    accuracy: int | None = Field(default=None, ge=0, le=100)
    quantization_type: QuantizationType | None = None
    compression_ratio: int | None = None
    distribute_params: DistributeParams | None = None
    advanced_params: dict[str, Any] | None = None
    parallel_creation: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_legacy_dependencies(self) -> "LegacyIndexParams":
        if self.indexing is not None and self.indexing.lower() not in {
            "auto",
            "manual",
        }:
            raise ValueError("indexing must be one of AUTO or MANUAL")
        if (
            self.distance_metric is not None
            and self.distance is not None
            and self.distance_metric != self.distance
        ):
            raise ValueError("distance and distance_metric must match")
        return self


class QueryBy(_StrictModel):
    text: str | None = None
    id: str | None = None
    vector: list[float] | None = None

    @model_validator(mode="after")
    def validate_single_mode(self) -> "QueryBy":
        # Search resolves exactly one query source.  Sending multiple modes is
        # ambiguous, while sending none gives the database nothing to resolve.
        modes = sum(
            value is not None for value in (self.text, self.id, self.vector)
        )
        if modes != 1:
            raise ValueError(
                "query_by must contain exactly one of text, id, or vector"
            )
        return self


class QueryAdvancedParams(_StrictModel):
    rescore_factor: int | None = Field(default=None, ge=1, le=100)


class QueryAdvancedOptions(_StrictModel):
    distance_metric: DistanceMetric | None = None
    accuracy: int | None = Field(default=None, ge=0, le=100)
    advanced_params: QueryAdvancedParams | None = None
    idx_parameters: dict[str, Any] | None = None


class RerankModelParams(_StrictModel):
    top_n: int | None = Field(default=None, gt=0)


def _validate_ivf_advanced_params(value: Mapping[str, Any]) -> None:
    """Validate the organization-specific advanced options for IVF."""

    class IVFAdvancedParams(_StrictModel):
        partitions: int | None = Field(default=None, ge=1, le=10_000_000)

    try:
        IVFAdvancedParams.model_validate(value)
    except ValidationError as validation_error:
        # Prefix nested Pydantic locations so the public error identifies the
        # JSON container the caller must correct.
        raise ValueError(
            f"vector_index_params.advanced_params is invalid: {validation_error}"
        ) from validation_error


def _validate_hnsw_advanced_params(value: Mapping[str, Any]) -> None:
    """Validate the organization-specific advanced options for HNSW."""

    class HNSWAdvancedParams(_StrictModel):
        neighbors: int | None = Field(default=None, ge=1, le=2048)
        efConstruction: int | None = Field(default=None, ge=1, le=65535)
        rescore_factor: int | None = Field(default=None, ge=1, le=100)
        algorithm: str | None = None

        @model_validator(mode="after")
        def validate_algorithm(self) -> "HNSWAdvancedParams":
            if (
                self.algorithm is not None
                and self.algorithm != "uniform_quantization"
            ):
                raise ValueError("algorithm must be 'uniform_quantization'")
            return self

    try:
        HNSWAdvancedParams.model_validate(value)
    except ValidationError as validation_error:
        # Keep the same public JSON path for graph-specific nested failures.
        raise ValueError(
            f"vector_index_params.advanced_params is invalid: {validation_error}"
        ) from validation_error


def _require_mapping(value: Any, parameter_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{parameter_name} must be a JSON object")
    return value


def validate_table_params(value: Any) -> None:
    TableParams.model_validate(_require_mapping(value, "table_params"))


def validate_embed_params(value: Any) -> None:
    EmbedParams.model_validate(_require_mapping(value, "embed_params"))


def validate_index_params(value: Any) -> None:
    params = _require_mapping(value, "index_params")
    if "vector_index_params" in params or "metadata_index_params" in params:
        IndexParams.model_validate(params)
        return

    # The package converts legacy flat parameters to the current nested shape
    # before applying the same dependency rules.  Do the conversion on a new
    # dictionary only; the decorator must never rewrite the caller's request.
    legacy = LegacyIndexParams.model_validate(params)
    vector_params: dict[str, Any] = {}
    if legacy.indexing is not None:
        vector_params["auto_index"] = legacy.indexing.lower() == "auto"
    for key in (
        "organization",
        "accuracy",
        "quantization_type",
        "compression_ratio",
        "distribute_params",
        "advanced_params",
    ):
        value = getattr(legacy, key)
        if value is not None:
            vector_params[key] = value
    distance = legacy.distance_metric or legacy.distance
    if distance is not None:
        vector_params["distance_metric"] = distance
    current: dict[str, Any] = {}
    if vector_params:
        current["vector_index_params"] = vector_params
    if legacy.parallel_creation is not None:
        current["parallel_creation"] = legacy.parallel_creation
    IndexParams.model_validate(current)


def validate_rebuild_index_params(value: Any) -> None:
    raw_params = _require_mapping(value, "index_params")
    if (
        "vector_index_params" not in raw_params
        and "metadata_index_params" not in raw_params
    ):
        # Action APIs preserve the flat payload's optional index_type selector
        # while converting the remaining legacy fields before validation.
        index_type = raw_params.get("index_type")
        if index_type is not None:
            IndexType(index_type)
        validate_index_params(
            {
                key: item
                for key, item in raw_params.items()
                if key != "index_type"
            }
        )
        return

    params = IndexActionParams.model_validate(raw_params)
    # Rebuild uses existing metadata indexes; it may select paths, but PL/SQL
    # rejects metadata auto_index because that flag only belongs to creation.
    if (
        params.metadata_index_params
        and params.metadata_index_params.auto_index is not None
    ):
        raise ValueError(
            "metadata_index_params.auto_index is not supported for rebuild_index"
        )


def validate_query_by(value: Any) -> None:
    QueryBy.model_validate(_require_mapping(value, "query_by"))


def validate_query_advanced_options(value: Any) -> None:
    QueryAdvancedOptions.model_validate(
        _require_mapping(value, "advanced_options")
    )


def validate_positive_top_k(value: Any) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
    ):
        raise ValueError("top_k must be greater than zero")


def validate_list_vectors_arguments(arguments: Mapping[str, Any]) -> None:
    limit = arguments.get("limit")
    offset = arguments.get("offset")
    ids = arguments.get("ids")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")
    if offset is not None and (
        isinstance(offset, bool)
        or not isinstance(offset, (int, float))
        or offset < 0
    ):
        raise ValueError("offset must be greater than or equal to zero")
    if ids is not None and (
        not isinstance(ids, list)
        or not all(isinstance(item, str) for item in ids)
    ):
        raise ValueError("ids must be a JSON array of strings")


def validate_rerank_model_params(value: Any) -> None:
    RerankModelParams.model_validate(_require_mapping(value, "model_params"))


ParameterValidator = Any


OPERATION_PARAMETER_VALIDATORS: dict[str, dict[str, ParameterValidator]] = {
    "create_vector_table": {
        "embed_params": validate_embed_params,
        "index_params": validate_index_params,
    },
    "create_index": {"index_params": validate_index_params},
    "rebuild_index": {"index_params": validate_rebuild_index_params},
    "query": {
        "query_by": validate_query_by,
        "top_k": validate_positive_top_k,
        "advanced_options": validate_query_advanced_options,
    },
    "rerank": {"model_params": validate_rerank_model_params},
}


def validate_operation_arguments(
    operation: str, arguments: Mapping[str, Any]
) -> None:
    """Validate JSON parameters and operation-level scalar dependencies."""
    for parameter_name, validator in OPERATION_PARAMETER_VALIDATORS.get(
        operation, {}
    ).items():
        value = arguments.get(parameter_name)
        # A missing value and explicit None both map to PL/SQL DEFAULT NULL
        # where applicable, so no local JSON validation is needed in that case.
        if value is not None:
            validator(value)

    if operation == "list_vectors":
        validate_list_vectors_arguments(arguments)


__all__ = [
    "OPERATION_PARAMETER_VALIDATORS",
    "validate_operation_arguments",
]
