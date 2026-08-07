##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

from __future__ import annotations

from typing import Any, Dict

import pytest
import oracle_vecdb.ords as ords_module
from pydantic import ValidationError
from oracle_vecdb.configuration import Configuration
from oracle_vecdb.ords import ORDSService, create_ords_service
from oracle_vecdb.ords_response_handlers import ORDSResponseHandler
from oracle_vecdb.vecdb_exception import VecDBException

VALID_HOST = "https://example.com/ords/foo/_/db-api/stable/vecdb/"


class TransportError(Exception):
    """Transport-shaped error used to test the generic retry contract."""

    def __init__(self, *, status: int, reason: str) -> None:
        self.status = status
        self.reason = reason
        super().__init__(reason)


def test_sdk_api_client_uses_configured_default_timeout(mocker):
    config = Configuration(rest_url=VALID_HOST, timeout=12.5)
    client = ords_module._CustomApiClient(config)
    request = mocker.Mock(return_value=mocker.Mock())
    client.rest_client.request = request

    client.call_api("GET", "/health")

    assert request.call_args.kwargs["_request_timeout"] == 12.5  # nosec B101


def test_sdk_api_client_preserves_per_request_timeout(mocker):
    config = Configuration(rest_url=VALID_HOST, timeout=12.5)
    client = ords_module._CustomApiClient(config)
    request = mocker.Mock(return_value=mocker.Mock())
    client.rest_client.request = request

    client.call_api("GET", "/health", _request_timeout=(1.0, 2.0))

    assert request.call_args.kwargs["_request_timeout"] == (
        1.0,
        2.0,
    )  # nosec B101


