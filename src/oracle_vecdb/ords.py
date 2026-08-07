##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""ORDS-backed service implementation and generated runtime bindings."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union, cast

from .data_types import (
    DatabaseSummaryResponse,
    DeleteVectorsResponse,
    DropIndexResponse,
    DropModelResponse,
    DropVectorTableResponse,
    EmbeddingResponse,
    IndexDescriptionResponse,
    JobCollectionResponse,
    JobLogResponse,
    JobResponse,
    ModelCollectionResponse,
    ModelResponse,
    QueryResponse,
    RerankResponse,
    UpsertVectorsResponse,
    VectorCollectionResponse,
    VectorTableCollectionResponse,
    VectorTableResponse,
)
from .services.ords.api.vector_database_inference_operations_api import (
    VectorDatabaseInferenceOperationsApi,
)
from .services.ords.api.vector_database_models_api import (
    VectorDatabaseModelsApi,
)
from .services.ords.api.vector_database_summary_api import (
    VectorDatabaseSummaryApi,
)
from .services.ords.api.vector_database_vector_indexes_api import (
    VectorDatabaseVectorIndexesApi,
)
from .services.ords.api.vector_database_vector_operations_api import (
    VectorDatabaseVectorOperationsApi,
)
from .services.ords.api.vector_database_vector_search_api import (
    VectorDatabaseVectorSearchApi,
)
from .services.ords.api.vector_database_vector_tables_api import (
    VectorDatabaseVectorTablesApi,
)
from .services.ords.api_client import ApiClient
from .configuration import ORDSBaseConfiguration
from .services.ords import models as _generated_models
from .types import UpsertVectorsRequestVectorsInner, VectorEmbedInputItem
from .ords_response_handlers import ORDSResponseHandler
from .vecdb_exception import VecDBException


class _CustomApiClient(ApiClient):
    """Handwritten adapter for generator-owned request plumbing.

    Generated API methods pass ``None`` when no per-request timeout is set.
    Apply the SDK configuration default here so regeneration of ``ApiClient``
    does not discard the public timeout contract.
    """

    def call_api(
        self,
        method: Any,
        url: Any,
        header_params: Any = None,
        body: Any = None,
        post_params: Any = None,
        _request_timeout: Any = None,
    ) -> Any:
        if _request_timeout is None:
            _request_timeout = getattr(self.configuration, "timeout", None)
        return super().call_api(
            method,
            url,
            header_params,
            body,
            post_params,
            _request_timeout,
        )


class ORDSSettings:
    """Mutable settings for ORDS response handling."""

    def __init__(
        self,
        max_retry_count_error_555: int = 3,
        max_retry_count_error_429: int = 3,
    ) -> None:
        self.max_retry_count_error_555 = max(0, int(max_retry_count_error_555))
        self.max_retry_count_error_429 = max(0, int(max_retry_count_error_429))


_models = cast(Any, _generated_models)

_GENERATED_MODEL_NAMES = [
    name
    for name, value in vars(_models).items()
    if not name.startswith("_")
    and getattr(value, "__module__", "").startswith(
        "oracle_vecdb.services.ords.models"
    )
]


