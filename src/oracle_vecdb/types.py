##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""Backward-compatible public SDK type aliases used by the facade client.

Prefer importing response models from ``oracle_vecdb.data_types`` for new code.
"""

from .data_types import (
    DatabaseSummaryResponse as SummaryItem,
    DeleteVectorsResponse as DeleteVectors200Response,
    DropModelResponse as DropModel200Response,
    DropVectorTableResponse as DropVectorTable200Response,
    EmbeddingResponse as VectorEmbedResponse,
    IndexDescriptionResponse as DescribeIndex200Response,
    JobCollectionResponse as VecDBJobCollection,
    JobLogResponse as VecDBJobLogItem,
    JobResponse as VecDBJobItem,
    ModelCollectionResponse as ModelsCollection,
    ModelResponse as ModelItem,
    UpsertVectorsResponse as UpsertVectors201Response,
    VectorCollectionResponse as VecDBVectorVectorCollection,
    VectorTableCollectionResponse as VecDBTableCollection,
    VectorTableResponse as VecDBTableNoLinks,
)
from .services.ords.models.upsert_vectors_request_vectors_inner import (
    UpsertVectorsRequestVectorsInner,
)
from .services.ords.models.vector_debug_flags import VectorDebugFlags
from .services.ords.models.vector_embed_input_item import VectorEmbedInputItem
from .services.ords.models.vector_rerank_item import VectorRerankItem

__all__ = [
    "DeleteVectors200Response",
    "DescribeIndex200Response",
    "DropModel200Response",
    "DropVectorTable200Response",
    "ModelItem",
    "ModelsCollection",
    "SummaryItem",
    "UpsertVectors201Response",
    "UpsertVectorsRequestVectorsInner",
    "VecDBJobCollection",
    "VecDBJobItem",
    "VecDBJobLogItem",
    "VecDBTableCollection",
    "VecDBTableNoLinks",
    "VecDBVectorVectorCollection",
    "VectorDebugFlags",
    "VectorEmbedInputItem",
    "VectorEmbedResponse",
    "VectorRerankItem",
]