class RecordingApi:
    def __init__(self, returns: Dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.returns = returns or {}

    def __getattr__(self, name: str):
        def _method(*args: Any, **kwargs: Any) -> Any:
            self.calls.append((name, args, kwargs))
            return self.returns.get(name, {"message": f"{name} ok"})

        return _method


def _make_service() -> Any:
    service: Any = ORDSService.__new__(ORDSService)
    service.config = None
    service.api_client = None
    service.summary_api = RecordingApi({"describe_vector_database": "summary"})
    service.table_api = RecordingApi({"list_vector_tables": "tables"})
    service.inference_api = RecordingApi(
        {
            "generate_embedding": "embedding",
            "rerank": [{"index": 0, "score": 0.9}],
        }
    )
    service.vector_api = RecordingApi(
        {
            "upsert_vectors": "upserted",
            "list_vectors": "vectors",
            "load_vectors": "load-job",
            "list_vector_load_jobs": "load-jobs",
            "describe_vector_load_job": "load-job-description",
            "get_vector_load_job_log": "load-job-log",
        }
    )
    service.search_api = RecordingApi(
        {"query_vectors": {"results": [{"id": "v1", "distance": 0.2}]}}
    )
    service.index_api = RecordingApi(
        {
            "create_index": "index-job",
            "list_index_jobs": "index-jobs",
            "describe_index_job": "index-job-description",
            "get_index_job_log": "index-job-log",
            "describe_index": {"Index Status": "READY"},
        }
    )
    service.model_api = RecordingApi(
        {
            "list_models": "models",
            "load_model": "loaded-model",
            "describe_model": "model-description",
        }
    )
    return service


def _first_positional_request(api: RecordingApi, method_name: str) -> Any:
    for call_name, args, _ in api.calls:
        if call_name == method_name:
            return args[0]
    raise AssertionError(f"{method_name} was not called")


def _first_keyword_request(
    api: RecordingApi, method_name: str, keyword: str
) -> Any:
    for call_name, _, kwargs in api.calls:
        if call_name == method_name:
            return kwargs[keyword]
    raise AssertionError(f"{method_name} was not called")


def test_response_handler_descriptor_and_normalized_exception():
    class Endpoint:
        config = None

        @ORDSResponseHandler
        def execute(self):
            raise VecDBException(status=400, reason="invalid")

    endpoint = Endpoint()
    assert (
        Endpoint.execute.__get__(None, Endpoint) is Endpoint.execute
    )  # nosec B101
    with pytest.raises(VecDBException, match="VECDB-"):
        endpoint.execute()


def test_response_handler_redispatches_non_retryable_error():
    class Endpoint:
        def __init__(self):
            self.config = Configuration(rest_url=VALID_HOST)
            self.config.ords_settings.max_retry_count_error_429 = 1
            self.calls = 0

        @ORDSResponseHandler
        def execute(self):
            self.calls += 1
            if self.calls == 1:
                raise TransportError(status=429, reason="retry")
            raise TransportError(status=400, reason="bad request")

    endpoint = Endpoint()
    with pytest.raises(TransportError, match="bad request"):
        endpoint.execute()
    assert endpoint.calls == 2  # nosec B101


def test_create_ords_service_wires_generated_api_delegates(monkeypatch):
    class FakeApiClient:
        def __init__(self, config):
            self.config = config

    class FakeGeneratedApi:
        def __init__(self, api_client):
            self.api_client = api_client

    monkeypatch.setattr(ords_module, "_CustomApiClient", FakeApiClient)
    for name in (
        "VectorDatabaseVectorTablesApi",
        "VectorDatabaseVectorIndexesApi",
        "VectorDatabaseInferenceOperationsApi",
        "VectorDatabaseModelsApi",
        "VectorDatabaseVectorSearchApi",
        "VectorDatabaseSummaryApi",
        "VectorDatabaseVectorOperationsApi",
    ):
        monkeypatch.setattr(ords_module, name, FakeGeneratedApi)

    config = Configuration(rest_url=VALID_HOST)
    service = create_ords_service(config)

    assert service.config is config  # nosec B101
    assert service.api_client.config is config  # nosec B101
    assert service.table_api.api_client is service.api_client  # nosec B101
    assert service.vector_api.api_client is service.api_client  # nosec B101


@pytest.mark.parametrize(
    "method_name, api_name",
    [
        ("list_vector_tables", "table_api"),
        ("list_vector_load_jobs", "vector_api"),
        ("list_index_jobs", "index_api"),
        ("list_models", "model_api"),
    ],
)
def test_collection_pagination_is_forwarded(method_name, api_name):
    service = _make_service()
    getattr(service, method_name)(limit=3, offset=9)
    assert getattr(service, api_name).calls[-1] == (  # nosec B101
        method_name,
        (),
        {"limit": 3, "offset": 9},
    )


def test_generated_index_params_omit_absent_optional_fields():
    from oracle_vecdb.services.ords.models.vector_index_params import (
        VectorIndexParams,
    )

    payload = VectorIndexParams.from_dict(
        {"vector_index_params": {"organization": "PARTITIONS"}}
    ).to_dict()
    assert payload["vector_index_params"] == {  # nosec B101
        "organization": "PARTITIONS"
    }


def test_generated_index_params_accepts_documented_distribution_method():
    from oracle_vecdb.services.ords.models.vector_index_params import (
        VectorIndexParams,
    )

    payload = VectorIndexParams.from_dict(
        {
            "vector_index_params": {
                "organization": "INMEMORY GRAPH",
                "distribute_params": {"distribute_method": "AUTO"},
            }
        }
    ).to_dict()

    assert payload["vector_index_params"]["distribute_params"] == {
        "distribute_method": "AUTO"
    }  # nosec B101


def test_ords_debug_flag_conversion():
    service = _make_service()

    assert service._convert_debug_flags(None) is None  # nosec B101
    assert service._convert_debug_flags({}) == {}  # nosec B101

    converted = service._convert_debug_flags({"vector_index": "low"})

    assert converted.vector_index == "low"  # nosec B101


def test_ords_service_retries_555_and_ords_25001(monkeypatch):
    service = _make_service()
    service.config = Configuration(rest_url=VALID_HOST)
    service.config.ords_settings.max_retry_count_error_555 = 2
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise TransportError(status=555, reason="ORDS-25001")
        return "tables"

    service.table_api.list_vector_tables = flaky
    assert isinstance(
        service.list_vector_tables(), ords_module.VectorTableCollectionResponse
    )  # nosec B101
    assert calls["count"] == 3  # nosec B101


def test_ords_service_honors_max_retries(monkeypatch):
    service = _make_service()
    service.config = Configuration(rest_url=VALID_HOST)
    service.config.ords_settings.max_retry_count_error_555 = 1
    calls = {"count": 0}

    def failing():
        calls["count"] += 1
        raise TransportError(status=555, reason="ORDS-25001")

    service.table_api.list_vector_tables = failing
    with pytest.raises(VecDBException):
        service.list_vector_tables()
    assert calls["count"] == 2  # nosec B101


def test_ords_service_retries_429_in_public_facade():
    service = _make_service()
    service.config = Configuration(rest_url=VALID_HOST)
    service.config.ords_settings.max_retry_count_error_429 = 2
    calls = {"count": 0}

    def throttled():
        calls["count"] += 1
        if calls["count"] < 3:
            raise TransportError(status=429, reason="Too Many Requests")
        return "tables"

    service.table_api.list_vector_tables = throttled

    assert isinstance(
        service.list_vector_tables(), ords_module.VectorTableCollectionResponse
    )  # nosec B101
    assert calls["count"] == 3  # nosec B101


def test_ords_service_honors_429_max_retries():
    service = _make_service()
    service.config = Configuration(rest_url=VALID_HOST)
    service.config.ords_settings.max_retry_count_error_429 = 1
    calls = {"count": 0}

    def throttled():
        calls["count"] += 1
        raise TransportError(status=429, reason="Too Many Requests")

    service.table_api.list_vector_tables = throttled

    with pytest.raises(VecDBException):
        service.list_vector_tables()
    assert calls["count"] == 2  # nosec B101


def test_ords_service_does_not_retry_normalized_vecdb_error():
    service = _make_service()
    service.config = Configuration(rest_url=VALID_HOST)
    service.config.ords_settings.max_retry_count_error_429 = 2
    calls = {"count": 0}

    original = TransportError(status=429, reason="Too Many Requests")

    def throttled_then_normalized():
        calls["count"] += 1
        if calls["count"] == 1:
            raise original
        raise VecDBException.from_service_error(
            "list_vector_tables",
            {"args": (), "kwargs": {}},
            "ORDSService",
            original,
        )

    service.table_api.list_vector_tables = throttled_then_normalized

    with pytest.raises(VecDBException):
        service.list_vector_tables()
    assert calls["count"] == 2  # nosec B101


def test_ords_service_does_not_retry_unhandled_api_errors():
    service = _make_service()
    service.config = Configuration(rest_url=VALID_HOST)
    calls = {"count": 0}

    def invalid_request():
        calls["count"] += 1
        raise TransportError(status=400, reason="Bad Request")

    service.table_api.list_vector_tables = invalid_request

    with pytest.raises(VecDBException):
        service.list_vector_tables()
    assert calls["count"] == 1  # nosec B101


def test_ords_service_maps_table_inference_and_vector_requests():
    service = _make_service()
    vector_item = ords_module._models.UpsertVectorsRequestVectorsInner(
        id="v2",
        dense_vector=[0.3, 0.4],
        metadata={"kind": "existing"},
    )
    embed_item = ords_module._models.VectorEmbedInputItem(
        text="already-normalized"
    )

    assert isinstance(
        service.describe_vector_database(), ords_module.DatabaseSummaryResponse
    )  # nosec B101
    assert isinstance(
        service.list_vector_tables(), ords_module.VectorTableCollectionResponse
    )  # nosec B101
    assert isinstance(
        service.describe_vector_table("docs"), ords_module.VectorTableResponse
    )  # nosec B101
    assert service.drop_vector_table("docs").message  # nosec B101
    assert isinstance(
        service.list_vector_load_jobs(), ords_module.JobCollectionResponse
    )  # nosec B101
    assert isinstance(
        service.describe_vector_load_job("job1"), ords_module.JobResponse
    )  # nosec B101
    assert isinstance(
        service.get_vector_load_job_log("job1"), ords_module.JobLogResponse
    )  # nosec B101

    service.create_vector_table(
        name="docs",
        comment="Documents",
        annotations={"owner": "sdk"},
        table_params={"auto_generate_id": True},
        embed_params={"model": "all_MiniLM_L12_v2"},
        index_params={"vector_index_params": {"auto_index": False}},
        debug_flags={"vector_index": "low"},
    )
    service.update_vector_table_annotation(
        "docs",
        comment="Updated documents",
        annotations={"tier": "gold"},
        debug_flags={"vector_index": "low"},
    )
    service.generate_embedding(
        "embedder",
        ["hello", embed_item],
        debug_flags={"vector_index": "low"},
    )
    service.upsert_vectors(
        "docs",
        [
            {"id": "v1", "dense_vector": [0.1, 0.2], "metadata": {"a": 1}},
            vector_item,
        ],
        debug_flags={"vector_index": "low"},
    )
    service.list_vectors(
        "docs",
        ids=["v1"],
        limit=2,
        offset=1,
        debug_flags={"vector_index": "low"},
    )
    assert service.delete_vectors("docs", ["v1"]).message  # nosec B101
    assert isinstance(  # nosec B101
        service.load_vectors("docs", "https://example.com/data.json"),
        ords_module.JobResponse,
    )

    create_request = _first_positional_request(
        service.table_api, "create_vector_table"
    )
    embed_request = _first_positional_request(
        service.inference_api, "generate_embedding"
    )
    upsert_request = _first_keyword_request(
        service.vector_api, "upsert_vectors", "upsert_vectors_request"
    )

    assert create_request.name == "docs"  # nosec B101
    assert create_request.comment == "Documents"  # nosec B101
    assert create_request.table_params.auto_generate_id is True  # nosec B101
    assert (  # nosec B101
        create_request.embed_params.model == "all_MiniLM_L12_v2"
    )
    assert (  # nosec B101
        create_request.index_params.vector_index_params.auto_index is False
    )
    assert embed_request.inputs[0].text == "hello"  # nosec B101
    assert embed_request.inputs[1] is embed_item  # nosec B101
    assert upsert_request.vectors[0].id == "v1"  # nosec B101
    assert upsert_request.vectors[1] is vector_item  # nosec B101


@pytest.mark.parametrize(
    "kwargs, message",
    [
        ({"table_params": "not-a-dict"}, "table_params"),
        ({"embed_params": "not-a-dict"}, "embed_params"),
        ({"index_params": "not-a-dict"}, "index_params"),
        ({"debug_flags": "not-a-dict"}, "debug_flags"),
    ],
)
def test_ords_service_rejects_non_dict_create_table_options(kwargs, message):
    service = _make_service()

    with pytest.raises((VecDBException, TypeError), match=message) as error:
        service.create_vector_table(name="docs", **kwargs)
    assert isinstance(error.value, VecDBException)  # nosec B101
    assert error.value.is_original_exception(TypeError)  # nosec B101


@pytest.mark.parametrize(
    "method_name", ["create_index", "rebuild_index", "drop_index"]
)
def test_ords_service_rejects_non_dict_index_params(method_name):
    service = _make_service()

    with pytest.raises(TypeError, match="index_params must be a dictionary"):
        getattr(service, method_name)("docs", index_params="not-a-dict")


@pytest.mark.parametrize(
    "index_params",
    [
        {"organization": "INMEMORY GRAPH"},
        {"vectorIndexParams": {}},
        {"vector_index_params": {"compressionRatio": 4}},
        {
            "vector_index_params": {
                "distribute_params": {"distribute_method": None}
            }
        },
        {"vector_index_params": {"distribute_params": {}}},
        {
            "vector_index_params": {
                "distribute_params": {"distribute_method": "NONE"}
            }
        },
    ],
)
def test_ords_service_rejects_legacy_or_unknown_index_fields(index_params):
    service = _make_service()

    with pytest.raises((VecDBException, TypeError, ValueError)) as error:
        service.create_index("docs", index_params=index_params)
    assert isinstance(error.value, VecDBException)  # nosec B101
    assert isinstance(  # nosec B101
        error.value.original_exception, (TypeError, ValueError)
    )


def test_ords_service_wraps_generated_pydantic_validation_error():
    service = _make_service()

    def raise_validation_error(_request):
        from oracle_vecdb.services.ords.models.vector_index_params_vector_index_params_distribute_params import (
            VectorIndexParamsVectorIndexParamsDistributeParams,
        )

        VectorIndexParamsVectorIndexParamsDistributeParams(
            distribute_method="NONE"
        )

    service.table_api.create_vector_table = raise_validation_error

    with pytest.raises(VecDBException) as error:
        service.create_vector_table(name="docs")

    assert error.value.is_original_exception(ValidationError)  # nosec B101
    assert error.value.original_exception_type is ValidationError  # nosec B101
    assert "ValidationError" in str(error.value)  # nosec B101
    assert "distribute_method" in str(error.value)  # nosec B101
    assert "NONE" not in str(error.value)  # nosec B101


def test_ords_service_accepts_nullable_distribute_params():
    """All index lifecycle facade methods share nullable index validation."""
    ORDSService._validate_index_params_fields(
        {"vector_index_params": {"distribute_params": None}}
    )


def test_generated_index_params_accept_nullable_distribution_method():
    from oracle_vecdb.services.ords.models.vector_index_params import (
        VectorIndexParams,
    )

    params = VectorIndexParams.from_dict(
        {
            "vector_index_params": {
                "distribute_params": {"distribute_method": None}
            }
        }
    )
    assert (
        params.to_dict()["vector_index_params"]["distribute_params"] == {}
    )  # nosec B101
    payload = VectorIndexParams.from_dict(
        {"vector_index_params": {"distribute_params": None}}
    ).to_dict()
    assert (
        payload["vector_index_params"]["distribute_params"] is None
    )  # nosec B101
    with pytest.raises(ValueError, match="enum"):
        VectorIndexParams.from_dict(
            {
                "vector_index_params": {
                    "distribute_params": {"distribute_method": "NONE"}
                }
            }
        )


@pytest.mark.parametrize(
    "method_name, kwargs",
    [
        ("list_vector_tables", {"limit": 0}),
        ("list_models", {"offset": -1}),
        ("list_index_jobs", {"limit": "1"}),
        ("list_vectors", {"limit": "1"}),
    ],
)
def test_ords_service_validates_pagination(method_name, kwargs):
    service = _make_service()

    if method_name == "list_vectors":

        def call():
            return service.list_vectors("docs", **kwargs)

    else:

        def call():
            return getattr(service, method_name)(**kwargs)

    with pytest.raises((TypeError, ValueError)):
        call()


@pytest.mark.parametrize(
    "method_name, kwargs",
    [
        ("generate_embedding", {"inputs": []}),
        ("generate_embedding", {"inputs": "text"}),
        ("upsert_vectors", {"vectors": "not-a-list"}),
        ("delete_vectors", {"ids": "not-a-list"}),
        ("rerank", {"documents": []}),
        ("rerank", {"documents": ["ok", 1]}),
    ],
)
def test_ords_service_rejects_invalid_collection_arguments(method_name, kwargs):
    service = _make_service()

    defaults = {
        "generate_embedding": {"model_name": "model"},
        "upsert_vectors": {"table_name": "docs"},
        "delete_vectors": {"table_name": "docs"},
        "rerank": {"query": "query", "model_name": "model"},
    }
    with pytest.raises((TypeError, ValueError)):
        getattr(service, method_name)(**defaults[method_name], **kwargs)


def test_ords_service_maps_search_index_and_model_requests():
    service = _make_service()

    query_response = service.query(
        "docs",
        query_by={"text": "hello"},
        top_k=3,
        filters={"ACCOUNT_CATEGORY": {"$eq": "Savings"}},
        advanced_options={"ef_search": 16},
        include_vectors=True,
        output_selector=["category", "price"],
        debug_flags={"vector_index": "low"},
    )
    rerank_response = service.rerank(
        "hello",
        ["doc1", "doc2"],
        "reranker",
        model_params={"provider": "database"},
        debug_flags={"vector_index": "low"},
    )

    assert query_response.items[0].id == "v1"  # nosec B101
    assert rerank_response.items[0].score == 0.9  # nosec B101
    assert isinstance(  # nosec B101
        service.create_index(
            "docs", {"vector_index_params": {"organization": "PARTITIONS"}}
        ),
        ords_module.JobResponse,
    )
    assert isinstance(
        service.list_index_jobs(), ords_module.JobCollectionResponse
    )  # nosec B101
    assert isinstance(
        service.describe_index_job("job1"), ords_module.JobResponse
    )  # nosec B101
    assert isinstance(
        service.get_index_job_log("job1"), ords_module.JobLogResponse
    )  # nosec B101
    assert service.describe_index("docs").index_status == "READY"  # nosec B101
    assert service.drop_index(
        "docs", {"index_type": "all"}
    ).message  # nosec B101
    assert isinstance(
        service.list_models(), ords_module.ModelCollectionResponse
    )  # nosec B101
    assert isinstance(
        service.load_model(
            "embedder",
            "https://example.com/model.onnx",
            model_params={"provider": "database"},
            debug_flags={"vector_index": "low"},
        ),
        ords_module.ModelResponse,
    )  # nosec B101
    assert isinstance(
        service.describe_model("embedder"), ords_module.ModelResponse
    )  # nosec B101
    assert service.drop_model("embedder").message  # nosec B101

    service.rebuild_index(
        "docs",
        {"vector_index_params": {"organization": "PARTITIONS"}},
        debug_flags={"vector_index": "low"},
    )

    query_request = service.search_api.calls[0][2]["query_vectors_request"]
    create_index_request = _first_positional_request(
        service.index_api, "create_index"
    )
    rebuild_kwargs = next(
        kwargs
        for name, _, kwargs in service.index_api.calls
        if name == "rebuild_index"
    )
    drop_kwargs = next(
        kwargs
        for name, _, kwargs in service.index_api.calls
        if name == "drop_index"
    )
    load_model_request = _first_positional_request(
        service.model_api, "load_model"
    )
    rerank_request = _first_positional_request(service.inference_api, "rerank")

    assert query_request.query_by == {"text": "hello"}  # nosec B101
    assert query_request.output_selector == ["category", "price"]  # nosec B101
    assert isinstance(  # nosec B101
        create_index_request.index_params,
        ords_module._models.VectorIndexParams,
    )
    assert (  # nosec B101
        create_index_request.index_params.vector_index_params.organization
        == "PARTITIONS"
    )
    assert rebuild_kwargs["vector_table_name"] == "docs"  # nosec B101
    assert isinstance(  # nosec B101
        rebuild_kwargs["rebuild_index_request"].index_params,
        ords_module._models.VectorIndexParams,
    )
    assert (  # nosec B101
        rebuild_kwargs[
            "rebuild_index_request"
        ].index_params.vector_index_params.organization
        == "PARTITIONS"
    )
    assert (  # nosec B101
        drop_kwargs["rebuild_index_request"].index_params.index_type == "all"
    )
    assert load_model_request.model_params.provider == "database"  # nosec B101
    assert rerank_request.model_params.provider == "database"  # nosec B101


def test_query_accepts_empty_string_output_selector_and_rejects_non_string():
    service = _make_service()

    service.query(
        "docs",
        query_by={"text": "hello"},
        top_k=1,
        output_selector=[""],
    )

    with pytest.raises(VecDBException) as error:
        service.query(
            "docs",
            query_by={"text": "hello"},
            top_k=1,
            output_selector=[123],
        )
    assert error.value.is_original_exception(ValidationError)  # nosec B101


def test_rerank_preserves_extensible_model_params():
    service = _make_service()
    service.rerank("query", ["document"], "reranker", model_params={"top_n": 3})

    request = _first_positional_request(service.inference_api, "rerank")
    assert request.model_params.to_dict()["top_n"] == 3  # nosec B101


def test_public_paged_responses_preserve_ords_aliases():
    service = _make_service()
    service.table_api.returns["list_vector_tables"] = {
        "items": [],
        "hasMore": True,
        "limit": 10,
        "offset": 2,
        "count": 4,
    }
    response = service.list_vector_tables()
    assert response.has_more is True  # nosec B101
