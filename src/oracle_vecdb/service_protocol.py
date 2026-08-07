##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""Common backend contract used by the public OracleVecDB facade."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, Union

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
from .types import VectorDebugFlags


class VecDBServiceProtocol(Protocol):
    """Contract implemented by the ORDS service delegate."""

    api_client: Any
    table_api: Any
    index_api: Any
    inference_api: Any
    model_api: Any
    search_api: Any
    summary_api: Any
    vector_api: Any

    def _convert_debug_flags(
        self, debug_flags: Optional[Dict[str, str]]
    ) -> Union[VectorDebugFlags, Dict[str, str], None]:
        """Normalize debug flags for the active backend."""

    def describe_vector_database(
        self, *args: Any, **kwargs: Any
    ) -> DatabaseSummaryResponse: ...

    def list_vector_tables(
        self, *args: Any, **kwargs: Any
    ) -> VectorTableCollectionResponse: ...

    def create_vector_table(
        self, *args: Any, **kwargs: Any
    ) -> VectorTableResponse: ...

    def describe_vector_table(
        self, *args: Any, **kwargs: Any
    ) -> VectorTableResponse: ...

    def drop_vector_table(
        self, *args: Any, **kwargs: Any
    ) -> DropVectorTableResponse: ...

    def update_vector_table_annotation(
        self, *args: Any, **kwargs: Any
    ) -> VectorTableResponse: ...

    def generate_embedding(
        self, *args: Any, **kwargs: Any
    ) -> EmbeddingResponse: ...

    def upsert_vectors(
        self, *args: Any, **kwargs: Any
    ) -> UpsertVectorsResponse: ...

    def list_vectors(
        self, *args: Any, **kwargs: Any
    ) -> VectorCollectionResponse: ...

    def delete_vectors(
        self, *args: Any, **kwargs: Any
    ) -> DeleteVectorsResponse: ...

    def load_vectors(self, *args: Any, **kwargs: Any) -> JobResponse: ...

    def list_vector_load_jobs(
        self, *args: Any, **kwargs: Any
    ) -> JobCollectionResponse: ...

    def describe_vector_load_job(
        self, *args: Any, **kwargs: Any
    ) -> JobResponse: ...

    def get_vector_load_job_log(
        self, *args: Any, **kwargs: Any
    ) -> JobLogResponse: ...

    def query(self, *args: Any, **kwargs: Any) -> QueryResponse: ...

    def rerank(self, *args: Any, **kwargs: Any) -> RerankResponse: ...

    def create_index(self, *args: Any, **kwargs: Any) -> JobResponse: ...

    def list_index_jobs(
        self, *args: Any, **kwargs: Any
    ) -> JobCollectionResponse: ...

    def describe_index_job(self, *args: Any, **kwargs: Any) -> JobResponse: ...

    def get_index_job_log(
        self, *args: Any, **kwargs: Any
    ) -> JobLogResponse: ...

    def rebuild_index(self, *args: Any, **kwargs: Any) -> JobResponse: ...

    def describe_index(
        self, *args: Any, **kwargs: Any
    ) -> IndexDescriptionResponse: ...

    def drop_index(self, *args: Any, **kwargs: Any) -> DropIndexResponse: ...

    def list_models(
        self, *args: Any, **kwargs: Any
    ) -> ModelCollectionResponse: ...

    def load_model(self, *args: Any, **kwargs: Any) -> ModelResponse: ...

    def describe_model(self, *args: Any, **kwargs: Any) -> ModelResponse: ...

    def drop_model(self, *args: Any, **kwargs: Any) -> DropModelResponse: ...