class ORDSConfiguration(ORDSBaseConfiguration):
    """Configuration selected for ORDS/REST based VecDB access."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.ords_settings = ORDSSettings()

        if not self.has_rest_url:
            raise ValueError(
                "ORDSConfiguration requires an ORDS endpoint. Please provide "
                "'rest_url' or the deprecated 'host' parameter."
            )


class ORDSService:
    """Expose Oracle VecDB operations backed by the ORDS APIs."""

    def __getattribute__(self, name: str) -> Any:
        """Wrap service failures at the handwritten ORDS boundary."""
        value = super().__getattribute__(name)
        if name.startswith("_") or not callable(value):
            return value

        def call_with_context(*args: Any, **kwargs: Any) -> Any:
            try:
                return value(*args, **kwargs)
            except VecDBException:
                raise
            except Exception as error:
                wrapped = VecDBException.from_service_error(
                    operation=name,
                    arguments={"args": args, "kwargs": kwargs},
                    service_name=type(self).__name__,
                    error=error,
                )
                # The wrapper already contains the complete original ORDS
                # traceback. Suppress implicit exception chaining so reports
                # contain one clear template instead of the same failure twice.
                raise wrapped from None

        return call_with_context

    def __init__(self, config: ORDSBaseConfiguration) -> None:
        self.config = config
        self.api_client = _CustomApiClient(config)
        self.table_api = VectorDatabaseVectorTablesApi(self.api_client)
        self.index_api = VectorDatabaseVectorIndexesApi(self.api_client)
        self.inference_api = VectorDatabaseInferenceOperationsApi(
            self.api_client
        )
        self.model_api = VectorDatabaseModelsApi(self.api_client)
        self.search_api = VectorDatabaseVectorSearchApi(self.api_client)
        self.summary_api = VectorDatabaseSummaryApi(self.api_client)
        self.vector_api = VectorDatabaseVectorOperationsApi(self.api_client)

    def _convert_debug_flags(
        self, debug_flags: Optional[Dict[str, str]]
    ) -> Union[Any, Dict[str, str], None]:
        """Convert debug flag dictionaries to the generated model."""
        if debug_flags is None:
            return None
        if not isinstance(debug_flags, dict):
            raise TypeError("debug_flags must be a dictionary.")
        if isinstance(debug_flags, dict) and debug_flags:
            return _models.VectorDebugFlags(**debug_flags)
        return debug_flags

    @staticmethod
    def _require_optional_dict(value: Any, parameter_name: str) -> None:
        if value is not None and not isinstance(value, dict):
            raise TypeError(f"{parameter_name} must be a dictionary.")

    @staticmethod
    def _require_non_empty_list(value: Any, parameter_name: str) -> None:
        if not isinstance(value, list) or not value:
            raise TypeError(f"{parameter_name} must be a non-empty list.")

    @staticmethod
    def _validate_pagination(
        limit: Any, offset: Any, *, integer: bool = True
    ) -> None:
        for value, name in ((limit, "limit"), (offset, "offset")):
            if value is None:
                continue
            valid_type = int if integer else (int, float)
            if isinstance(value, bool) or not isinstance(value, valid_type):
                expected = "integer" if integer else "number"
                raise TypeError(f"{name} must be a {expected}.")
            if value < (1 if name == "limit" else 0):
                raise ValueError(
                    f"{name} must be {'positive' if name == 'limit' else 'non-negative'}."
                )

    @staticmethod
    def _validate_index_params_fields(index_params: Any) -> None:
        """Reject legacy/camel-case keys that generated models retain silently."""
        if not isinstance(index_params, dict):
            return
        allowed = {
            "vector_index_params",
            "metadata_index_params",
            "parallel_creation",
            "index_type",
        }
        unknown = set(index_params) - allowed
        if unknown:
            raise ValueError(
                f"Unsupported index_params field(s): {', '.join(sorted(unknown))}"
            )
        nested_allowed = {
            "auto_index",
            "organization",
            "distance_metric",
            "accuracy",
            "online_build",
            "quantization_type",
            "compression_ratio",
            "distribute_params",
            "advanced_params",
        }
        vector = index_params.get("vector_index_params")
        if vector is not None:
            if not isinstance(vector, dict):
                raise TypeError("vector_index_params must be a dictionary.")
            unknown = set(vector) - nested_allowed
            if unknown:
                raise ValueError(
                    "Unsupported vector_index_params field(s): "
                    f"{', '.join(sorted(unknown))}"
                )
            if "distribute_params" in vector:
                distribute = vector["distribute_params"]
                # The OpenAPI contract declares distribute_params nullable.
                # Validate its required child field only when an object was
                # supplied; an explicit null is a valid request value.
                if distribute is None:
                    pass
                elif not isinstance(distribute, dict):
                    raise TypeError("distribute_params must be a dictionary.")
                elif set(distribute) != {"distribute_method"}:
                    raise ValueError("Unsupported distribute_params field(s)")
                elif distribute["distribute_method"] is None:
                    raise ValueError(
                        "distribute_params.distribute_method is required."
                    )
        metadata = index_params.get("metadata_index_params")
        if metadata is not None:
            if not isinstance(metadata, dict):
                raise TypeError("metadata_index_params must be a dictionary.")
            unknown = set(metadata) - {
                "auto_index",
                "include_paths",
                "exclude_paths",
            }
            if unknown:
                raise ValueError(
                    "Unsupported metadata_index_params field(s): "
                    f"{', '.join(sorted(unknown))}"
                )

    @ORDSResponseHandler
    def describe_vector_database(self) -> DatabaseSummaryResponse:
        return DatabaseSummaryResponse.from_internal(
            self.summary_api.describe_vector_database()
        )

    @ORDSResponseHandler
    def list_vector_tables(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> VectorTableCollectionResponse:
        self._validate_pagination(limit, offset)
        kwargs: Dict[str, Any] = {
            k: v
            for k, v in {"limit": limit, "offset": offset}.items()
            if v is not None
        }
        return VectorTableCollectionResponse.from_internal(
            self.table_api.list_vector_tables(**kwargs)
        )

    @ORDSResponseHandler
    def create_vector_table(
        self,
        name: str,
        comment: Optional[str] = None,
        annotations: Optional[Dict[str, Any]] = None,
        table_params: Optional[Dict[str, Any]] = None,
        embed_params: Optional[Dict[str, Any]] = None,
        index_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> VectorTableResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_optional_dict(annotations, "annotations")
        self._require_optional_dict(table_params, "table_params")
        converted_table_params = None
        if isinstance(table_params, dict) and table_params:
            converted_table_params = (
                _models.CreateVectorTableRequestTableParams.from_dict(
                    table_params
                )
            )
        self._require_optional_dict(embed_params, "embed_params")
        converted_embed_params = None
        if isinstance(embed_params, dict) and embed_params:
            converted_embed_params = (
                _models.CreateVectorTableRequestEmbedParams.from_dict(
                    embed_params
                )
            )
        self._require_optional_dict(index_params, "index_params")
        self._validate_index_params_fields(index_params)
        converted_index_params = None
        if isinstance(index_params, dict) and index_params:
            converted_index_params = _models.VectorIndexParams.from_dict(
                index_params
            )

        request = _models.CreateVectorTableRequest(
            name=name,
            comment=comment,
            annotations=annotations,
            table_params=converted_table_params,
            embed_params=converted_embed_params,
            index_params=converted_index_params,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return VectorTableResponse.from_internal(
            self.table_api.create_vector_table(request)
        )

    @ORDSResponseHandler
    def describe_vector_table(self, name: str) -> VectorTableResponse:
        return VectorTableResponse.from_internal(
            self.table_api.describe_vector_table(vector_table_name=name)
        )

    @ORDSResponseHandler
    def drop_vector_table(self, name: str) -> DropVectorTableResponse:
        response = self.table_api.drop_vector_table(vector_table_name=name)
        return DropVectorTableResponse.from_internal(response)

    @ORDSResponseHandler
    def update_vector_table_annotation(
        self,
        name: str,
        comment: Optional[str] = None,
        annotations: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> VectorTableResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_optional_dict(annotations, "annotations")

        request_debug_flags = (
            converted_debug_flags
            if isinstance(converted_debug_flags, _models.VectorDebugFlags)
            else None
        )
        request = _models.UpdateVectorTableAnnotationRequest(
            comment=comment,
            annotations=annotations,
            debug_flags=request_debug_flags,
        )  # type: ignore[call-arg]
        return VectorTableResponse.from_internal(
            self.table_api.update_vector_table_annotation(
                vector_table_name=name,
                update_vector_table_annotation_request=request,
            )
        )

    @ORDSResponseHandler
    def generate_embedding(
        self,
        model_name: str,
        inputs: List[Union[str, VectorEmbedInputItem]],
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> EmbeddingResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_non_empty_list(inputs, "inputs")
        normalized_inputs = [
            (
                item
                if isinstance(item, _models.VectorEmbedInputItem)
                else (
                    _models.VectorEmbedInputItem.from_dict(item)
                    if isinstance(item, dict)
                    else _models.VectorEmbedInputItem(text=cast(str, item))
                )
            )
            for item in (inputs or [])
        ]
        request = _models.VectorEmbedRequest(
            model_name=model_name,
            inputs=normalized_inputs,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return EmbeddingResponse.from_internal(
            self.inference_api.generate_embedding(request)
        )

    @ORDSResponseHandler
    def upsert_vectors(
        self,
        table_name: str,
        vectors: List[Union[UpsertVectorsRequestVectorsInner, Dict[str, Any]]],
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> UpsertVectorsResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        if not isinstance(vectors, list):
            raise TypeError("vectors must be a list.")
        if any(
            not isinstance(
                vector, (dict, _models.UpsertVectorsRequestVectorsInner)
            )
            for vector in vectors
        ):
            raise TypeError(
                "vectors must contain dictionaries or vector model objects."
            )
        converted_vectors = [
            (
                vector
                if isinstance(vector, _models.UpsertVectorsRequestVectorsInner)
                else _models.UpsertVectorsRequestVectorsInner(
                    **cast(Dict[str, Any], vector)
                )
            )
            for vector in (vectors or [])
        ]
        request = _models.UpsertVectorsRequest(
            vectors=converted_vectors,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return UpsertVectorsResponse.from_internal(
            self.vector_api.upsert_vectors(
                vector_table_name=table_name,
                upsert_vectors_request=request,
            )
        )

    @ORDSResponseHandler
    def list_vectors(
        self,
        table_name: str,
        ids: Optional[List[str]] = None,
        limit: int = 15,
        offset: Optional[Union[float, int]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> VectorCollectionResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._validate_pagination(limit, offset, integer=False)
        if ids is not None:
            if not isinstance(ids, list) or any(
                not isinstance(item, str) for item in ids
            ):
                raise TypeError("ids must be a list of strings.")
        request = _models.ListVectorsRequest(
            ids=ids,
            limit=limit,
            offset=offset,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return VectorCollectionResponse.from_internal(
            self.vector_api.list_vectors(
                vector_table_name=table_name,
                list_vectors_request=request,
            )
        )

    @ORDSResponseHandler
    def delete_vectors(
        self,
        table_name: str,
        ids: List[str],
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> DeleteVectorsResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        if not isinstance(ids, list):
            raise TypeError("ids must be a list of strings.")
        if any(not isinstance(item, str) for item in ids):
            raise TypeError("ids must be a list of strings.")
        request = _models.DeleteVectorsRequest(
            ids=ids,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        response = self.vector_api.delete_vectors(
            vector_table_name=table_name,
            delete_vectors_request=request,
        )
        return DeleteVectorsResponse.from_internal(response)

    @ORDSResponseHandler
    def load_vectors(
        self,
        table_name: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> JobResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_optional_dict(params, "params")
        request = _models.LoadVectorsRequest(
            table_name=table_name,
            url=url,
            params=params,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return JobResponse.from_internal(self.vector_api.load_vectors(request))

    @ORDSResponseHandler
    def list_vector_load_jobs(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> JobCollectionResponse:
        kwargs: Dict[str, Any] = {
            k: v
            for k, v in {"limit": limit, "offset": offset}.items()
            if v is not None
        }
        return JobCollectionResponse.from_internal(
            self.vector_api.list_vector_load_jobs(**kwargs)
        )

    @ORDSResponseHandler
    def describe_vector_load_job(self, load_job_name: str) -> JobResponse:
        return JobResponse.from_internal(
            self.vector_api.describe_vector_load_job(load_job_name)
        )

    @ORDSResponseHandler
    def get_vector_load_job_log(self, load_job_name: str) -> JobLogResponse:
        return JobLogResponse.from_internal(
            self.vector_api.get_vector_load_job_log(load_job_name)
        )

    @ORDSResponseHandler
    def query(
        self,
        table_name: str,
        query_by: Dict[str, Any],
        top_k: Union[float, int],
        filters: Optional[Dict[str, Any]] = None,
        advanced_options: Optional[Dict[str, Any]] = None,
        include_vectors: Optional[bool] = None,
        output_selector: Optional[List[str]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> QueryResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_optional_dict(query_by, "query_by")
        self._require_optional_dict(filters, "filters")
        self._require_optional_dict(advanced_options, "advanced_options")
        request = _models.QueryVectorsRequest(
            query_by=query_by,
            top_k=top_k,
            filters=filters,
            advanced_options=advanced_options,
            include_vectors=include_vectors,
            output_selector=output_selector,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        response = self.search_api.query_vectors(
            vector_table_name=table_name,
            query_vectors_request=request,
        )
        return QueryResponse.from_internal(response)

    @ORDSResponseHandler
    def rerank(
        self,
        query: str,
        documents: List[str],
        model_name: str,
        model_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> RerankResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_non_empty_list(documents, "documents")
        if any(not isinstance(document, str) for document in documents):
            raise TypeError("documents must be a list of strings.")
        self._require_optional_dict(model_params, "model_params")
        converted_model_params = None
        if isinstance(model_params, dict) and model_params:
            # ``modelParams`` is intentionally extensible (for example,
            # ``top_n`` is consumed by hosted rerank providers).  The
            # generated model's constructor only retains declared fields;
            # ``from_dict`` captures unknown fields in additional_properties
            # and emits them back in the request payload.
            converted_model_params = (
                _models.VectorRerankRequestModelParams.from_dict(model_params)
            )

        request = _models.VectorRerankRequest(
            model_name=model_name,
            query=query,
            documents=documents,
            model_params=converted_model_params,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return RerankResponse.from_internal(self.inference_api.rerank(request))

    @ORDSResponseHandler
    def create_index(
        self,
        table_name: str,
        index_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> JobResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_optional_dict(index_params, "index_params")
        self._validate_index_params_fields(index_params)
        converted_index_params = None
        if isinstance(index_params, dict) and index_params:
            converted_index_params = _models.VectorIndexParams.from_dict(
                index_params
            )

        request = _models.CreateIndexRequest(
            table_name=table_name,
            index_params=converted_index_params,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return JobResponse.from_internal(self.index_api.create_index(request))

    @ORDSResponseHandler
    def list_index_jobs(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> JobCollectionResponse:
        self._validate_pagination(limit, offset)
        kwargs: Dict[str, Any] = {
            k: v
            for k, v in {"limit": limit, "offset": offset}.items()
            if v is not None
        }
        return JobCollectionResponse.from_internal(
            self.index_api.list_index_jobs(**kwargs)
        )

    @ORDSResponseHandler
    def describe_index_job(self, index_job_name: str) -> JobResponse:
        return JobResponse.from_internal(
            self.index_api.describe_index_job(index_job_name)
        )

    @ORDSResponseHandler
    def get_index_job_log(self, index_job_name: str) -> JobLogResponse:
        return JobLogResponse.from_internal(
            self.index_api.get_index_job_log(index_job_name)
        )

    @ORDSResponseHandler
    def rebuild_index(
        self,
        table_name: str,
        index_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> JobResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_optional_dict(index_params, "index_params")
        self._validate_index_params_fields(index_params)
        converted_index_params = None
        if isinstance(index_params, dict) and index_params:
            converted_index_params = _models.VectorIndexParams.from_dict(
                index_params
            )

        request = _models.RebuildIndexRequest(
            index_params=converted_index_params,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return JobResponse.from_internal(
            self.index_api.rebuild_index(
                vector_table_name=table_name,
                rebuild_index_request=request,
            )
        )

    @ORDSResponseHandler
    def describe_index(self, table_name: str) -> IndexDescriptionResponse:
        response = self.index_api.describe_index(vector_table_name=table_name)
        return IndexDescriptionResponse.from_internal(response)

    @ORDSResponseHandler
    def drop_index(
        self,
        table_name: str,
        index_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> DropIndexResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_optional_dict(index_params, "index_params")
        self._validate_index_params_fields(index_params)
        converted_index_params = None
        if isinstance(index_params, dict) and index_params:
            converted_index_params = _models.VectorIndexParams.from_dict(
                index_params
            )
        request = _models.RebuildIndexRequest(
            index_params=converted_index_params,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        response = self.index_api.drop_index(
            vector_table_name=table_name,
            rebuild_index_request=request,
        )
        return DropIndexResponse.from_internal(response)

    @ORDSResponseHandler
    def list_models(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> ModelCollectionResponse:
        self._validate_pagination(limit, offset)
        kwargs: Dict[str, Any] = {
            k: v
            for k, v in {"limit": limit, "offset": offset}.items()
            if v is not None
        }
        return ModelCollectionResponse.from_internal(
            self.model_api.list_models(**kwargs)
        )

    @ORDSResponseHandler
    def load_model(
        self,
        model_name: str,
        url: str,
        model_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> ModelResponse:
        converted_debug_flags = self._convert_debug_flags(debug_flags)
        self._require_optional_dict(model_params, "model_params")
        converted_model_params = None
        if isinstance(model_params, dict) and model_params:
            converted_model_params = (
                _models.LoadModelRequestModelParams.from_dict(model_params)
            )

        request = _models.LoadModelRequest(
            model_name=model_name,
            url=url,
            model_params=converted_model_params,
            debug_flags=converted_debug_flags,
        )  # type: ignore[call-arg]
        return ModelResponse.from_internal(self.model_api.load_model(request))

    @ORDSResponseHandler
    def describe_model(self, model_name: str) -> ModelResponse:
        return ModelResponse.from_internal(
            self.model_api.describe_model(model_name)
        )

    @ORDSResponseHandler
    def drop_model(self, model_name: str) -> DropModelResponse:
        response = self.model_api.drop_model(model_name)
        return DropModelResponse.from_internal(response)


def create_ords_service(config: ORDSBaseConfiguration) -> ORDSService:
    """Create the ORDS-backed service delegate."""
    return ORDSService(config)


__all__ = [
    "ApiClient",
    "ORDSConfiguration",
    "ORDSService",
    "create_ords_service",
    "VectorDatabaseInferenceOperationsApi",
    "VectorDatabaseModelsApi",
    "VectorDatabaseSummaryApi",
    "VectorDatabaseVectorIndexesApi",
    "VectorDatabaseVectorOperationsApi",
    "VectorDatabaseVectorSearchApi",
    "VectorDatabaseVectorTablesApi",
] + sorted(_GENERATED_MODEL_NAMES)
