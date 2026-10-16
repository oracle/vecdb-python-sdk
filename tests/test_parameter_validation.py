from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from oracle_vecdb.parameter_validation import (
    MetadataIndexParams,
    VectorIndexParams,
    validate_embed_params,
    validate_index_params,
    validate_list_vectors_arguments,
    validate_operation_arguments,
    validate_positive_top_k,
    validate_query_advanced_options,
    validate_query_by,
    validate_rebuild_index_params,
    validate_rerank_model_params,
    validate_table_params,
)


@pytest.mark.parametrize(
    "field, value",
    [
        ("include_paths", [" "]),
        ("exclude_paths", ["tags[*]"]),
        ("include_paths", ["tags]"]),
    ],
)
def test_metadata_index_rejects_empty_or_array_paths(field, value):
    with pytest.raises(ValidationError):
        MetadataIndexParams.model_validate({field: value})


def test_metadata_index_rejects_conflicting_wildcards():
    with pytest.raises(ValidationError, match="cannot both contain"):
        MetadataIndexParams.model_validate(
            {"include_paths": ["*"], "exclude_paths": ["*"]}
        )


def test_metadata_index_accepts_distinct_paths():
    MetadataIndexParams.model_validate(
        {"include_paths": ["profile.name", "*"], "exclude_paths": ["tags"]}
    )


@pytest.mark.parametrize(
    "payload, message",
    [
        (
            {
                "organization": "PARTITIONS",
                "distribute_params": {"distribute_method": "AUTO"},
            },
            "supported only",
        ),
        (
            {"organization": "PARTITIONS", "online_build": True},
            "supported only",
        ),
        (
            {"organization": "PARTITIONS", "quantization_type": "SCALAR"},
            "compression_ratio is required",
        ),
        (
            {
                "organization": "PARTITIONS",
                "quantization_type": "SCALAR",
                "compression_ratio": 3,
            },
            "one of 2, 4, or 8",
        ),
        (
            {"organization": "PARTITIONS", "compression_ratio": 2},
            "requires",
        ),
    ],
)
def test_vector_index_rejects_invalid_dependencies(payload, message):
    with pytest.raises(ValidationError, match=message):
        VectorIndexParams.model_validate(payload)


def test_vector_index_accepts_ivf_advanced_params():
    VectorIndexParams.model_validate(
        {
            "organization": "PARTITIONS",
            "advanced_params": {"partitions": 8},
        }
    )


def test_vector_index_rejects_invalid_ivf_advanced_params():
    with pytest.raises(ValidationError, match="advanced_params is invalid"):
        VectorIndexParams.model_validate(
            {"organization": "PARTITIONS", "advanced_params": {"neighbors": 4}}
        )


@pytest.mark.parametrize(
    "distribute_method",
    ["AUTO", "DISTRIBUTE"],
    ids=["auto", "distribute"],
)
def test_vector_index_accepts_hnsw_advanced_params(distribute_method):
    VectorIndexParams.model_validate(
        {
            "organization": "INMEMORY GRAPH",
            "distribute_params": {"distribute_method": distribute_method},
            "online_build": True,
            "advanced_params": {
                "neighbors": 4,
                "efConstruction": 16,
                "rescore_factor": 2,
                "algorithm": "uniform_quantization",
            },
        }
    )


@pytest.mark.parametrize("distribute_method", ["NONE", "RANDOM"])
def test_vector_index_rejects_unlisted_explicit_distribution_method(
    distribute_method,
):
    with pytest.raises(ValidationError, match="distribute_method"):
        VectorIndexParams.model_validate(
            {
                "organization": "INMEMORY GRAPH",
                "distribute_params": {"distribute_method": distribute_method},
            }
        )


@pytest.mark.parametrize(
    "include_distribution",
    [False, True],
    ids=["omitted", "explicit-null"],
)
def test_vector_index_accepts_hnsw_without_or_with_null_distribution(
    include_distribution,
):
    payload: dict[str, Any] = {"organization": "INMEMORY GRAPH"}
    if include_distribution:
        payload["distribute_params"] = None

    validated = VectorIndexParams.model_validate(payload)
    assert validated.distribute_params is None  # nosec B101
    assert (
        "distribute_params" in validated.model_fields_set
    ) is include_distribution  # nosec B101


@pytest.mark.parametrize(
    "advanced_params, message",
    [
        ({"algorithm": "unsupported"}, "algorithm must be"),
        ({"partitions": 8}, "advanced_params is invalid"),
    ],
    ids=["unsupported-algorithm", "ivf-option-for-hnsw"],
)
def test_vector_index_rejects_invalid_hnsw_advanced_params(
    advanced_params, message
):
    with pytest.raises(ValidationError, match=message):
        VectorIndexParams.model_validate(
            {
                "organization": "INMEMORY GRAPH",
                "distribute_params": {"distribute_method": "AUTO"},
                "advanced_params": advanced_params,
            }
        )


def test_validate_index_params_converts_legacy_flat_shape():
    validate_index_params(
        {
            "indexing": "AUTO",
            "organization": "PARTITIONS",
            "distance": "COSINE",
            "accuracy": 90,
            "advanced_params": {"partitions": 8},
            "parallel_creation": 2,
        }
    )
    validate_index_params({})


