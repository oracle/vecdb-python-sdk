##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""
OracleVecDB: A Python SDK for working with vectors in Oracle AI Database 26ai+.

This module provides a high-level Python client for interacting with Oracle AI Database 26ai+,
offering simple APIs for vector table management, indexing, search, and inference operations.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union, cast

from .configuration import Configuration
from .ords import create_ords_service
from .service_protocol import VecDBServiceProtocol
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
from .types import (
    UpsertVectorsRequestVectorsInner,
    VectorDebugFlags,
    VectorEmbedInputItem,
)
from .validation import validate_resource_names
from .vecdb_exception import VecDBException
from .vecdb_errors import (
    InvalidTableNameFormatError,
    InvalidModelNameFormatError,
    InvalidLoadJobNameFormatError,
    InvalidIndexJobNameFormatError,
    InvalidVectorsError,
    VectorPayloadTooLargeError,
    InvalidLoadJobLogError,
    InvalidIndexJobLogError,
    ResourceNotFoundError,
)

_PROXIED_SERVICE_ATTRIBUTES = frozenset(
    {
        "api_client",
        "table_api",
        "index_api",
        "inference_api",
        "model_api",
        "search_api",
        "summary_api",
        "vector_api",
    }
)

_MAX_UPSERT_PAYLOAD_BYTES = 32 * 1024 * 1024
# Reserve space for the generated request envelope and serialization details.
_UPSERT_PAYLOAD_SAFETY_MARGIN_BYTES = 64 * 1024
_MAX_UPSERT_BATCH_BYTES = (
    _MAX_UPSERT_PAYLOAD_BYTES - _UPSERT_PAYLOAD_SAFETY_MARGIN_BYTES
)
_UPSERT_ARRAY_OVERHEAD_BYTES = 2

TERMINAL_STATES = frozenset(
    {
        "SUCCEEDED",
        "FAILED",
        "STOPPED",
        "BROKEN",
    }
)


