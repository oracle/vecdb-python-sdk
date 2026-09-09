##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any, Dict, List, Tuple, cast

import pytest
import oracle_vecdb.client as client_module

from oracle_vecdb.client import OracleVecDB
from oracle_vecdb.default_settings import DefaultSettings
from oracle_vecdb.configuration import Configuration
from oracle_vecdb.data_types import UpsertVectorsResponse
from oracle_vecdb.service_protocol import VecDBServiceProtocol
from oracle_vecdb.vecdb_exception import VecDBException
from oracle_vecdb.vecdb_errors import (
    InvalidIndexJobNameFormatError,
    InvalidLoadJobNameFormatError,
    InvalidModelNameFormatError,
    InvalidTableNameFormatError,
    InvalidVectorsError,
    VectorPayloadTooLargeError,
)

VALID_HOST = "https://example.com/ords/foo/_/db-api/stable/vecdb/"


class FakeBackend:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: List[Tuple[str, Tuple[Any, ...], Dict[str, Any]]] = []
        self.api_client = object()
        self.table_api = object()
        self.index_api = object()
        self.inference_api = object()
        self.model_api = object()
        self.search_api = object()
        self.summary_api = object()
        self.vector_api = object()

    def _convert_debug_flags(self, debug_flags: Any) -> Dict[str, Any]:
        self.calls.append(("_convert_debug_flags", (debug_flags,), {}))
        return {"backend": self.name, "debug_flags": debug_flags}

    def __getattr__(self, name: str) -> Any:
        def _method(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            self.calls.append((name, args, kwargs))
            return {
                "backend": self.name,
                "method": name,
                "args": args,
                "kwargs": kwargs,
            }

        return _method


def _make_client(mocker):
    ords_backend = cast(VecDBServiceProtocol, FakeBackend("ords"))
    ords_factory = mocker.patch.object(
        client_module, "create_ords_service", return_value=ords_backend
    )
    return (
        OracleVecDB(Configuration(rest_url=VALID_HOST)),
        ords_backend,
        ords_factory,
    )


def test_convert_debug_flags_delegates_to_active_backend(mocker):
    client, active_backend, _ = _make_client(mocker)
    result = client._convert_debug_flags({"vector_index": "low"})

    assert result == {
        "backend": "ords",
        "debug_flags": {"vector_index": "low"},
    }  # nosec B101
    assert active_backend.calls == [
        ("_convert_debug_flags", ({"vector_index": "low"},), {})
    ]  # nosec B101


def test_query_forwards_output_selector_to_active_backend(mocker):
    client, active_backend, _ = _make_client(mocker)

    mocker.patch.object(
        active_backend,
        "query",
        return_value={"items": []},
    )
    client.query(
        table_name="docs",
        query_by={"text": "hi"},
        top_k=3,
        output_selector=["category", "price"],
    )

    active_backend.query.assert_called_once_with(  # type: ignore[attr-defined]
        table_name="docs",
        query_by={"text": "hi"},
        top_k=3,
        filters=None,
        advanced_options=None,
        include_vectors=False,
        output_selector=["category", "price"],
        debug_flags=None,
    )


def test_common_spec_applies_defaults_for_omitted_arguments(mocker):
    """Verify omitted facade arguments are populated from DefaultSettings.

    This test currently uses the mocked ORDS backend, but it verifies the
    transport-agnostic OracleVecDB facade contract that a native backend must
    also receive.  ``table_params`` and ``include_vectors`` are intentionally
    omitted by the caller and must therefore be obtained from DefaultSettings.
    """
    client, active_backend, _ = _make_client(mocker)

    client.create_vector_table(name="docs")
    client.query(
        table_name="docs",
        query_by={"text": "hi"},
        top_k=3,
    )

    assert active_backend.calls[0] == (  # nosec B101
        "create_vector_table",
        (),
        {
            "name": "docs",
            "comment": None,
            "annotations": None,
            "table_params": {"auto_generate_id": False},
            "embed_params": None,
            "index_params": None,
            "debug_flags": None,
        },
    )
    assert active_backend.calls[1][2]["include_vectors"] is False  # nosec B101


def test_common_spec_rejects_graph_index_without_distribution_method(mocker):
    client, active_backend, _ = _make_client(mocker)

    with pytest.raises(
        VecDBException,
        match="distribute_params cannot be None.*INMEMORY GRAPH",
    ):
        client.create_index(
            table_name="docs",
            index_params={
                "vector_index_params": {"organization": "INMEMORY GRAPH"}
            },
        )

    assert active_backend.calls == []  # nosec B101


def test_common_spec_rejects_graph_index_with_null_distribution_params(mocker):
    client, active_backend, _ = _make_client(mocker)

    with pytest.raises(
        VecDBException,
        match="distribute_params cannot be None.*INMEMORY GRAPH",
    ):
        client.create_index(
            table_name="docs",
            index_params={
                "vector_index_params": {
                    "organization": "INMEMORY GRAPH",
                    "distribute_params": None,
                }
            },
        )

    assert active_backend.calls == []  # nosec B101


def test_common_spec_honors_scalar_and_nested_caller_overrides(mocker):
    """Verify DefaultSettings defaults do not override explicit caller values.

    The mocked backend is ORDS, while the behavior belongs to the shared
    facade contract and applies equally to a future native backend.  DefaultSettings
    supplies missing nested ``table_params`` keys, but explicit caller values
    such as ``include_vectors=True`` always take precedence.
    """
    client, active_backend, _ = _make_client(mocker)

    client.create_vector_table(
        name="docs",
        table_params={"custom_option": {"source": "caller"}},
    )
    client.query(
        table_name="docs",
        query_by={"text": "hi"},
        top_k=3,
        include_vectors=True,
    )

    assert active_backend.calls[0][2]["table_params"] == {  # nosec B101
        "auto_generate_id": False,
        "custom_option": {"source": "caller"},
    }
    assert active_backend.calls[1][2]["include_vectors"] is True  # nosec B101


def test_common_spec_honors_explicit_none_and_ignores_unknown_operations(
    mocker,
):
    """Verify explicit ``None`` is preserved and unknown specs are a no-op.

    This uses the mocked ORDS backend to exercise facade behavior that must
    remain transport-neutral for native calls.  Only omitted arguments are
    obtained from DefaultSettings; explicitly passed ``None`` and operations with
    no DefaultSettings entry must reach the backend unchanged.

    This test specifically verifies that ``DefaultSettings`` does not override anything:

    - ``table_params=None`` was explicitly supplied, so it remains ``None``.
    - ``include_vectors=None`` was explicitly supplied, so it remains ``None``.
    - ``list_models()`` has no ``DefaultSettings`` entry, so its ``limit`` and ``offset`` remain their Python defaults of ``None``.
    """
    client, active_backend, _ = _make_client(mocker)

    client.create_vector_table(name="docs", table_params=None)
    client.query(
        table_name="docs",
        query_by={"text": "hi"},
        top_k=3,
        include_vectors=None,
    )
    client.list_models()

    assert active_backend.calls[0][2]["table_params"] is None  # nosec B101
    assert active_backend.calls[1][2]["include_vectors"] is None  # nosec B101
    assert active_backend.calls[2] == (  # nosec B101
        "list_models",
        (),
        {"limit": None, "offset": None},
    )
    assert (
        DefaultSettings.get_default_args_for("list_models") == {}
    )  # nosec B101


@pytest.mark.parametrize(
    "method_name",
    [
        "list_vector_tables",
        "list_vector_load_jobs",
        "list_index_jobs",
        "list_models",
    ],
)
def test_collection_pagination_is_forwarded(mocker, method_name):
    client, active_backend, _ = _make_client(mocker)
    mocker.patch.object(active_backend, method_name, return_value={"items": []})

    getattr(client, method_name)(limit=7, offset=14)

    getattr(active_backend, method_name).assert_called_once_with(
        limit=7, offset=14
    )


def test_upsert_vectors_automatically_batches_large_payloads(mocker):
    client, active_backend, _ = _make_client(mocker)
    response = UpsertVectorsResponse(upserted_count=3)
    mocker.patch.object(active_backend, "upsert_vectors", return_value=response)
    vectors = [{"id": "v1"}, {"id": "v2"}, {"id": "v3"}]

    result = client.upsert_vectors(table_name="docs", vectors=vectors)

    assert result.upserted_count == 3  # nosec B101
    active_backend.upsert_vectors.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.parametrize("vectors", [None, []])
def test_upsert_vectors_rejects_missing_or_empty_vectors(mocker, vectors):
    client, active_backend, _ = _make_client(mocker)

    with pytest.raises(InvalidVectorsError, match="[Aa]t least one vector"):
        client.upsert_vectors(table_name="docs", vectors=vectors)

    assert not active_backend.calls  # nosec B101


def test_upsert_vectors_aggregates_size_bounded_batches(mocker):
    client, active_backend, _ = _make_client(mocker)
    responses = [UpsertVectorsResponse(upserted_count=2)]
    mocker.patch.object(active_backend, "upsert_vectors", side_effect=responses)
    vectors = [{"id": f"v{i}"} for i in range(5)]

    result = client.upsert_vectors(table_name="docs", vectors=vectors)

    assert result.upserted_count == 2  # nosec B101
    assert active_backend.upsert_vectors.call_count == 1  # nosec B101
    assert vectors == [{"id": f"v{i}"} for i in range(5)]  # nosec B101


def test_upsert_vectors_under_limit_uses_one_request(mocker):
    client, active_backend, _ = _make_client(mocker)
    response = UpsertVectorsResponse(upserted_count=2)
    mocker.patch.object(active_backend, "upsert_vectors", return_value=response)
    vectors = [{"id": "one"}, {"id": "two"}]

    result = client.upsert_vectors(table_name="docs", vectors=vectors)

    assert result.upserted_count == 2  # nosec B101
    active_backend.upsert_vectors.assert_called_once_with(  # type: ignore[attr-defined]
        table_name="docs", vectors=vectors, debug_flags=None
    )


def test_upsert_vectors_under_limit_does_not_enter_batch_helper(mocker):
    client, active_backend, _ = _make_client(mocker)
    response = UpsertVectorsResponse(upserted_count=1)
    mocker.patch.object(active_backend, "upsert_vectors", return_value=response)
    helper = mocker.patch.object(client, "_upsert_vectors_in_batches")

    result = client.upsert_vectors(table_name="docs", vectors=[{"id": "small"}])

    assert result is response  # nosec B101
    helper.assert_not_called()


def test_upsert_vectors_splits_by_serialized_payload_size(mocker):
    client, active_backend, _ = _make_client(mocker)
    mocker.patch.object(
        active_backend,
        "upsert_vectors",
        side_effect=[UpsertVectorsResponse(upserted_count=1)] * 2,
    )
    vectors = [
        {"id": str(i), "metadata": {"text": "x" * 16_000_000}} for i in range(3)
    ]

    result = client.upsert_vectors(table_name="docs", vectors=vectors)

    assert result.upserted_count == 2  # nosec B101
    assert active_backend.upsert_vectors.call_count == 2  # nosec B101


def test_upsert_vectors_rejects_single_oversized_vector(mocker):
    client, active_backend, _ = _make_client(mocker)
    vector = {"id": "huge", "metadata": {"text": "x" * (32 * 1024 * 1024)}}

    with pytest.raises(VectorPayloadTooLargeError, match="single vector"):
        client.upsert_vectors(table_name="docs", vectors=[vector])

    assert not active_backend.calls  # nosec B101


def test_upsert_vectors_rejects_vector_that_exceeds_safe_batch_limit(
    mocker,
):
    client, active_backend, _ = _make_client(mocker)
    mocker.patch.object(client_module, "_MAX_UPSERT_BATCH_BYTES", 80)
    vector = {"id": "near-limit", "metadata": {"text": "x" * 60}}

    with pytest.raises(VectorPayloadTooLargeError):
        client.upsert_vectors(table_name="docs", vectors=[vector])

    assert not active_backend.calls  # nosec B101


def test_upsert_vector_json_size_supports_typed_model():
    class TypedVector:
        def model_dump(self, mode):
            assert mode == "json"  # nosec B101
            return {"id": "typed"}

    assert OracleVecDB._upsert_vector_json_size(TypedVector()) > 0  # nosec B101


def test_upsert_vector_json_size_rejects_non_serializable_value():
    with pytest.raises(TypeError, match="JSON-serializable"):
        OracleVecDB._upsert_vector_json_size({"value": object()})


def test_upsert_vectors_stops_after_batch_failure(mocker):
    client, active_backend, _ = _make_client(mocker)
    failure = RuntimeError("batch failed")
    mocker.patch.object(
        active_backend,
        "upsert_vectors",
        side_effect=[UpsertVectorsResponse(upserted_count=2), failure],
    )
    vectors = [
        {"id": f"v{i}", "metadata": {"text": "x" * 16_000_000}}
        for i in range(3)
    ]

    with pytest.raises(RuntimeError, match="batch failed"):
        client.upsert_vectors(table_name="docs", vectors=vectors)

    assert active_backend.upsert_vectors.call_count == 2  # nosec B101


def test_client_routes_to_ords_service_when_rest_url_is_configured(mocker):
    _, _, ords_factory = _make_client(mocker)

    client = OracleVecDB(Configuration(rest_url=VALID_HOST))

    assert (
        client._get_active_service() is ords_factory.return_value
    )  # nosec B101
    ords_factory.assert_called_once()


def test_proxied_service_attribute_access_and_assignment(mocker):
    client, active_backend, _ = _make_client(mocker)
    replacement_api = object()

    assert client.api_client is active_backend.api_client  # nosec B101

    client.api_client = replacement_api

    assert active_backend.api_client is replacement_api  # nosec B101


def test_unknown_attribute_raises_attribute_error(mocker):
    client, _, _ = _make_client(mocker)

    with pytest.raises(AttributeError, match="does_not_exist"):
        _ = client.does_not_exist


@pytest.mark.parametrize(
    "backend_kind,method_name,args,kwargs",
    [
        ("ords", "describe_vector_database", (), {}),
        ("ords", "list_vector_tables", (), {}),
        ("ords", "create_vector_table", (), {"name": "docs"}),
        ("ords", "describe_vector_table", ("docs",), {}),
        ("ords", "drop_vector_table", ("docs",), {}),
        (
            "ords",
            "update_vector_table_annotation",
            ("docs", "new"),
            {"annotations": {"tier": "gold"}},
        ),
        (
            "ords",
            "generate_embedding",
            (),
            {"model_name": "embedder", "inputs": ["hello"]},
        ),
        (
            "ords",
            "upsert_vectors",
            (),
            {"table_name": "docs", "vectors": [{"id": "v1"}]},
        ),
        (
            "ords",
            "list_vectors",
            (),
            {"table_name": "docs", "ids": ["v1"]},
        ),
        (
            "ords",
            "delete_vectors",
            (),
            {"table_name": "docs", "ids": ["v1"]},
        ),
        (
            "ords",
            "load_vectors",
            (),
            {"table_name": "docs", "url": "https://example.com/data.json"},
        ),
        ("ords", "list_vector_load_jobs", (), {}),
        ("ords", "describe_vector_load_job", ("job1",), {}),
        ("ords", "get_vector_load_job_log", ("job1",), {}),
        (
            "ords",
            "query",
            (),
            {
                "table_name": "docs",
                "query_by": {"text": "hi"},
                "top_k": 3,
                "output_selector": None,
            },
        ),
        (
            "ords",
            "rerank",
            (),
            {
                "query": "what is vecdb",
                "documents": ["doc1", "doc2"],
                "model_name": "reranker",
            },
        ),
        ("ords", "create_index", (), {"table_name": "docs"}),
        ("ords", "list_index_jobs", (), {}),
        ("ords", "describe_index_job", ("job1",), {}),
        ("ords", "get_index_job_log", ("job1",), {}),
        ("ords", "rebuild_index", (), {"table_name": "docs"}),
        ("ords", "describe_index", ("docs",), {}),
        ("ords", "drop_index", ("docs",), {}),
        ("ords", "list_models", (), {}),
        (
            "ords",
            "load_model",
            (),
            {
                "model_name": "embedder",
                "url": "https://example.com/model.onnx",
            },
        ),
        ("ords", "describe_model", ("embedder",), {}),
        ("ords", "drop_model", ("embedder",), {}),
    ],
)
def test_facade_delegates_public_methods_to_active_backend(
    mocker, backend_kind, method_name, args, kwargs
):
    client, active_backend, _ = _make_client(mocker)
    if method_name == "get_vector_load_job_log":
        mocker.patch.object(
            client,
            "describe_vector_load_job",
            return_value=SimpleNamespace(state="SUCCEEDED"),
        )
    elif method_name == "get_index_job_log":
        mocker.patch.object(
            client,
            "describe_index_job",
            return_value=SimpleNamespace(state="SUCCEEDED"),
        )
    signature = inspect.signature(getattr(OracleVecDB, method_name))
    bound = signature.bind(client, *args, **kwargs)
    bound.apply_defaults()
    expected_kwargs = dict(bound.arguments)
    expected_kwargs.pop("self", None)
    if method_name == "create_vector_table":
        expected_kwargs["table_params"] = {"auto_generate_id": False}
    elif method_name == "query":
        expected_kwargs["include_vectors"] = False
    result = getattr(client, method_name)(*args, **kwargs)

    assert result == {
        "backend": backend_kind,
        "method": method_name,
        "args": (),
        "kwargs": expected_kwargs,
    }  # nosec B101
    assert active_backend.calls == [
        (method_name, (), expected_kwargs)
    ]  # nosec B101


@pytest.mark.parametrize(
    "method_name,args,kwargs,error_type",
    [
        (
            "create_vector_table",
            (),
            {"name": "  "},
            InvalidTableNameFormatError,
        ),
        (
            "describe_vector_table",
            ("  ",),
            {},
            InvalidTableNameFormatError,
        ),
        ("drop_vector_table", ("  ",), {}, InvalidTableNameFormatError),
        (
            "update_vector_table_annotation",
            ("  ",),
            {"annotations": {"tier": "gold"}},
            InvalidTableNameFormatError,
        ),
        (
            "upsert_vectors",
            (),
            {"table_name": "  ", "vectors": []},
            InvalidTableNameFormatError,
        ),
        ("list_vectors", (), {"table_name": "  "}, InvalidTableNameFormatError),
        (
            "delete_vectors",
            (),
            {"table_name": "  ", "ids": ["v1"]},
            InvalidTableNameFormatError,
        ),
        (
            "load_vectors",
            (),
            {"table_name": "  ", "url": "https://example.com/data.json"},
            InvalidTableNameFormatError,
        ),
        (
            "query",
            (),
            {"table_name": "  ", "query_by": {"text": "hi"}, "top_k": 3},
            InvalidTableNameFormatError,
        ),
        ("create_index", (), {"table_name": "  "}, InvalidTableNameFormatError),
        (
            "rebuild_index",
            (),
            {"table_name": "  "},
            InvalidTableNameFormatError,
        ),
        ("describe_index", ("  ",), {}, InvalidTableNameFormatError),
        ("drop_index", ("  ",), {}, InvalidTableNameFormatError),
        (
            "generate_embedding",
            (),
            {"model_name": "  ", "inputs": ["hi"]},
            InvalidModelNameFormatError,
        ),
        (
            "load_model",
            (),
            {"model_name": "  ", "url": "https://example.com/model.onnx"},
            InvalidModelNameFormatError,
        ),
        ("describe_model", ("  ",), {}, InvalidModelNameFormatError),
        ("drop_model", ("  ",), {}, InvalidModelNameFormatError),
        (
            "describe_vector_load_job",
            ("  ",),
            {},
            InvalidLoadJobNameFormatError,
        ),
        (
            "get_vector_load_job_log",
            ("  ",),
            {},
            InvalidLoadJobNameFormatError,
        ),
        (
            "describe_index_job",
            ("  ",),
            {},
            InvalidIndexJobNameFormatError,
        ),
        (
            "get_index_job_log",
            ("  ",),
            {},
            InvalidIndexJobNameFormatError,
        ),
    ],
)
def test_facade_rejects_invalid_resource_names(
    mocker, method_name, args, kwargs, error_type
):
    client, active_backend, _ = _make_client(mocker)

    with pytest.raises(VecDBException) as exception:
        getattr(client, method_name)(*args, **kwargs)

    assert exception.value.is_original_exception(error_type)  # nosec B101

    assert active_backend.calls == []  # nosec B101


@pytest.mark.parametrize(
    "method_name,error_type",
    [
        ("describe_vector_table", InvalidTableNameFormatError),
        ("describe_model", InvalidModelNameFormatError),
        ("describe_vector_load_job", InvalidLoadJobNameFormatError),
        ("describe_index_job", InvalidIndexJobNameFormatError),
    ],
)
@pytest.mark.parametrize(
    "unsafe_name", [b"docs", "\x00", "docs\x00old", 'docs"old']
)
def test_facade_rejects_unsafe_resource_name_values(
    mocker, method_name, error_type, unsafe_name
):
    """Reject names that cannot safely retain a resource's text identity."""
    client, active_backend, _ = _make_client(mocker)

    with pytest.raises(VecDBException) as exception:
        getattr(client, method_name)(unsafe_name)

    assert exception.value.is_original_exception(error_type)  # nosec B101
    assert active_backend.calls == []  # nosec B101


@pytest.mark.parametrize(
    "method_name,resource_parameter",
    [
        ("describe_vector_table", "name"),
        ("describe_model", "model_name"),
        ("describe_vector_load_job", "load_job_name"),
        ("describe_index_job", "index_job_name"),
    ],
)
@pytest.mark.parametrize(
    "resource_name",
    [
        "my-table",
        "my.table",
        "my table",
        "1st_name",
        "Delta_名",
        "my$name",
        "my#name",
        "my/name",
        "my'name",
    ],
)
def test_facade_delegates_database_defined_resource_name_grammar(
    mocker, method_name, resource_parameter, resource_name
):
    """Leave database-specific characters and identifier rules to VecDB."""
    client, active_backend, _ = _make_client(mocker)

    getattr(client, method_name)(resource_name)

    assert active_backend.calls == [
        (method_name, (), {resource_parameter: resource_name})
    ]  # nosec B101


@pytest.mark.parametrize(
    "method_name,kwargs",
    [
        ("create_vector_table", {}),
        ("describe_vector_table", {}),
        ("drop_vector_table", {}),
        ("create_index", {}),
        ("drop_index", {}),
        ("load_model", {"url": "http://example.com/model"}),
        ("drop_model", {}),
        ("generate_embedding", {"inputs": ["text"]}),
        ("query", {"query_by": {"text": "hi"}, "top_k": 5}),
        ("load_vectors", {"url": "http://example.com/data"}),
        ("delete_vectors", {"ids": ["id1"]}),
    ],
)
def test_public_methods_missing_required_args(method_name, kwargs):
    client = OracleVecDB(Configuration(rest_url=VALID_HOST))
    method = getattr(client, method_name)

    with pytest.raises(TypeError):
        method(**kwargs)