def test_validate_index_params_accepts_current_nested_shape():
    validate_index_params(
        {"metadata_index_params": {"include_paths": ["profile.name"]}}
    )


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"indexing": "invalid"}, "indexing must be one"),
        (
            {"distance_metric": "COSINE", "distance": "HAMMING"},
            "distance and distance_metric must match",
        ),
    ],
)
def test_validate_index_params_rejects_invalid_legacy_shape(payload, message):
    with pytest.raises(ValidationError, match=message):
        validate_index_params(payload)


def test_validate_rebuild_index_params_converts_legacy_shape():
    validate_rebuild_index_params(
        {
            "index_type": "vector",
            "organization": "PARTITIONS",
            "distance_metric": "COSINE",
            "advanced_params": {"partitions": 4},
        }
    )


def test_validate_rebuild_index_params_accepts_nested_shape():
    validate_rebuild_index_params(
        {
            "vector_index_params": {"organization": "PARTITIONS"},
            "index_type": "vector",
        }
    )


def test_validate_rebuild_index_params_rejects_metadata_auto_index():
    with pytest.raises(ValueError, match="not supported for rebuild_index"):
        validate_rebuild_index_params(
            {"metadata_index_params": {"auto_index": True}}
        )


def test_validate_rebuild_index_params_rejects_unknown_index_type():
    with pytest.raises(ValueError):
        validate_rebuild_index_params({"index_type": "unsupported"})


@pytest.mark.parametrize("value", [None, {}, {"text": "one", "id": "two"}])
def test_validate_query_by_requires_one_query_mode(value):
    with pytest.raises((ValidationError, ValueError)):
        validate_query_by(value)


def test_validate_query_and_rerank_models_accept_documented_shapes():
    validate_query_by({"vector": [0.1, 0.2]})
    validate_query_advanced_options(
        {
            "distance_metric": "COSINE",
            "accuracy": 80,
            "advanced_params": {"rescore_factor": 2},
            "idx_parameters": {"efSearch": 16},
        }
    )
    validate_rerank_model_params({"top_n": 3})


@pytest.mark.parametrize(
    "value", [True, False, None, 0, -1, 0.2, 2.5, 2.0, "3", set(), {}]
)
def test_validate_positive_top_k_rejects_non_positive_or_non_integer(value):
    """Reject booleans, floats, and values outside the positive integer range."""
    with pytest.raises(
        ValueError, match=r"top_k must be a positive integer \(>= 1\)"
    ):
        validate_positive_top_k(value)


@pytest.mark.parametrize("value", [1, 3])
def test_validate_positive_top_k_accepts_positive_integers(value):
    """Accept positive integer result counts, including the lower boundary."""
    assert validate_positive_top_k(value) is None  # nosec B101


def test_validate_list_vectors_accepts_pagination_and_ids():
    validate_list_vectors_arguments({"limit": 10, "offset": 0, "ids": ["one"]})
    validate_list_vectors_arguments({"limit": 1, "offset": 1.5})


@pytest.mark.parametrize(
    "arguments, message",
    [
        ({"limit": True}, "limit must be"),
        ({"limit": 0}, "limit must be"),
        ({"limit": 1, "offset": -1}, "offset must be"),
        ({"limit": 1, "offset": "1"}, "offset must be"),
        ({"limit": 1, "ids": ("one",)}, "ids must be"),
        ({"limit": 1, "ids": [1]}, "ids must be"),
    ],
)
def test_validate_list_vectors_rejects_invalid_arguments(arguments, message):
    with pytest.raises(ValueError, match=message):
        validate_list_vectors_arguments(arguments)


@pytest.mark.parametrize(
    "validator, name",
    [
        (validate_table_params, "table_params"),
        (validate_embed_params, "embed_params"),
        (validate_index_params, "index_params"),
        (validate_query_by, "query_by"),
        (validate_query_advanced_options, "advanced_options"),
        (validate_rerank_model_params, "model_params"),
    ],
)
def test_parameter_validators_reject_non_mapping_values(validator, name):
    with pytest.raises(ValueError, match=f"{name} must be a JSON object"):
        validator(None)


def test_validate_operation_arguments_skips_missing_optional_values():
    """Skip None for optional query fields and unknown operations."""
    validate_operation_arguments(
        "query",
        {"query_by": None, "top_k": 3, "advanced_options": None},
    )
    validate_operation_arguments("unknown_operation", {})


def test_validate_operation_arguments_rejects_none_for_required_top_k():
    """Validate required top_k even though optional query fields may be None."""
    with pytest.raises(
        ValueError, match=r"top_k must be a positive integer \(>= 1\)"
    ):
        validate_operation_arguments(
            "query",
            {"query_by": None, "top_k": None, "advanced_options": None},
        )


def test_validate_operation_arguments_dispatches_list_vectors_validation():
    validate_operation_arguments("list_vectors", {"limit": 5, "offset": 0})
    with pytest.raises(ValueError, match="limit must be"):
        validate_operation_arguments("list_vectors", {"limit": 0})