class OracleVecDB:
    """
    A client for interacting with Oracle AI Database 26ai+.

    The ``OracleVecDB`` class provides a unified interface for managing vector tables,
    indexes, and performing vector search and inference operations in Oracle AI Database 26ai+.
    This client simplifies vector operations by handling schema creation, embedding integration,
    and index management automatically.

    Response models:
        Public methods return typed response models from ``oracle_vecdb.data_types``.
        Most object responses can be serialized with ``model_dump()`` or ``to_dict()``
        depending on the underlying model. Query result rows support list-style
        indexing in current SDK versions.

    Args:
        config: Configuration object containing connection details and credentials for Oracle AI Database 26ai+.

    Example:

        .. code-block:: python
            :caption: Connect, list tables, and inspect the response

            from oracle_vecdb import OracleVecDB, Configuration

            config = Configuration(
                rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                access_token="<bearer-token>",  # or username="<user>", password="<pass>"
            )

            client = OracleVecDB(config)

            tables = client.list_vector_tables()
            print(tables)

    Distance metric guidance:

        .. list-table::
            :header-rows: 1
            :widths: 20 40 40

            * - Metric
              - Summary
              - When to use
            * - ``COSINE``
              - Compares vector direction and ignores magnitude.
              - Best default for semantic search, text embeddings, and normalized vectors.
            * - ``DOT``
              - Uses dot-product similarity, so both direction and magnitude can affect ranking.
              - Use when the model was trained with dot-product scoring or magnitude carries meaning.
            * - ``EUCLIDEAN``
              - Measures straight-line distance between vectors.
              - Use for geometric or spatial comparisons where actual distance matters.
            * - ``EUCLIDEAN_SQUARED / L2_SQUARED``
              - Euclidean distance without the square root.
              - Faster distance calculations where exact distance magnitude is unimportant.
            * - ``MANHATTAN``
              - Sums absolute differences across vector dimensions.
              - Use for sparse vectors or when you want less sensitivity to large single-dimension differences.
            * - ``HAMMING``
              - Counts how many positions differ between two vectors.
              - Use for binary embeddings, hashes, bit vectors, or yes/no feature encodings.
            * - ``JACCARD``
              - Compares shared features against total features present across both vectors.
              - Use for set-style similarity, binary tags, and sparse binary feature data.

    """

    def __init__(self, config: Configuration) -> None:
        """
        Initialize the OracleVecDB client.

        config: Configuration object with Oracle Database connection parameters.
        """
        object.__setattr__(self, "config", config)
        object.__setattr__(self, "_ords_service", None)

    def _get_ords_service(self) -> VecDBServiceProtocol:
        service = cast(
            Optional[VecDBServiceProtocol], self.__dict__.get("_ords_service")
        )
        if service is None:
            service = create_ords_service(self.config)
            object.__setattr__(self, "_ords_service", service)
        return service

    def _convert_debug_flags(
        self, debug_flags: Optional[Dict[str, str]]
    ) -> Union[VectorDebugFlags, Dict[str, str], None]:
        """Convert debug flags dict to VectorDebugFlags object."""
        return self._get_active_service()._convert_debug_flags(debug_flags)

    def __getattr__(self, name: str) -> Any:
        if name in _PROXIED_SERVICE_ATTRIBUTES:
            return getattr(self._get_active_service(), name)
        raise AttributeError(
            f"{type(self).__name__!s} object has no attribute {name!r}"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _PROXIED_SERVICE_ATTRIBUTES and "config" in self.__dict__:
            setattr(self._get_active_service(), name, value)
            return
        object.__setattr__(self, name, value)

    def _get_active_service(self) -> VecDBServiceProtocol:
        return self._get_ords_service()

    def describe_vector_database(self) -> DatabaseSummaryResponse:
        """
        Get summary statistics for the entire vector database service.

        Returns:
            ``DatabaseSummaryResponse`` with database-level statistics including
            total tables, models, and vectors.

            Example response::

                {
                    "total_tables": 48,
                    "total_vectors": 1353894,
                    "total_models": 9
                }

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                summary = client.describe_vector_database()
                print(summary)
        """
        return self._get_active_service().describe_vector_database()

    def list_vector_tables(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> VectorTableCollectionResponse:
        """
        List all vector tables in the database.

        Returns a list of all vector tables accessible to the current user, including
        their names and basic configuration details.

        Returns:
            ``VectorTableCollectionResponse`` containing table information.

            - Table names
            - Descriptions
            - Vector types
            - Row counts
            - Creation timestamps

        Example response::

                {
                    "items": [
                        {
                            "table_name": "DEMO_PRODUCTS",
                            "description": "Demo table for SDK examples",
                            "status": "Empty",
                            "vector_type": "dense",
                            "vector_table_type": "BYOV",
                            "index_params": {
                                "vector_index_params": {
                                    "auto_index": true,
                                    "organization": "PARTITIONS",
                                    "distance_metric": "COSINE",
                                    "accuracy": 90,
                                    "advanced_params": {"partitions": 10}
                                },
                                "parallel_creation": 4
                            },
                            "annotations": {"metric": "cosine", "dimension": "5"},
                            "links": [
                                {
                                    "rel": "self",
                                    "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/demo_products"
                                }
                            ]
                        },
                        {
                            "table_name": "PRODUCT_TEXT_VECTORS_CAT",
                            "description": "Product recommendations (PRODUCT_TEXT_VECTORS_CAT)",
                            "status": "Empty",
                            "vector_type": "dense",
                            "vector_table_type": "BYOV",
                            "index_params": {
                                "vector_index_params": {
                                    "auto_index": true,
                                    "organization": "PARTITIONS",
                                    "distance_metric": "COSINE",
                                    "accuracy": 90,
                                    "advanced_params": {"partitions": 10}
                                },
                                "parallel_creation": 4
                            },
                            "annotations": {"dimension": "512", "metric": "cosine"},
                            "links": [
                                {
                                    "rel": "self",
                                    "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/product_text_vectors_cat"
                                }
                            ]
                        }
                    ]
                }

            Each entry contains ``table_name``, ``vector_type``, ``status``,
            ``index_params`` (if defined), and annotations.

        Example:

            .. code-block:: python
                :caption: List tables and print their names

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                tables = client.list_vector_tables()
                print(tables)
        """
        return self._get_active_service().list_vector_tables(
            limit=limit, offset=offset
        )

    @validate_resource_names(name=InvalidTableNameFormatError)
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
        """
        Create a new vector table for storing vector embeddings.

        Creates a vector table with a fixed schema optimized for vector search. The table
        includes columns for ID, vector data, and JSON metadata. You can configure automatic
        ID generation, embedding integration, and index parameters during creation.

        :param name: Name of the vector table to create. Must be unique within the database.
        :type name: str
        :param comment: Human-readable comment describing the table's purpose.
        :type comment: str, optional
        :param annotations: Key-value pairs for custom metadata about the table.
            Example: ``{'application': 'chatbot', 'department': 'sales'}``.
        :type annotations: dict, optional
        :param table_params: Table configuration from the OpenAPI
            ``tableParams`` object. Example: ``{'auto_generate_id': True}``.
        :type table_params: dict, optional
        :param embed_params: Configuration for integrated embedding model. If provided,
            the table will automatically generate embeddings on insert. Example:
            ``{'model': 'all_MiniLM_L12_v2', 'embed_metadata_jsonpath': 'content'}``.
        :type embed_params: dict, optional
        :param index_params: 26.2 index configuration. The generated REST
            payload uses nested keys:

            - ``vector_index_params``: vector index settings such as
              ``auto_index``, ``organization``, ``distance_metric``,
              ``accuracy``, ``online_build``, ``quantization_type``,
              ``compression_ratio``, ``distribute_params``, and
              ``advanced_params``.
            - ``metadata_index_params``: metadata index settings such as
              ``auto_index``, ``include_paths``, and ``exclude_paths``.
            - ``parallel_creation``: optional parallel DDL degree.
            - ``index_type``: ``'vector'``, ``'metadata'``, or ``'all'`` for
              rebuild/drop operations.

            Example:
            ``{'vector_index_params': {'auto_index': True, 'organization': 'PARTITIONS', 'advanced_params': {'partitions': 5}}, 'parallel_creation': 4}``

        :type index_params: dict, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``VectorTableResponse`` containing the created table details and
            status.

            Example response::

                {
                    "table_name": "DEMO_PRODUCTS",
                    "owner": "VECTOR3",
                    "status": "Empty",
                    "vector_type": "dense",
                    "vector_table_type": "BYOV",
                    "index_params": {
                        "vector_index_params": {
                            "auto_index": true,
                            "organization": "PARTITIONS",
                            "advanced_params": {"partitions": 10}
                        },
                        "parallel_creation": 4
                    },
                    "annotations": {"metric": "cosine", "dimension": "5"},
                    "created": "2026-03-12T11:21:30Z"
                }

        Raises:
            Exception: If table already exists or if invalid parameters provided.

        Examples:

            .. code-block:: python
                :caption: Create table for pre-computed vectors

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>",  # or username="<user>", password="<pass>"
                    )
                )

                table = client.create_vector_table(
                    name="product_vectors",
                    comment="Product embeddings",
                    table_params={"auto_generate_id": True},
                    index_params={
                        "vector_index_params": {
                            "auto_index": True,
                            "organization": "PARTITIONS",
                            "distance_metric": "COSINE",
                        }
                    },
                )
                print(table)

            .. code-block:: python
                :caption: Create table with integrated embedding

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>",  # or username="<user>", password="<pass>"
                    )
                )

                table = client.create_vector_table(
                    name="documents",
                    table_params={"auto_generate_id": True},
                    embed_params={
                        "model": "all_MiniLM_L12_v2",
                        "embed_metadata_jsonpath": "content",
                    },
                )
                print(table)

            .. code-block:: python
                :caption: Create table for bring-your-own vectors with manual indexing

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                table = client.create_vector_table(
                    name="customer_vectors",
                    comment="Manually managed vector table",
                    index_params={
                        "vector_index_params": {
                            "auto_index": False,
                        }
                    },
                )
                print(table)
        """
        return self._get_active_service().create_vector_table(
            name=name,
            comment=comment,
            annotations=annotations,
            table_params=table_params,
            embed_params=embed_params,
            index_params=index_params,
            debug_flags=debug_flags,
        )

    @validate_resource_names(name=InvalidTableNameFormatError)
    def describe_vector_table(self, name: str) -> VectorTableResponse:
        """
        Retrieve detailed configuration and metadata for a vector table.

        Returns comprehensive information about the specified table including its schema,
        index configuration, embedding settings, row count, and creation timestamp.

        :param name: Name of the vector table to describe.
        :type name: str

        Returns:
            ``VectorTableResponse`` describing the table.

            - Table name and description
            - Vector type and dimensions
            - Index parameters and status
            - Embedding model configuration (if applicable)
            - Row count and storage statistics
            - Annotations and metadata

        Example response::

                {
                    "table_name": "DEMO_PRODUCTS",
                    "owner": "VECTOR3",
                    "status": "Empty",
                    "vector_type": "dense",
                    "vector_table_type": "BYOV",
                    "index_params": {
                        "vector_index_params": {
                            "auto_index": true,
                            "organization": "PARTITIONS",
                            "advanced_params": {"partitions": 10}
                        },
                        "parallel_creation": 4
                    },
                    "annotations": {"metric": "cosine", "dimension": "5"},
                    "embed_params": null,
                    "created": "2026-03-12T11:21:30Z",
                    "description": "Demo table for SDK examples"
                }

        Key fields:

            - ``table_name``: Vector table identifier.
            - ``index_params``: Active index metadata (if configured).
            - ``annotations``: Custom metadata supplied at creation/update time.

        Raises:
            Exception: If the table does not exist.

        Example:

            .. code-block:: python
                :caption: Describe a table and print key attributes

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>",  # or username="<user>", password="<pass>"
                    )
                )

                details = client.describe_vector_table(name="product_vectors")
                print(details.to_dict())
        """
        return self._get_active_service().describe_vector_table(
            name=name,
        )

    @validate_resource_names(name=InvalidTableNameFormatError)
    def drop_vector_table(self, name: str) -> DropVectorTableResponse:
        """
        Permanently delete a vector table and all its data.

        Drops the specified vector table, including all vectors, metadata, and associated
        indexes. This operation cannot be undone.

        :param name: Name of the vector table to drop.
        :type name: str

        Returns:
            ``DropVectorTableResponse`` confirming the table was dropped
            successfully.

        Example response::

                {
                    "message": "Table DEMO_PRODUCTS deleted successfully"
                }

        Raises:
            Exception: If the table does not exist.

        Warning:
            This operation is irreversible. All data in the table will be permanently deleted.

        Example:

            .. code-block:: python
                :caption: Drop a table and inspect the response

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>",  # or username="<user>", password="<pass>"
                    )
                )

                response = client.drop_vector_table(name="old_vectors")
                print(response)
        """
        return self._get_active_service().drop_vector_table(
            name=name,
        )

    @validate_resource_names(name=InvalidTableNameFormatError)
    def update_vector_table_annotation(
        self,
        name: str,
        comment: Optional[str] = None,
        annotations: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> VectorTableResponse:
        """
        Update annotations for an existing vector table.

        Modifies table comment and annotations without affecting stored data.

        :param name: Name of the vector table to update.
        :type name: str
        :param comment: Updated table comment.
        :type comment: str, optional
        :param annotations: New annotations to replace existing ones.
            Annotations are completely replaced, not merged.
        :type annotations: dict, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``VectorTableResponse`` describing the updated table metadata.

            Example response::

                {
                    "table_name": "products",
                    "annotations": {"version": "2.0", "updated": "2025-01-27"},
                    "description": "Product embeddings"
                }

        Raises:
            Exception: If the table does not exist or invalid parameters provided.

        Note:
            Annotations are replaced entirely, not merged. To preserve existing
            annotations, include them in the update request.

        Example:

            .. code-block:: python

               from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                response = client.update_vector_table_annotation(
                    name='products',
                    comment='Updated product embeddings',
                    annotations={'version': '2.0', 'updated': '2025-01-27'}
                )
        """
        return self._get_active_service().update_vector_table_annotation(
            name=name,
            comment=comment,
            annotations=annotations,
            debug_flags=debug_flags,
        )

    @validate_resource_names(model_name=InvalidModelNameFormatError)
    def generate_embedding(
        self,
        model_name: str,
        inputs: List[Union[str, VectorEmbedInputItem]],
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> EmbeddingResponse:
        """
        Generate vector embeddings for text inputs using a loaded model.

        Converts text into dense vector representations using the specified embedding
        model. The model must be loaded in the database using ``load_model()`` first.

        :param model_name: Name of the loaded embedding model to use.
        :type model_name: str
        :param inputs: List of text inputs to embed. Can be list of dicts: ``[{'text': 'text1'}, {'text': 'text2'}]``
        :type inputs: list
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``EmbeddingResponse`` containing generated embeddings for each input.

            Example response::

                {
                    "data": [
                        {
                            "text": "Sample text to embed",
                            "embedding": [
                                0.0117027815,
                                0.00419755466,
                                -0.0301191173,
                                0.011317092,
                                0.0763486549
                            ]
                        }
                    ]
                }

        Raises:
            Exception: If the model is not loaded or inputs are invalid.

        Example:

            .. code-block:: python
                :caption: Load a model, generate embeddings, and inspect the response

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                client.load_model(
                    model_name="all-MiniLM-L6-v2",
                    url="https://objectstorage.example.com/bucket/all-MiniLM-L6-v2.onnx",
                    model_params={"provider": "database", "credential": "OCI_CREDENTIAL"},
                )

                embeddings = client.generate_embedding(
                    model_name="all-MiniLM-L6-v2",
                    inputs=[
                        "Wireless noise-cancelling headphones",
                        "Ergonomic office chair with lumbar support",
                    ],
                )

                print(embeddings.to_dict()["data"][0]["embedding"])
        """
        return self._get_active_service().generate_embedding(
            model_name=model_name,
            inputs=inputs,
            debug_flags=debug_flags,
        )

    @validate_resource_names(table_name=InvalidTableNameFormatError)
    def upsert_vectors(
        self,
        table_name: str,
        vectors: List[Union[UpsertVectorsRequestVectorsInner, Dict[str, Any]]],
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> UpsertVectorsResponse:
        """
        Insert or update vectors in a table.

        Upserts vectors into the specified table. If a vector with the same ID already
        exists, it will be updated with the new values. Otherwise, a new record is inserted.

        :param table_name: Name of the vector table.
        :type table_name: str
        :param vectors: List of vectors to upsert. Each vector can be:
            - Dict with 'id', 'dense_vector', and 'metadata' keys
            - For tables with embedding models: Dict with 'id' and 'metadata'
            (vector generated automatically from configured metadata field)
        :type vectors: list
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        If table is configured with auto generated as True, then you don't need to provide id as part of the upsert object.

        For tables with integrated embedding models, you can provide text in metadata as one of the values with embed_metadata_jsonpath configured earlier as key
        and embeddings will be generated automatically.

        Returns:
            ``UpsertVectorsResponse`` confirming how many vectors were upserted.

            Example response::

                {
                    "upserted_count": 10
                }

        Raises:
            Exception: If the table does not exist or vector format is invalid.

        Example:

            .. code-block:: python
                :caption: Upsert pre-computed vectors

                response = client.upsert_vectors(
                    table_name='products',
                    vectors=[
                        {
                            'id': 'prod_1',
                            'dense_vector': [0.1, 0.2, 0.3, 0.4, 0.5],
                            'metadata': {
                                'name': 'Wireless Headphones',
                                'category': 'electronics',
                                'price': 99.99
                            }
                        },
                        {
                            'id': 'prod_2',
                            'dense_vector': [0.2, 0.3, 0.1, 0.5, 0.4],
                            'metadata': {
                                'name': 'Smart Watch',
                                'category': 'electronics',
                                'price': 199.99
                            }
                        }
                    ]
                )
                print(response)

            .. code-block:: python
                :caption: Upsert with automatic embedding (table must have embed_params configured)

                response = client.upsert_vectors(
                    table_name='documents',
                    vectors=[
                        {
                            'id': 'doc_1',
                            'metadata': {
                                'content': 'Machine learning is transforming healthcare',
                                'category': 'AI',
                                'author': 'John Doe'
                            }
                        },
                        {
                            'id': 'doc_2',
                            'metadata': {
                                'content': 'Vector databases enable semantic search',
                                'category': 'Database',
                                'author': 'Jane Smith'
                            }
                        }
                    ]
                )
                print(response)

        Requests are automatically split so each JSON payload stays within the
        service's 32 MiB limit. Input order is preserved and successful batch
        responses are aggregated. IDs are not deduplicated and service rate
        limits are not guaranteed to be avoided.
        """
        if not vectors:
            raise InvalidVectorsError()
        payload_size = self._upsert_vectors_json_size(vectors)
        if payload_size <= _MAX_UPSERT_BATCH_BYTES:
            return self._get_active_service().upsert_vectors(
                table_name=table_name,
                vectors=vectors,
                debug_flags=debug_flags,
            )
        return self._upsert_vectors_in_batches(
            table_name=table_name,
            vectors=vectors,
            debug_flags=debug_flags,
        )

    def _upsert_vectors_json_size(
        self,
        vectors: List[Union[UpsertVectorsRequestVectorsInner, Dict[str, Any]]],
    ) -> int:
        """Return the compact JSON size of the vectors array."""
        sizes = [self._upsert_vector_json_size(vector) for vector in vectors]
        for size in sizes:
            if size + _UPSERT_ARRAY_OVERHEAD_BYTES > _MAX_UPSERT_BATCH_BYTES:
                raise VectorPayloadTooLargeError(size, _MAX_UPSERT_BATCH_BYTES)
        return (
            _UPSERT_ARRAY_OVERHEAD_BYTES + sum(sizes) + max(0, len(sizes) - 1)
        )

    def _upsert_vectors_in_batches(
        self,
        table_name: str,
        vectors: List[Union[UpsertVectorsRequestVectorsInner, Dict[str, Any]]],
        debug_flags: Optional[Dict[str, str]],
    ) -> UpsertVectorsResponse:
        """Submit size-bounded ordered batches and aggregate their counts."""
        total = 0
        has_count = False
        batch: List[Union[UpsertVectorsRequestVectorsInner, Dict[str, Any]]] = (
            []
        )
        batch_size = 2  # account for the JSON array brackets and separators
        for vector in vectors:
            vector_size = self._upsert_vector_json_size(vector)
            if (
                vector_size + _UPSERT_ARRAY_OVERHEAD_BYTES
                > _MAX_UPSERT_BATCH_BYTES
            ):
                raise VectorPayloadTooLargeError(
                    vector_size, _MAX_UPSERT_BATCH_BYTES
                )
            if batch and batch_size + vector_size + 1 > _MAX_UPSERT_BATCH_BYTES:
                total, has_count = self._submit_upsert_batch(
                    table_name, batch, debug_flags, total, has_count
                )
                batch = []
                batch_size = 2
            batch.append(vector)
            batch_size += vector_size + 1
        if batch:
            total, has_count = self._submit_upsert_batch(
                table_name, batch, debug_flags, total, has_count
            )
        return UpsertVectorsResponse(
            upserted_count=total if has_count else None
        )

    @staticmethod
    def _upsert_vector_json_size(
        vector: Union[UpsertVectorsRequestVectorsInner, Dict[str, Any]],
    ) -> int:
        value: Any = vector
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json")
        try:
            # Match the generated client's default JSON encoding, including
            # whitespace. Compact JSON underestimates the wire payload and can
            # still produce ORA-40604 near the 32 MiB service limit.
            return len(json.dumps(value).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise TypeError(
                "vectors must contain JSON-serializable records"
            ) from exc

    def _submit_upsert_batch(
        self,
        table_name: str,
        batch: List[Any],
        debug_flags: Optional[Dict[str, str]],
        total: int,
        has_count: bool,
    ) -> tuple[int, bool]:
        response = self._get_active_service().upsert_vectors(
            table_name=table_name, vectors=batch, debug_flags=debug_flags
        )
        count = (
            response.get("upserted_count")
            if isinstance(response, dict)
            else response.upserted_count
        )
        if count is not None:
            total += count
            has_count = True
        return total, has_count

    @validate_resource_names(table_name=InvalidTableNameFormatError)
    def list_vectors(
        self,
        table_name: str,
        ids: Optional[List[str]] = None,
        limit: int = 15,
        offset: Optional[Union[float, int]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> VectorCollectionResponse:
        """
        Retrieve vectors from a table by their IDs.

        Lists vector records with their IDs, embeddings, and metadata. Supports
        pagination for large result sets.

        :param table_name: Name of the vector table.
        :type table_name: str
        :param ids: List of vector IDs to retrieve. Example: ``['id1', 'id2', 'id3']``.
        :type ids: list
        :param limit: Maximum number of results to return. Defaults to 15.
        :type limit: int, optional
        :param offset: Number of records to skip for pagination.
        :type offset: int, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``VectorCollectionResponse`` containing matching vectors.

                - IDs
                - Dense vectors
                - Metadata

        Example response::

                {
                    "items": [
                        {
                            "id": "prod_010",
                            "dense_vector": [0.21, 0.19, 0.24, 0.47, 0.40],
                            "metadata": {
                                "name": "Halo Headphones",
                                "category": "electronics",
                                "price": 199.0,
                                "color": "onyx"
                            }
                        },
                        {
                            "id": "prod_003",
                            "dense_vector": [0.08, 0.25, 0.34, 0.41, 0.50],
                            "metadata": {
                                "name": "Zephyr Running Tee",
                                "category": "apparel",
                                "price": 39.95,
                                "color": "light grey"
                            }
                        }
                    ],
                    "limit": 15,
                    "offset": 0,
                    "count": 10
                }

        Example:

            .. code-block:: python
                :caption: Get specific vectors by ID

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                vectors = client.list_vectors(
                    table_name='products',
                    ids=['prod_1', 'prod_2', 'prod_3']
                )

            .. code-block:: python
                :caption: Paginate through results (First 10 results)

                page1 = client.list_vectors(
                    table_name='products',
                    limit=10,
                    offset=0
                )

            .. code-block:: python
                :caption: Next 10 results

                page2 = client.list_vectors(
                    table_name='products',
                    limit=10,
                    offset=10
                )
        """
        return self._get_active_service().list_vectors(
            table_name=table_name,
            ids=ids,
            limit=limit,
            offset=offset,
            debug_flags=debug_flags,
        )

    # VectorApi methods
    @validate_resource_names(table_name=InvalidTableNameFormatError)
    def delete_vectors(
        self,
        table_name: str,
        ids: List[str],
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> DeleteVectorsResponse:
        """
        Delete vectors from a table by their IDs.

        Removes the specified vectors and their associated metadata from the table.
        Essentially delete the rows from the table for the given IDs.

        :param table_name: Name of the vector table.
        :type table_name: str
        :param ids: List of vector IDs to delete. Example: ``['id1', 'id2', 'id3']``.
        :type ids: list
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``DeleteVectorsResponse`` confirming deletion.

        Example response::

                {
                    "message": "Deleted 3 vector records"
                }

        Raises:
            Exception: If the table does not exist.

        Example:

            .. code-block:: python
                :caption: Delete specific vectors

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                response = client.delete_vectors(
                    table_name='products',
                    ids=['prod_old_1', 'prod_old_2', 'prod_old_3']
                )
                print(response)
        """
        return self._get_active_service().delete_vectors(
            table_name=table_name,
            ids=ids,
            debug_flags=debug_flags,
        )

    @validate_resource_names(table_name=InvalidTableNameFormatError)
    def load_vectors(
        self,
        table_name: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> JobResponse:
        """
        Bulk load vectors from a CSV file in object storage.

        Loads a large dataset from object storage into an existing vector table
        asynchronously. If the specified table does not exist, the service
        returns a not-found error. Existing rows are preserved and new vectors
        are appended to the table.

        :param table_name: Name of the existing target vector table.
        :type table_name: str
        :param url: Object storage URL pointing to the CSV file containing vectors.
        :type url: str
        :param params: Optional parameters for the load operation. Example: ``{'credential': 'OCI_CREDENTIAL'}`` if object storage URL requires authentication. Refer to the Oracle Cloud Infrastructure documentation for configuring object storage credentials: ``https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingcredentials.htm``.
        :type params: dict, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        The object storage URL should point to a CSV file with the following format:

        .. code-block:: text

            id,dense_vector,metadata
            id1,[0.1, 0.2, 0.3],{"field1": "value1", "field2": "value2"}
            id2,[0.4, 0.5, 0.6],{"field1": "value3", "field2": "value4"}

        The CSV file should have the following columns:

        - ``id``: Unique identifier for each vector.
        - ``dense_vector``: List of floating-point values representing the vector.
        - ``metadata``: JSON object containing additional metadata for the vector.

        Returns:
            ``JobResponse`` containing the load job ID and initial status.

        Example response::

                {
                    "job_name": "VECDB_LOAD_ABC123",
                    "job_creator": "VECTOR3",
                    "operation": "LOAD",
                    "state": "SUCCEEDED",
                    "links": [
                        {
                            "rel": "collection",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/"
                        },
                        {
                            "rel": "self",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/vecdb_load_abc123/"
                        },
                        {
                            "rel": "related",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/vecdb_load_abc123/jobfile"
                        }
                    ]
                }

        Example:

            .. code-block:: python
                :caption: Load vectors from object storage

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                response = client.load_vectors(
                    table_name='products',
                    url='https://objectstorage.region.oraclecloud.com/.../vectors.csv',
                    params={'credential': 'OCI_CREDENTIAL'}
                )

            .. code-block:: python
                :caption: Monitor load progress

                status = client.describe_vector_load_job(response.job_name)
        """
        return self._get_active_service().load_vectors(
            table_name=table_name,
            url=url,
            params=params,
            debug_flags=debug_flags,
        )

    def list_vector_load_jobs(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> JobCollectionResponse:
        """
        List all bulk load operations.

        Returns metadata for all load jobs including their states and progress.

        Returns:
            ``JobCollectionResponse`` containing load jobs with names, owners,
            states, and timestamps.

        Example response::

                {
                    "items": [
                        {
                            "job_name": "VECDB_LOAD_ABC123",
                            "job_creator": "VECTOR3",
                            "operation": "LOAD",
                            "state": "SUCCEEDED",
                            "links": [
                                {
                                    "rel": "self",
                                    "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/vecdb_load_abc123"
                                },
                                {
                                    "rel": "related",
                                    "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/vecdb_load_abc123/jobfile"
                                }
                            ]
                        }
                    ],
                    "count": 1
                }

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                jobs = client.list_vector_load_jobs()
        """
        return self._get_active_service().list_vector_load_jobs(
            limit=limit, offset=offset
        )

    @validate_resource_names(load_job_name=InvalidLoadJobNameFormatError)
    def describe_vector_load_job(self, load_job_name: str) -> JobResponse:
        """
        Get the status of a bulk load operation.

        Returns details about an asynchronous load job initiated by ``load_vectors()``.

        :param load_job_name: Name of the load job to describe.
        :type load_job_name: str

        Returns:
            ``JobResponse`` containing job status, progress, and statistics.

        Example response::

                {
                    "job_name": "VECDB_LOAD_ABC123",
                    "job_creator": "VECTOR3",
                    "operation": "LOAD",
                    "state": "SUCCEEDED",
                    "links": [
                        {
                            "rel": "collection",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/"
                        },
                        {
                            "rel": "self",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/vecdb_load_abc123/"
                        },
                        {
                            "rel": "related",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/vecdb_load_abc123/jobfile"
                        }
                    ]
                }

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                status = client.describe_vector_load_job(load_job_name='LOAD_JOB_67890')
        """
        return self._get_active_service().describe_vector_load_job(
            load_job_name=load_job_name,
        )

    @validate_resource_names(load_job_name=InvalidLoadJobNameFormatError)
    def get_vector_load_job_log(self, load_job_name: str) -> JobLogResponse:
        """
        Retrieve the log output for a bulk load job.

        :param load_job_name: Name of the load job.
        :type load_job_name: str

        Returns:
            ``JobLogResponse`` containing log file metadata and contents.

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                logs = client.get_vector_load_job_log(load_job_name='LOAD_JOB_67890')
        """
        # Validate job exists and has finished
        is_finished_job = False
        try:
            status = self.describe_vector_load_job(load_job_name)
            status_state = (
                status.get("state")
                if isinstance(status, dict)
                else status.state
            )
            is_finished_job = status_state in TERMINAL_STATES
        except VecDBException as error:
            if getattr(error, "status", None) != 404:
                raise
            # Job does not exist. Keep the resource-specific error available
            # through ``original_exception`` while retaining the facade's
            # normalized public exception contract.
            raise VecDBException.from_service_error(
                operation="get_vector_load_job_log",
                arguments={"kwargs": {"load_job_name": load_job_name}},
                service_name="OracleVecDB",
                error=ResourceNotFoundError(load_job_name),
            ) from error

        if not is_finished_job:
            # Job has not finished yet
            raise InvalidLoadJobLogError(load_job_name, status_state)

        # At this point, the job is finished, we can fetch its log
        return self._get_active_service().get_vector_load_job_log(
            load_job_name=load_job_name,
        )

    # SearchApi methods
    @validate_resource_names(table_name=InvalidTableNameFormatError)
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
        """
        The Query operation searches a vector table, using a query vector, text, or record ID.

        Performs similarity search to find the most similar vectors in the table.
        Supports filtering by metadata and various distance metrics.
        It retrieves the ids, metadata, vectors and similarity scores of the most similar items from the given table.

        :param table_name: Name of the vector table to search.
        :type table_name: str
        :param query_by:
            Query specification. One of:

            - ``{'vector': [0.1, 0.2, ...]}`` - Search by vector.
            - ``{'text': 'query text'}`` - Search by text (requires table with embedding
              model).
            - ``{'id': 'vector_id'}`` - Find similar vectors to an existing record.
        :type query_by: dict
        :param top_k: Number of most similar results to return.
        :type top_k: int
        :param filters:
            Metadata filters to narrow search results. Supports:

            - ``$eq``: Equal to.
            - ``$ne``: Not equal to.
            - ``$gt``, ``$gte``: Greater than (or equal).
            - ``$lt``, ``$lte``: Less than (or equal).
            - ``$in``, ``$nin``: In/not in array.
            - ``$and``, ``$or``: Logical operators.
            - ``$exists``: Field existence check.
        :type filters: dict, optional

            Example::

                {'category': {'$eq': 'electronics'}, 'price': {'$lt': 100}}

        :param advanced_options:
            Search tuning parameters that override index defaults.

            - ``distance_metric``: Optional per-query override. Supported values:
              ``COSINE``, ``MANHATTAN``, ``HAMMING``, ``JACCARD``, ``DOT``,
              ``EUCLIDEAN``, ``L2_SQUARED``, ``EUCLIDEAN_SQUARED``. See the
              class-level distance metric guidance table above for a summary
              of each metric and when to use it.
            - ``accuracy``: Target accuracy (0-100). Higher values provide better recall but
              slower search; ``100`` approximates an exact search.
            - ``idx_parameters``: Direct control of index knobs. Supported keys:

              - ``efsearch``: HNSW beam width controlling recall. Use this instead of accuracy to specify
                maximum number of candidates to be considered while probing the index. Higher values provide better accuracy.
              - ``neighbor partition probes``: IVF partition probes. Increasing the number of
                partitions scanned can improve recall for IVF indexes.

            For additional context, see Oracle’s vector index guidance:
            https://docs.oracle.com/en/database/oracle/oracle-database/26/vecse/create-vector-indexes-and-hybrid-vector-indexes.html
        :type advanced_options: dict, optional
        :param include_vectors: Include vector values in response.
            Defaults to False to minimize response size.
        :type include_vectors: bool, optional
        :param output_selector: Metadata keys to include in each result. An empty
            list projects no metadata; ``None`` returns full metadata.
        :type output_selector: list[str], optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            Search results for the query.

                - Each item contains ``id``, ``metadata``, ``distance``,
                  and ``vector`` (when ``include_vectors=True``)
                - Distance scores are lower-is-better for the common distance
                  metrics exposed by VecDB

        Example response::

                {
                    "items": [
                        {
                            "id": "prod_001",
                            "metadata": {
                                "name": "Aurora Trail Boots",
                                "category": "footwear",
                                "price": 129.99,
                                "color": "midnight blue"
                            },
                            "vector": null,
                            "distance": 0.0
                        },
                        {
                            "id": "prod_008",
                            "metadata": {
                                "name": "Glacier Insulated Bottle",
                                "category": "accessories",
                                "price": 34.0,
                                "color": "arctic white"
                            },
                            "vector": null,
                            "distance": 0.00393
                        }
                    ]
                }

        Example:

            .. code-block:: python
                :caption: Search by query vector

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                results = client.query(
                    table_name='products',
                    query_by={'vector': [0.1, 0.2, 0.3, ...]},
                    top_k=10
                )
                for index in range(len(results)):
                    item = results[index]
                    row = item if isinstance(item, dict) else item.model_dump()
                    print(row["id"])

            .. code-block:: python
                :caption: Search by text with filtering

                results = client.query(
                    table_name='products',
                    query_by={'text': 'wireless headphones'},
                    top_k=5,
                    filters={
                        '$and': [
                            {'category': {'$eq': 'electronics'}},
                            {'price': {'$lt': 200}}
                        ]
                    }
                )

            .. code-block:: python
                :caption: Find similar items to an existing product

                results = client.query(
                    table_name='products',
                    query_by={'id': 'prod_12345'},
                    top_k=10,
                    filters={'category': {'$eq': 'electronics'}}
                )

            .. code-block:: python
                :caption: Search with custom distance metric

                results = client.query(
                    table_name='products',
                    query_by={'text': 'laptop'},
                    top_k=10,
                    advanced_options={
                        'distance_metric': 'EUCLIDEAN',
                        'accuracy': 95,
                        'idx_parameters': {
                            'efsearch': 128,
                            'neighbor partition probes': 4
                        }
                    },
                    include_vectors=True
                )
                print(results)
        """
        return self._get_active_service().query(
            table_name=table_name,
            query_by=query_by,
            top_k=top_k,
            filters=filters,
            advanced_options=advanced_options,
            include_vectors=include_vectors,
            output_selector=output_selector,
            debug_flags=debug_flags,
        )

    # SummaryApi methods

    def rerank(
        self,
        query: str,
        documents: List[str],
        model_name: str,
        model_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> RerankResponse:
        """
        Re-rank search results based on relevance to a query.

        Uses a reranking model to score and reorder documents relative to a query.
        This improves search quality by performing a more detailed comparison between
        the query and each candidate document.

        :param query: The search query text.
        :type query: str
        :param documents: List of documents to rerank. Typically the results from
            ``query``.
        :type documents: list
        :param model_name: Name of the loaded reranking model.
        :type model_name: str
        :param model_params: Model configuration. Example:
            ``{'top_n': 5}`` to return only top 5 reranked results.
        :type model_params: dict, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``RerankResponse`` with reranked items available under ``items``.

            Example::

                {
                    "items": [
                        {
                            "index": 0,
                            "score": 0.82
                        }
                    ]
                }

        Raises:
            Exception: If the model is not loaded or inputs are invalid.

        Example:

            .. code-block:: python
                :caption: First, perform initial search

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                search_results = client.query(
                    table_name='documents',
                    query_by={'text': 'machine learning'},
                    top_k=20
                )

            .. code-block:: python
                :caption: Then rerank for better relevance

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                def metadata_for(result):
                    row = result if isinstance(result, dict) else result.model_dump()
                    return row.get("metadata") or {}

                documents = []
                for index in range(len(search_results)):
                    metadata = metadata_for(search_results[index])
                    if "content" in metadata:
                        documents.append(metadata["content"])

                reranked = client.rerank(
                    query='machine learning applications in healthcare',
                    documents=documents,
                    model_name='cohere-rerank-3.5',
                    model_params={'top_n': 5}
                )
                for item in reranked.items:
                    original = search_results[item.index]
                    metadata = metadata_for(original)
                    print(f"{item.score:.3f} - {metadata['content']}")

        """
        return self._get_active_service().rerank(
            query=query,
            documents=documents,
            model_name=model_name,
            model_params=model_params,
            debug_flags=debug_flags,
        )

    # ModelApi methods

    # IndexApi methods
    @validate_resource_names(table_name=InvalidTableNameFormatError)
    def create_index(
        self,
        table_name: str,
        index_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> JobResponse:
        """
        Create a vector index on a table to enable fast similarity search.

        Creates an index for efficient approximate nearest neighbor (ANN) search.
        The index creation runs asynchronously as a background job. Use ``describe_index()``
        or ``describe_index_job()`` to monitor progress.

        Supports IVF (Inverted File) and HNSW (Hierarchical Navigable Small World) indexes.
        When ``index_params`` are omitted, ORDS creates an index with server-side
        defaults. The 26.2 request model uses nested ``vector_index_params`` and
        ``metadata_index_params`` objects.

        :param table_name: Name of the vector table to index.
        :type table_name: str
        :param index_params: 26.2 index configuration. Accepted top-level keys
            are ``vector_index_params``, ``metadata_index_params``, and
            ``parallel_creation``. ``vector_index_params`` may include
            ``auto_index``, ``organization``, ``distance_metric``, ``accuracy``,
            ``online_build``, ``quantization_type``, ``compression_ratio``,
            ``distribute_params``, and ``advanced_params``. ``metadata_index_params``
            may include ``auto_index``, ``include_paths``, and ``exclude_paths``.

            Example:
            ``{'vector_index_params': {'organization': 'INMEMORY GRAPH', 'distance_metric': 'COSINE', 'advanced_params': {'neighbors': 32, 'efConstruction': 200}}, 'parallel_creation': 4}``

        :type index_params: dict, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``JobResponse`` containing the index job ID and status.

        Example:

            .. code-block:: python
                :caption: Create index with default IVF settings

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                response = client.create_index(table_name='products')

            .. code-block:: python
                :caption: Create HNSW index with custom parameters

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                response = client.create_index(
                    table_name='products',
                    index_params={
                        'vector_index_params': {
                            'auto_index': True,
                            'organization': 'INMEMORY GRAPH',
                            'distance_metric': 'COSINE',
                            'quantization_type': 'SCALAR',
                            'compression_ratio': 4,
                            'distribute_params': {
                                'distribute_method': 'AUTO'
                            },
                            'advanced_params': {
                                'neighbors': 32,
                                'efConstruction': 200,
                                'rescore_factor': 10,
                                'algorithm': 'uniform_quantization'
                            }
                        },
                        'metadata_index_params': {
                            'auto_index': True,
                            'include_paths': ['tenant', 'category'],
                            'exclude_paths': ['body']
                        },
                        'parallel_creation': 4
                    }
                )
                print(response)

            .. code-block:: python
                :caption: Create IVF index with explicit defaults

                response = client.create_index(
                    table_name='products',
                    index_params={
                        'vector_index_params': {
                            'organization': 'PARTITIONS',
                            'distance_metric': 'COSINE',
                            'advanced_params': {
                                'partitions': 16
                            }
                        }
                    }
                )
                print(response)

            .. code-block:: python
                :caption: Monitor index creation progress

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                status = client.describe_index(table_name='products')
        """
        return self._get_active_service().create_index(
            table_name=table_name,
            index_params=index_params,
            debug_flags=debug_flags,
        )

    def list_index_jobs(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> JobCollectionResponse:
        """
        List all index build and rebuild jobs.

        Returns metadata for all CREATE and REBUILD index operations, including
        their current states and progress.

        Returns:
            ``JobCollectionResponse`` containing index job metadata.

                - Job names
                - Owners
                - States (SCHEDULED, RUNNING, SUCCEEDED, FAILED)
                - Start/end timestamps
                - Log file paths

        Example response::

                {
                    "items": [
                        {
                            "job_name": "VECDB_CREATE_INDEX_ABC123",
                            "job_creator": "VECTOR3",
                            "operation": "CREATE",
                            "state": "SUCCEEDED",
                            "links": [
                                {
                                    "rel": "self",
                                    "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/jobs/vecdb_create_index_abc123/"
                                },
                                {
                                    "rel": "related",
                                    "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/jobs/vecdb_create_index_abc123/jobfile"
                                }
                            ]
                        }
                    ],
                    "count": 1
                }
        """
        return self._get_active_service().list_index_jobs(
            limit=limit, offset=offset
        )

    @validate_resource_names(index_job_name=InvalidIndexJobNameFormatError)
    def describe_index_job(self, index_job_name: str) -> JobResponse:
        """
        Retrieve metadata and status for a specific index build job.

        Returns details about an asynchronous index creation or rebuild job, including
        its current state, progress, owner, and log file location.

        :param index_job_name: Name of the index job to describe.
        :type index_job_name: str

        Returns:
            ``JobResponse`` describing the index job.

                - Job name and owner
                - Job state (SCHEDULED, RUNNING, SUCCEEDED, FAILED)
                - Start and end timestamps
                - Log file path
                - Error messages (if failed)

        Example response::

                {
                    "job_name": "VECDB_CREATE_INDEX_ABC123",
                    "job_creator": "VECTOR3",
                    "operation": "CREATE",
                    "state": "SUCCEEDED",
                    "links": [
                        {
                            "rel": "collection",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/jobs/"
                        },
                        {
                            "rel": "self",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/jobs/vecdb_create_index_abc123/"
                        },
                        {
                            "rel": "related",
                            "href": "https://<host>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/jobs/vecdb_create_index_abc123/jobfile"
                        }
                    ]
                }

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                job_status = client.describe_index_job(index_job_name='INX_JOB_12345')
                print(job_status)
        """
        return self._get_active_service().describe_index_job(
            index_job_name=index_job_name,
        )

    @validate_resource_names(index_job_name=InvalidIndexJobNameFormatError)
    def get_index_job_log(self, index_job_name: str) -> JobLogResponse:
        """
        Retrieve the log output for an index build job.

        Returns the detailed log file contents for diagnosing index creation issues
        or monitoring progress.

        :param index_job_name: Name of the index job.
        :type index_job_name: str

        Returns:
            ``JobLogResponse`` containing log file metadata and contents.

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                logs = client.get_index_job_log(index_job_name='INX_JOB_12345')
        """
        # Validate job exists and has finished
        is_finished_job = False
        try:
            status = self.describe_index_job(index_job_name)
            status_state = (
                status.get("state")
                if isinstance(status, dict)
                else status.state
            )
            is_finished_job = status_state in TERMINAL_STATES
        except VecDBException as error:
            if getattr(error, "status", None) != 404:
                raise
            # Job does not exist. Keep the resource-specific error available
            # through ``original_exception`` while retaining the facade's
            # normalized public exception contract.
            raise VecDBException.from_service_error(
                operation="get_index_job_log",
                arguments={"kwargs": {"index_job_name": index_job_name}},
                service_name="OracleVecDB",
                error=ResourceNotFoundError(index_job_name),
            ) from error

        if not is_finished_job:
            # Job has not finished yet
            raise InvalidIndexJobLogError(index_job_name, status_state)

        # At this point, the job is finished, we can fetch its log
        return self._get_active_service().get_index_job_log(
            index_job_name=index_job_name,
        )

    @validate_resource_names(table_name=InvalidTableNameFormatError)
    def rebuild_index(
        self,
        table_name: str,
        index_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> JobResponse:
        """
        Rebuild an existing vector index with updated parameters.

        Recreates the index, optionally with new configuration parameters. Useful for
        optimizing search performance or adjusting to changed data distributions.
        The rebuild runs asynchronously as a background job.

        :param table_name: Name of the vector table.
        :type table_name: str
        :param index_params: Rebuild configuration using the 26.2
            ``VectorIndexParams`` shape. Use ``index_type`` to scope the rebuild
            to ``'vector'``, ``'metadata'``, or ``'all'``. ``parallel_creation``
            controls the optional parallel DDL degree. ``vector_index_params``
            and ``metadata_index_params`` mirror ``create_index()``.
        :type index_params: dict, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``JobResponse`` containing the rebuild job ID and status.

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                # Rebuild all indexes with parallel DDL.
                response = client.rebuild_index(
                    table_name='products',
                    index_params={
                        'index_type': 'all',
                        'parallel_creation': 4
                    }
                )
                print(response)
        """
        return self._get_active_service().rebuild_index(
            table_name=table_name,
            index_params=index_params,
            debug_flags=debug_flags,
        )

    # InferenceApi methods

    @validate_resource_names(table_name=InvalidTableNameFormatError)
    def describe_index(self, table_name: str) -> IndexDescriptionResponse:
        """
        Get the current status and configuration of a vector table's index.

        Returns detailed information about the index including its type, parameters,
        build status, and statistics.

        :param table_name: Name of the vector table.
        :type table_name: str

        Returns:
            ``IndexDescriptionResponse``. The current generated ORDS schema only
            exposes ``index_status`` on this endpoint.

        Raises:
            Exception: If the table or index does not exist.

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                status = client.describe_index(table_name='products')
                print(status)
        """
        return self._get_active_service().describe_index(
            table_name=table_name,
        )

    @validate_resource_names(table_name=InvalidTableNameFormatError)
    def drop_index(
        self,
        table_name: str,
        index_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> DropIndexResponse:
        """
        Drop the vector index from a table.

        Removes the index while preserving the table and its data. Queries will
        fall back to exact search until a new index is created.
        ORDS 26.2 requires a request body for this operation. Pass
        ``index_params`` using the OpenAPI ``VectorIndexParams`` shape, such as
        ``{'index_type': 'all'}``, ``{'index_type': 'vector'}``, or
        ``{'index_type': 'metadata'}``.

        :param table_name: Name of the vector table.
        :type table_name: str
        :param index_params: Index deletion scope and options.
        :type index_params: dict, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``DropIndexResponse`` confirming index deletion.
            Example response::

                {
                    "message": "Index drop request submitted."
                }

        Raises:
            Exception: If the table or index does not exist.

        Example:

            .. code-block:: python
                :caption: Drop an index and inspect the response

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                result = client.drop_index(
                    table_name="products",
                    index_params={"index_type": "all"},
                )
                print(result)
        """
        return self._get_active_service().drop_index(
            table_name=table_name,
            index_params=index_params,
            debug_flags=debug_flags,
        )

    def list_models(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> ModelCollectionResponse:
        """
        List all loaded embedding and reranking models.

        Returns information about all models available for use in the database,
        limited to models currently loaded in the service.

        Returns:
            ``ModelCollectionResponse`` containing:
                - Model names
                - Types (embedding, reranking)
                - Algorithms
                - Creation timestamps
                - Attributes and parameters

            Example response::

                {
                    "items": [
                        {
                            "model_name": "ALL_MINILM_L12_V2",
                            "algorithm": "ONNX",
                            "mining_function": "EMBEDDING",
                            "creation_date": "2026-01-27T07:23:21Z",
                            "attributes": [
                                {
                                    "name": "DATA",
                                    "value": "TEXT",
                                    "data_type": "VARCHAR2",
                                    "data_length": 32767
                                },
                                {
                                    "name": "ORA$ONNXTARGET",
                                    "value": "VECTOR",
                                    "data_type": "VECTOR",
                                    "data_length": 1593,
                                    "vector_info": "VECTOR(384,FLOAT32)"
                                }
                            ]
                        }
                    ]
                }

            Each entry describes a loaded model; models available in storage but
            not yet loaded are not included.

        Example:

            .. code-block:: python
                :caption: List loaded models and print their names

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>",
                    )
                )

                models = client.list_models()
                print([item.model_name for item in models.items or []])
        """
        return self._get_active_service().list_models(
            limit=limit, offset=offset
        )

    @validate_resource_names(model_name=InvalidModelNameFormatError)
    def load_model(
        self,
        model_name: str,
        url: str,
        model_params: Optional[Dict[str, Any]] = None,
        debug_flags: Optional[Dict[str, str]] = None,
    ) -> ModelResponse:
        """
        Load an embedding or reranking model into the database.

        Imports a model from object storage (ONNX format) for use in embedding
        generation and reranking operations. Once loaded, the model can be used
        for integrated table embeddings or standalone inference.

        :param model_name: Unique name to assign to the loaded model.
        :type model_name: str
        :param url: Object storage URL where the model file is located.
            Supports Oracle Object Storage URLs and public URLs.
        :type url: str
        :param model_params: Model loading parameters. Example:
            ``{'provider': 'database', 'credential': 'OCI_CRED', 'metadata': {...}}``.
        :type model_params: dict, optional
        :param debug_flags: Debug configuration for detailed logging.
        :type debug_flags: dict, optional

        Returns:
            ``ModelResponse`` confirming model metadata after loading.

            Example response::

                {
                    "model_name": "SAMPLE_MODEL",
                    "algorithm": "ONNX",
                    "mining_function": "EMBEDDING",
                    "creation_date": "2026-03-12T11:27:21Z",
                    "attributes": [
                        {
                            "name": "DATA",
                            "value": "TEXT",
                            "data_type": "VARCHAR2",
                            "data_length": 32767
                        },
                        {
                            "name": "ORA$ONNXTARGET",
                            "value": "VECTOR",
                            "data_type": "VECTOR",
                            "data_length": 1593,
                            "vector_info": "VECTOR(384,FLOAT32)"
                        }
                    ]
                }

        Raises:
            Exception: If model already exists or URL is inaccessible.

        Example:

            .. code-block:: python
                :caption: Load model from Oracle Object Storage

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                response = client.load_model(
                    model_name='all-MiniLM-L6-v2',
                    url='https://objectstorage.us-phoenix-1.oraclecloud.com/n/namespace/b/bucket/o/model.onnx',
                    model_params={
                        'provider': 'database',
                        'credential': 'OCI_CREDENTIAL'
                    }
                )
                print(response)

            .. code-block:: python
                :caption: Verify model was loaded

                models = client.list_models()
                print([item.model_name for item in models.items or []])
        """
        return self._get_active_service().load_model(
            model_name=model_name,
            url=url,
            model_params=model_params,
            debug_flags=debug_flags,
        )

    @validate_resource_names(model_name=InvalidModelNameFormatError)
    def describe_model(self, model_name: str) -> ModelResponse:
        """
        Retrieve detailed metadata for a loaded model.

        Returns comprehensive information about the model including its type,
        parameters, attributes, and usage statistics.

        :param model_name: Name of the model to describe.
        :type model_name: str

        Returns:
            ``ModelResponse`` containing:
                - Model name and type
                - Algorithm and mining function
                - Input/output attributes
                - Creation timestamp
                - Model parameters

            Example response::

                {
                    "model_name": "ALL_MINILM_L12_V2",
                    "algorithm": "ONNX",
                    "mining_function": "EMBEDDING",
                    "creation_date": "2026-01-27T07:23:21Z",
                    "attributes": [
                        {
                            "name": "DATA",
                            "value": "TEXT",
                            "data_type": "VARCHAR2",
                            "data_length": 32767
                        },
                        {
                            "name": "ORA$ONNXTARGET",
                            "value": "VECTOR",
                            "data_type": "VECTOR",
                            "data_length": 1593,
                            "vector_info": "VECTOR(384,FLOAT32)"
                        }
                    ]
                }

        Raises:
            Exception: If the model does not exist.

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                details = client.describe_model(model_name='all-MiniLM-L6-v2')
                print(details)
        """
        return self._get_active_service().describe_model(
            model_name=model_name,
        )

    @validate_resource_names(model_name=InvalidModelNameFormatError)
    def drop_model(self, model_name: str) -> DropModelResponse:
        """
        Remove a loaded model from the database.

        Drops the specified embedding or reranking model. Models currently in use
        by vector tables cannot be dropped and will throw an error.

        :param model_name: Name of the model to drop.
        :type model_name: str

        Returns:
            ``DropModelResponse`` confirming model deletion.

            Example response::

                {
                    "dropped": SAMPLE_MODEL,
                    "message": "Model SAMPLE_MODEL dropped successfully"
                }

        Raises:
            Exception: If the model does not exist or is still associated with a vector table.

        Example:

            .. code-block:: python

                from oracle_vecdb import OracleVecDB, Configuration

                client = OracleVecDB(
                    Configuration(
                        rest_url="https://<host>/ords/<schema>/_/db-api/stable/vecdb/",
                        access_token="<bearer-token>", # or username="<user>", password="<pass>"
                    )
                )

                response = client.drop_model(model_name='old-model')
                print(response)
        """
        return self._get_active_service().drop_model(
            model_name=model_name,
        )
