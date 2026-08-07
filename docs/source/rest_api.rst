REST API Reference
===================

.. contents::
   :local:
   :depth: 1

Authentication & Base URL
--------------------------

- Host template: ``https://<hostname>:<port>/ords/<schema>/_/db-api/stable/vecdb/``
- Headers: ``Authorization: Bearer <token>`` (Bearer or Basic), ``Content-Type: application/json``
- Most POST/PATCH operations accept optional ``debugFlags`` objects that raise VecDB tracing levels; when omitted, standard logging is used.

.. note::

   **debugFlags** is accepted by POST/PATCH endpoints. Each key accepts ``"low"``, ``"medium"``, or ``"high"``.
   Available keys: ``VECTOR_INDEX``, ``VECTOR_INDEX_NEIGHBOR_GRAPH``, ``VECTOR_INDEX_NEIGHBOR_GRAPH_BUILD``,
   ``VECTOR_INDEX_NEIGHBOR_GRAPH_MEM``, ``VECTOR_INDEX_NEIGHBOR_GRAPH_SEARCH``,
   ``VECTOR_INDEX_NEIGHBOR_GRAPH_APPCHNG``, ``VECTOR_INDEX_NEIGHBOR_GRAPH_STATS``,
   ``VECTOR_INDEX_NEIGHBOR_PARTITIONS``, ``VECTOR_INDEX_FIXED_VIEW``, ``VECIDX_TRANS``,
   ``VECIDX_TRANS_COM``, ``VECIDX_TRANS_PJ``, ``VECIDX_TRANS_PJ_DWNGRD``, ``VECIDX_TRANS_PJ_GROW``,
   ``VECIDX_TRANS_SJ``, ``VECIDX_TRANS_SJ_BG``, ``VEC_INDEX_CALIBRATION``, ``VECTOR_TRACE``.

Distance Metric Guidance
-------------------------

Use the following guidance anywhere a request accepts ``distance_metric``.

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

Models
-------

**GET /vecdb/models/**

List all loaded embedding and reranking models.

Returns information about all models available for use in the database,
limited to models currently loaded in the service.

**Returns**

JSON response containing an array of models with model names, types (embedding, reranking), algorithms, creation timestamps, and attributes and parameters.

.. code-block:: json
   :caption: Example 200 response

   {
     "items": [
       {
         "model_name": "all-MiniLM-L6-v2",
         "algorithm": "ONNX",
         "mining_function": "EMBEDDING",
         "creation_date": "2026-01-14T09:32:11Z",
         "attributes": [
           {
             "name": "NUM_DIMENSIONS",
             "value": "384",
             "data_type": "NUMBER",
             "data_length": 22,
             "vector_info": null
           }
         ]
       }
     ],
     "hasMore": false,
     "limit": 25,
     "offset": 0,
     "count": 1,
     "links": []
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/models/" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

----

**POST /vecdb/models/**

Load an embedding or reranking model into the database.

Imports a model from object storage (ONNX format) for use in embedding
generation and reranking operations. Once loaded, the model can be used
for integrated table embeddings or standalone inference.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``modelName``
     - string
     - Yes
     - Unique name to assign to the loaded model.
   * - ``url``
     - string
     - Yes
     - Object storage URL where the model file is located. Supports Oracle Object Storage URLs and public URLs.
   * - ``modelParams``
     - object
     - No
     - Model loading parameters. Example: ``{'provider': 'database', 'credential': 'OCI_CRED', 'metadata': {...}}``.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response confirming the model was loaded successfully.

.. code-block:: json
   :caption: Example 201 response

   {
     "model_name": "all-MiniLM-L6-v2",
     "algorithm": "ONNX",
     "mining_function": "EMBEDDING",
     "creation_date": "2026-02-01T18:45:09Z",
     "attributes": []
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/models/" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "modelName": "all-MiniLM-L6-v2",
       "url": "https://objectstorage.us-phoenix-1.oraclecloud.com/n/namespace/b/bucket/o/model.onnx",
       "modelParams": {
         "provider": "database",
         "credential": "OCI_CREDENTIAL"
       }
     }'

**Response 400** – the request body included invalid parameters.

**Response 404** – model not found.

----

**GET /vecdb/models/{model_name}**

Retrieve detailed metadata for a loaded model.

Returns comprehensive information about the model including its type,
parameters, attributes, and usage statistics.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``model_name``
     - string
     - Yes
     - Name of the model to describe.

**Returns**

JSON response containing the model name and type, algorithm and mining function, input/output attributes, creation timestamp, and model parameters.

.. code-block:: json
   :caption: Example 200 response

   {
     "model_name": "all-MiniLM-L6-v2",
     "algorithm": "ONNX",
     "mining_function": "EMBEDDING",
     "creation_date": "2026-01-14T09:32:11Z",
     "attributes": [
       {
         "name": "NUM_DIMENSIONS",
         "value": "384",
         "data_type": "NUMBER",
         "data_length": 22,
         "vector_info": null
       }
     ]
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/models/all-MiniLM-L6-v2" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

**Response 404** – model not found.

----

**DELETE /vecdb/models/{model_name}**

Remove a loaded model from the database.

Drops the specified embedding or reranking model. Models currently in use
by vector tables cannot be dropped and will throw an error.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``model_name``
     - string
     - Yes
     - Name of the model to drop.

**Returns**

JSON response confirming model deletion.

.. code-block:: json
   :caption: Example 200 response

   {
     "dropped": "YES",
     "message": "Model all-MiniLM-L6-v2 removed"
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X DELETE \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/models/all-MiniLM-L6-v2" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

**Response 400** – the model is used in a vector table and cannot be deleted.

**Response 404** – model not found.

----

Vector Tables
--------------

**GET /vecdb/summary**

Get summary statistics for the entire vector database service.


**Returns**

JSON response with database-level statistics including total tables, models, and vectors.

.. code-block:: json
   :caption: Example 200 response

   {
     "total_tables": 4,
     "total_vectors": 125000,
     "total_models": 2
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/summary" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

----

**GET /vecdb/vector-tables/**

List all vector tables in the database.

Returns a list of all vector tables accessible to the current user, including
their names and basic configuration details.

**Returns**

JSON response containing an array of table information including table names, descriptions, vector types, row counts, and creation timestamps.

.. code-block:: json
   :caption: Example 200 response

   {
     "items": [
       {
         "table_name": "documents",
         "vector_type": "dense",
         "status": "READY",
         "annotations": {"department": "knowledge"}
       },
       {
         "table_name": "product_vectors",
         "vector_type": "dense",
         "status": "READY"
       }
     ]
   }

Each entry contains ``table_name``, ``vector_type``, ``status``,
``index_params`` (if defined), and annotations.

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

----

**POST /vecdb/vector-tables/**

Create a new vector table for storing vector embeddings.

Creates a vector table with a fixed schema optimized for vector search. The table
includes columns for ID, vector data, and JSON metadata. You can configure automatic
ID generation, embedding integration, and index parameters during creation.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``name``
     - string
     - Yes
     - Name of the vector table to create. Must be unique within the database.
   * - ``comment``
     - string
     - No
     - Table comment.
   * - ``annotations``
     - object
     - No
     - Key-value pairs added to the vector table metadata. Example: ``{"application": "chatbot", "department": "sales"}``.
   * - ``tableParams``
     - object
     - No
     - Table creation controls. Use ``{"auto_generate_id": true}`` when the ID column should default to ``SYS_GUID()``.
   * - ``embedParams``
     - object
     - No
     - Configuration for integrated embedding model. If provided, the table will automatically generate embeddings on insert:

       .. code-block:: json

          {
            "model": "<hosted-model-name>",
            "embed_metadata_jsonpath": "<field name in metadata to embed>"
          }

   * - ``indexParams``
     - object
     - No
     - Nested 26.2 vector and metadata index configuration:

       .. code-block:: json

          {
            "vector_index_params": {
              "auto_index": true,
              "organization": "<PARTITIONS | INMEMORY GRAPH>",
              "distance_metric": "<COSINE | MANHATTAN | HAMMING | JACCARD | DOT | EUCLIDEAN | L2_SQUARED | EUCLIDEAN_SQUARED>",
              "accuracy": 90,
              "online_build": true,
              "quantization_type": "<NONE | SCALAR>",
              "compression_ratio": 4,
              "distribute_params": {
                "distribute_method": "<ROWID RANGE | SIMILARITY | PARTITION | SUBPARTITION | DISTRIBUTE | AUTO>"
              },
              "advanced_params": {
                "partitions": 16,
                "neighbors": 32,
                "efConstruction": 128,
                "rescore_factor": 10,
                "algorithm": "uniform_quantization"
              }
            },
            "metadata_index_params": {
              "auto_index": true,
              "include_paths": ["tenant", "category"],
              "exclude_paths": ["body"]
            },
            "parallel_creation": 4
          }

       ``partitions`` applies to ``PARTITIONS`` organization;
       ``neighbors`` and ``efConstruction`` apply to ``INMEMORY GRAPH`` organization.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response containing the created table details and status.

.. code-block:: json
   :caption: Example 201 response

   {
     "table_name": "product_vectors",
     "vector_type": "dense",
     "auto_generate_id": true,
     "vector_table_type": "BYOV",
     "index_params": {
       "vector_index_params": {
         "auto_index": true,
         "organization": "PARTITIONS"
       },
       "parallel_creation": 4
     },
     "annotations": {"application": "catalog"}
   }

.. code-block:: bash
   :caption: Example curl request – Create table for pre-computed vectors

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
      "name": "product_vectors",
      "comment": "Product embeddings",
      "tableParams": {
        "auto_generate_id": true
      },
      "indexParams": {
        "vector_index_params": {
          "auto_index": true,
          "organization": "PARTITIONS",
          "distance_metric": "COSINE"
        },
        "parallel_creation": 4
      },
      "annotations": {"application": "catalog"}
    }'

.. code-block:: bash
   :caption: Example curl request – Create table with integrated embedding

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
      "name": "documents",
      "tableParams": {
        "auto_generate_id": true
      },
      "embedParams": {
        "model": "all_MiniLM_L12_v2",
        "embed_metadata_jsonpath": "content"
       }
     }'

.. code-block:: bash
   :caption: Example curl request – Create table for bring-your-own vectors with manual indexing

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
      "name": "customer_vectors",
      "comment": "Manually managed vector table",
      "indexParams": {
        "vector_index_params": {
          "auto_index": false
        }
      }
    }'

**Response 400** – invalid or missing parameters (for example, missing ``name``).

**Response 409** – a table with that name already exists.

----

**GET /vecdb/vector-tables/{vector_table_name}**

Retrieve detailed configuration and metadata for a vector table.

Returns comprehensive information about the specified table including its schema,
index configuration, embedding settings, row count, and creation timestamp.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table to describe.

**Returns**

JSON response describing the table including table name and description, vector type and dimensions, index parameters and status, embedding model configuration (if applicable), row count and storage statistics, and annotations and metadata.

.. code-block:: json
   :caption: Example 200 response

   {
     "table_name": "product_vectors",
     "description": "Product embeddings",
     "vector_type": "dense",
     "index_params": {
       "distance_metric": "COSINE",
       "organization": "PARTITIONS"
     },
     "embed_params": null,
     "annotations": {"version": "1.0"},
     "created": "2026-01-31T09:12:42Z"
   }

Key fields:

- ``table_name``: Vector table identifier.
- ``index_params``: Active index metadata (if configured).
- ``annotations``: Custom metadata supplied at creation/update time.

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/product_vectors" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

**Response 404** – not found or precondition failed.

----

**PATCH /vecdb/vector-tables/{vector_table_name}**

Update the description and annotations for an existing vector table.

Modifies the metadata and configuration of a vector table without affecting
the stored data. Can update description, annotations, and index parameters.

.. note::

   Annotations are replaced entirely, not merged. To preserve existing
   annotations, include them in the update request.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table to update.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``description``
     - string
     - Yes
     - New description for the table.
   * - ``annotations``
     - object
     - No
     - New annotations to replace existing ones. Annotations are completely replaced, not merged.
   * - ``indexParams``
     - object
     - No
     - Updated index configuration parameters.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response confirming the update.

.. code-block:: json
   :caption: Example 202 response

   {
     "status": "ACCEPTED",
     "tableName": "products",
     "requestId": "c9b8f6a2-...",
     "message": "Update scheduled"
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X PATCH \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "description": "Updated product embeddings",
       "annotations": {
         "version": "2.0",
         "updated": "2026-02-10"
       }
     }'

**Response 400** – invalid JSON, invalid types, or missing required fields.

**Response 404** – not found or precondition failed.

----

**DELETE /vecdb/vector-tables/{vector_table_name}**

Permanently delete a vector table and all its data.

Drops the specified vector table, including all vectors, metadata, and associated
indexes. This operation cannot be undone.

.. warning::

   This operation is irreversible. All data in the table will be permanently deleted.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table to drop.

**Returns**

JSON response confirming the table was dropped successfully.

.. code-block:: json
   :caption: Example 200 response

   {
     "status": "SUCCEEDED",
     "message": "Table dropped successfully",
     "tableName": "old_vectors"
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X DELETE \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/old_vectors" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

**Response 404** – table not found.

Manage Data
------------

**POST /vecdb/embed**

Generate vector embeddings for text inputs using a loaded model.

Converts text into dense vector representations using the specified embedding
model. The model must be loaded in the database using ``POST /vecdb/models/`` first.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``modelName``
     - string
     - Yes
     - Name of the loaded embedding model to use.
   * - ``inputs``
     - array
     - Yes
     - Array of input objects to embed. Each entry contains ``text`` (string, required). Example: ``[{"text": "text1"}, {"text": "text2"}]``.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response containing the generated embeddings — an array of vectors corresponding to each input.

.. code-block:: json
   :caption: Example 200 response

   {
     "data": [
       {
         "embedding": [0.1, 0.2, 0.3, 0.4],
         "text": "Wireless headphones"
       },
       {
         "embedding": [0.5, 0.4, 0.3, 0.2],
         "text": "Ergonomic office chair"
       }
     ]
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/embed" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "modelName": "all-MiniLM-L6-v2",
       "inputs": [
         {"text": "Wireless noise-cancelling headphones"},
         {"text": "Ergonomic office chair with lumbar support"}
       ]
     }'

**Response 400** – the request body included invalid parameters.

----

**POST /vecdb/vector-tables/{vector_table_name}/upsert**

Insert or update vectors in a table.

Upserts vectors into the specified table. If a vector with the same ID already
exists, it will be updated with the new values. Otherwise, a new record is inserted.

If the table is configured with ``autoGenerateID: true``, you don't need to provide
``id`` as part of the upsert object. For tables with integrated embedding models, you
can provide text in metadata — embeddings will be generated automatically.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vectors``
     - array
     - Yes
     - Array of vector objects to upsert. Each entry contains ``id``, ``dense_vector``, and ``metadata``. For tables with embedding models, ``dense_vector`` can be omitted and the embedding will be generated automatically from the configured metadata field.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response confirming upsert with count of inserted/updated vectors.

.. code-block:: json
   :caption: Example 201 response

   {
     "upserted_count": 2
   }

.. code-block:: bash
   :caption: Example curl request – Upsert pre-computed vectors

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/upsert" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "vectors": [
         {
           "id": "prod_1",
           "dense_vector": [0.1, 0.2, 0.3, 0.4, 0.5],
           "metadata": {
             "name": "Wireless Headphones",
             "category": "electronics",
             "price": 99.99
           }
         },
         {
           "id": "prod_2",
           "dense_vector": [0.2, 0.3, 0.1, 0.5, 0.4],
           "metadata": {
             "name": "Smart Watch",
             "category": "electronics",
             "price": 199.99
           }
         }
       ]
     }'

.. code-block:: bash
   :caption: Example curl request – Upsert with automatic embedding (table must have embed_params configured)

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/documents/upsert" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
       "vectors": [
         {
           "id": "doc_1",
           "metadata": {
             "content": "Machine learning is transforming healthcare",
             "category": "AI",
             "author": "John Doe"
           }
         },
         {
           "id": "doc_2",
           "metadata": {
             "content": "Vector databases enable semantic search",
             "category": "Database",
             "author": "Jane Smith"
           }
         }
       ]
     }'

**Response 400** – the request body included invalid parameters.

**Response 404** – the specified vector table does not exist.

----

**POST /vecdb/vector-tables/{vector_table_name}/list**

Retrieve vectors from a table by their IDs.

Lists vector records with their IDs, embeddings, and metadata. Supports
pagination for large result sets.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``ids``
     - array of string
     - No
     - List of vector IDs to retrieve. Example: ``["id1", "id2", "id3"]``.
   * - ``limit``
     - number
     - No
     - Maximum number of results to return. Defaults to ``15``.
   * - ``offset``
     - number
     - No
     - Number of records to skip for pagination.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response containing matching vectors including IDs, dense vectors, and metadata.

.. code-block:: json
   :caption: Example 200 response

   {
     "items": [
       {
         "id": "prod_1",
         "dense_vector": [0.1, 0.2, 0.3, 0.4, 0.5],
         "metadata": {"name": "Wireless Headphones", "category": "electronics", "price": 99.99}
       },
       {
         "id": "prod_2",
         "dense_vector": [0.2, 0.3, 0.1, 0.5, 0.4],
         "metadata": {"name": "Smart Watch", "category": "electronics", "price": 199.99}
       }
     ],
     "limit": 15,
     "offset": 0,
     "count": 2
   }

.. code-block:: bash
   :caption: Example curl request – Get specific vectors by ID

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/list" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "ids": ["prod_1", "prod_2", "prod_3"],
       "limit": 15,
       "offset": 0
     }'

.. code-block:: bash
   :caption: Example curl request – Paginate through results (First 10 results)

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/list" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
       "limit": 10,
       "offset": 0
     }'

.. code-block:: bash
   :caption: Example curl request – Next 10 results

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/list" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
       "limit": 10,
       "offset": 10
     }'

**Response 400** – the request body included invalid parameters.

**Response 404** – the specified vector table does not exist.

----

**POST /vecdb/vector-tables/{vector_table_name}/delete**

Delete vectors from a table by their IDs.

Removes the specified vectors and their associated metadata from the table.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``ids``
     - array of string
     - Yes
     - List of vector IDs to delete. Example: ``["id1", "id2", "id3"]``.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response confirming deletion with count of deleted vectors.

.. code-block:: json
   :caption: Example 200 response

   {
     "message": "Vectors removed successfully."
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/delete" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "ids": ["prod_old_1", "prod_old_2", "prod_old_3"]
     }'

**Response 400** – the request body included invalid parameters.

**Response 404** – the specified vector table does not exist.

----

**POST /vecdb/load**

Bulk load vectors from a CSV file in object storage.

Loads a large dataset from object storage into an existing vector table
asynchronously. If the specified table does not exist, the service returns a
not-found error. If the table exists, the new vectors are appended.

The object storage URL should point to a CSV file with the following format:

.. code-block:: text

   id,dense_vector,metadata
   id1,[0.1, 0.2, 0.3],{"field1": "value1", "field2": "value2"}
   id2,[0.4, 0.5, 0.6],{"field1": "value3", "field2": "value4"}

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``tableName``
     - string
     - Yes
     - Name of the existing target vector table.
   * - ``url``
     - string
     - Yes
     - Object storage URL pointing to the CSV file containing vectors.
   * - ``params``
     - object
     - No
     - Optional parameters for the load operation. Example: ``{'credential': 'OCI_CREDENTIAL'}`` if the object storage URL requires authentication.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response containing the load job ID and initial status.

.. code-block:: json
   :caption: Example 200 response

   {
     "job_name": "LOAD_PRODUCTS_20260210",
     "job_creator": "VECDB_USER",
     "job_type": "SCHEDULED",
     "operation": "LOAD_CSV",
     "state": "SCHEDULED",
     "start_date": null,
     "links": [
       {"rel": "job", "href": "/vecdb/load/jobs/LOAD_PRODUCTS_20260210/"}
     ]
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/load" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "tableName": "products",
       "url": "https://objectstorage.region.oraclecloud.com/.../vectors.csv",
       "params": {
         "credential": "OCI_CREDENTIAL"
       }
     }'

**Response 400** – the request body included invalid parameters.

----

**GET /vecdb/load/jobs/**

List all bulk load operations.

Returns metadata for all load jobs including their states and progress.

**Returns**

JSON response containing an array of load jobs with job names, owners, states, and timestamps.

.. code-block:: json
   :caption: Example 200 response

   {
     "items": [
       {
         "job_name": "LOAD_PRODUCTS_20260210",
         "job_creator": "VECDB_USER",
         "job_type": "SCHEDULED",
         "operation": "LOAD_CSV",
         "state": "SUCCEEDED",
         "start_date": "2026-02-10T19:00:00Z",
         "links": [
           {"rel": "self", "href": "/vecdb/load/jobs/LOAD_PRODUCTS_20260210/"}
         ]
       }
     ],
     "hasMore": false,
     "limit": 25,
     "offset": 0,
     "count": 1,
     "links": []
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

----

**GET /vecdb/load/jobs/{load_job_name}/**

Get the status of a bulk load operation.

Returns details about an asynchronous load job initiated by ``POST /vecdb/load``.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``load_job_name``
     - string
     - Yes
     - Name of the load job to describe.

**Returns**

JSON response containing job status, progress, and statistics.

.. code-block:: json
   :caption: Example 200 response

   {
     "job_name": "LOAD_PRODUCTS_20260210",
     "job_creator": "VECDB_USER",
     "job_type": "SCHEDULED",
     "operation": "LOAD_CSV",
     "state": "SUCCEEDED",
     "start_date": "2026-02-10T19:00:00Z",
     "links": [
       {"rel": "self", "href": "/vecdb/load/jobs/LOAD_PRODUCTS_20260210/"},
       {"rel": "jobfile", "href": "/vecdb/load/jobs/LOAD_PRODUCTS_20260210/jobfile"}
     ]
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/LOAD_JOB_67890/" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

----

**GET /vecdb/load/jobs/{load_job_name}/jobfile**

Retrieve the log output for a bulk load job.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``load_job_name``
     - string
     - Yes
     - Name of the load job.

**Returns**

JSON response containing log file metadata and contents.

.. code-block:: json
   :caption: Example 200 response

   {
     "log_date": "2026-02-10T19:12:45Z",
     "job_name": "LOAD_PRODUCTS_20260210",
     "status": "INFO",
     "error#": 0,
     "additional_info": "Loaded 500 rows",
     "actual_start_date": "2026-02-10T19:00:05Z",
     "run_duration": "+000 00:12:40.000",
     "links": []
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/load/jobs/LOAD_JOB_67890/jobfile" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

Search Data
------------

**POST /vecdb/vector-tables/{vector_table_name}/query**

Perform a vector similarity search using text, a vector, or an ID.

Performs similarity search to find the most similar vectors in the table.
Supports filtering by metadata and various distance metrics. Retrieves the
IDs, metadata, vectors and similarity scores of the most similar items.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table to search.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``queryBy``
     - object
     - Yes
     - Query specification. One of: ``{'vector': [0.1, 0.2, ...]}`` (search by vector), ``{'text': 'query text'}`` (search by text, requires table with embedding model), ``{'id': 'vector_id'}`` (find similar vectors to an existing record).
   * - ``topK``
     - number
     - Yes
     - Number of most similar results to return.
   * - ``includeVectors``
     - boolean
     - No
     - Include vector values in response. Defaults to ``false`` to minimize response size.
   * - ``filters``
     - object
     - No
     - Metadata filters to narrow search results. Supported operators: ``$eq``, ``$ne``, ``$gt``, ``$gte``, ``$lt``, ``$lte``, ``$in``, ``$nin``, ``$and``, ``$or``, ``$exists``. Example: ``{'category': {'$eq': 'electronics'}, 'price': {'$lt': 100}}``.
   * - ``advancedOptions``
     - object
     - No
     - Search tuning parameters:

       - ``distance_metric``: Override the default metric. Supported values are
         ``COSINE``, ``MANHATTAN``, ``HAMMING``, ``JACCARD``, ``DOT``,
         ``EUCLIDEAN``, ``L2_SQUARED``, and ``EUCLIDEAN_SQUARED``. Refer to
         the Distance Metric Guidance table above for metric summaries and
         usage guidance.
       - ``accuracy``: Target accuracy (0–100). Higher values provide better recall but slower search; ``100`` approximates an exact search.
       - ``idx_parameters``: Index-specific overrides. Supported keys:

         - ``efsearch``: HNSW beam width controlling recall. Use this instead of ``accuracy`` to specify the maximum number of candidates considered while probing the index. Higher values provide better accuracy.
         - ``neighbor partition probes``: IVF partition probes controlling how many inverted lists are scanned.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response containing matching results — an array of results with IDs, distances, and metadata. Distance scores (lower is more similar for most metrics). Vector values are included if ``includeVectors`` is ``true``.

.. code-block:: json
   :caption: Example 200 response

   [
     {
       "id": "prod_123",
       "metadata": {"name": "Wireless Headphones"},
       "distance": 0.12
     }
   ]

.. code-block:: bash
   :caption: Example curl request – Search by query vector

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/query" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "queryBy": {"vector": [0.1, 0.2, 0.3]},
       "topK": 10
     }'

.. code-block:: bash
   :caption: Example curl request – Search by text with filtering

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/query" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
       "queryBy": {"text": "wireless headphones"},
       "topK": 5,
       "filters": {
         "$and": [
           {"category": {"$eq": "electronics"}},
           {"price": {"$lt": 200}}
         ]
       }
     }'

.. code-block:: bash
   :caption: Example curl request – Find similar items to an existing product

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/query" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
       "queryBy": {"id": "prod_12345"},
       "topK": 10,
       "filters": {"category": {"$eq": "electronics"}}
     }'

.. code-block:: bash
   :caption: Example curl request – Search with custom distance metric

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-tables/products/query" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
       "queryBy": {"text": "laptop"},
       "topK": 10,
       "advancedOptions": {
         "distance_metric": "EUCLIDEAN",
         "accuracy": 95,
         "idx_parameters": {
           "efsearch": 128,
           "neighbor partition probes": 4
         }
       },
       "includeVectors": true
     }'

**Response 400** – the request body included invalid parameters.

**Response 404** – the specified vector table does not exist.

----

**POST /vecdb/rerank**

Re-rank search results based on relevance to a query.

Uses a reranking model to score and reorder documents relative to a query.
This improves search quality by performing a more detailed comparison between
the query and each candidate document.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``query``
     - string
     - Yes
     - The search query text.
   * - ``documents``
     - array of string
     - Yes
     - List of documents to rerank. Typically the results from ``POST /query``. Minimum 1 item.
   * - ``modelName``
     - string
     - Yes
     - Name of the loaded reranking model.
   * - ``modelParams``
     - object
     - No
     - Model configuration. Example: ``{"top_n": 5}`` to return only top 5 reranked results.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response containing reranked documents with relevance scores.

.. code-block:: json
   :caption: Example 200 response

   [
     {
       "text": "Machine learning for health",
       "index": 0,
       "score": 0.82
     }
   ]

.. code-block:: bash
   :caption: Example curl request

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/rerank" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "modelName": "cohere-rerank-3.5",
       "query": "machine learning applications in healthcare",
       "documents": [
         "Machine learning is transforming healthcare",
         "Vector databases enable semantic search",
         "Deep learning models for medical imaging"
       ],
       "modelParams": {
         "top_n": 5
       }
     }'

**Response 400** – the request body included invalid parameters.

Indexes
--------

**POST /vecdb/vector-indexes/**

Create a vector index on a table to enable fast similarity search.

Creates an index for efficient approximate nearest neighbor (ANN) search.
The index creation runs asynchronously as a background job. Use ``GET /vecdb/vector-indexes/{vector_table_name}``
or ``GET /vecdb/vector-indexes/jobs/{index_job_name}/`` to monitor progress.

Supports IVF (Inverted File) and HNSW (Hierarchical Navigable Small World) indexes.
When ``indexParams`` are omitted, ORDS creates an index using server-side
defaults. ORDS 26.2 represents vector and metadata settings as nested
``vector_index_params`` and ``metadata_index_params`` objects.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``tableName``
     - string
     - Yes
     - Name of the vector table to index.
   * - ``indexParams``
     - object
     - No
     - Nested 26.2 index configuration. If not specified, ORDS uses server-side defaults:

       .. code-block:: json

          {
            "vector_index_params": {
              "auto_index": true,
              "organization": "<PARTITIONS | INMEMORY GRAPH>",
              "distance_metric": "<COSINE | MANHATTAN | HAMMING | JACCARD | DOT | EUCLIDEAN | L2_SQUARED | EUCLIDEAN_SQUARED>",
              "quantization_type": "<NONE | SCALAR>",
              "compression_ratio": 4,
              "advanced_params": {
                "partitions": 16,
                "neighbors": 32,
                "efConstruction": 128
              }
            },
            "metadata_index_params": {
              "auto_index": true,
              "include_paths": ["tenant"],
              "exclude_paths": ["body"]
            },
            "parallel_creation": 4
          }

       ``partitions`` applies to ``PARTITIONS`` (IVF) organization;
       ``neighbors`` and ``efConstruction`` apply to ``INMEMORY GRAPH`` (HNSW) organization.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response containing the index job ID and status.

.. code-block:: json
   :caption: Example 200 response

   {
     "job_name": "IDX_PRODUCTS_20260210",
     "job_creator": "VECDB_USER",
     "job_type": "SCHEDULED",
     "operation": "CREATE_INDEX",
     "state": "SCHEDULED",
     "start_date": null,
     "links": [
       {"rel": "job", "href": "/vecdb/vector-indexes/jobs/IDX_PRODUCTS_20260210/"}
     ]
   }

.. code-block:: bash
   :caption: Example curl request – Create index with default IVF settings

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "tableName": "products"
     }'

.. code-block:: bash
   :caption: Example curl request – Create HNSW index with custom parameters

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
      "tableName": "products",
      "indexParams": {
        "vector_index_params": {
          "auto_index": true,
          "organization": "INMEMORY GRAPH",
          "distance_metric": "COSINE",
          "quantization_type": "SCALAR",
          "compression_ratio": 4,
          "distribute_params": {
            "distribute_method": "AUTO"
          },
          "advanced_params": {
            "neighbors": 32,
            "efConstruction": 128,
            "rescore_factor": 10,
            "algorithm": "uniform_quantization"
          }
        },
        "metadata_index_params": {
          "auto_index": true,
          "include_paths": ["tenant", "category"],
          "exclude_paths": ["body"]
        },
        "parallel_creation": 4
      }
    }'

.. code-block:: bash
   :caption: Example curl request – Create IVF index with explicit defaults

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
      "tableName": "products",
      "indexParams": {
        "vector_index_params": {
          "organization": "PARTITIONS",
          "distance_metric": "COSINE",
          "advanced_params": {
            "partitions": 16
          }
        }
      }
    }'

**Response 400** – the request body included invalid parameters.

**Response 404** – the vector table was not found.

----

**GET /vecdb/vector-indexes/jobs/**

List all index build and rebuild jobs.

Returns metadata for all CREATE and REBUILD index operations, including
their current states and progress.

**Returns**

JSON response containing an array of index jobs with job names, owners, states (SCHEDULED, RUNNING, SUCCEEDED, FAILED), start/end timestamps, and log file paths.

.. code-block:: json
   :caption: Example 200 response

   {
     "items": [
       {
         "job_name": "IDX_PRODUCTS_20260210",
         "job_creator": "VECDB_USER",
         "job_type": "SCHEDULED",
         "operation": "CREATE_INDEX",
         "state": "SUCCEEDED",
         "start_date": "2026-02-10T20:00:00Z",
         "links": [
           {"rel": "self", "href": "/vecdb/vector-indexes/jobs/IDX_PRODUCTS_20260210/"}
         ]
       }
     ],
     "hasMore": false,
     "limit": 25,
     "offset": 0,
     "count": 1,
     "links": []
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/jobs/" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

----

**GET /vecdb/vector-indexes/jobs/{index_job_name}/**

Retrieve metadata and status for a specific index build job.

Returns details about an asynchronous index creation or rebuild job, including
its current state, progress, owner, and log file location.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``index_job_name``
     - string
     - Yes
     - Name of the index job to describe.

**Returns**

JSON response describing the index job including job name and owner, job state (SCHEDULED, RUNNING, SUCCEEDED, FAILED), start and end timestamps, log file path, and error messages (if failed).

.. code-block:: json
   :caption: Example 200 response

   {
     "job_name": "IDX_PRODUCTS_20260210",
     "job_creator": "VECDB_USER",
     "job_type": "SCHEDULED",
     "operation": "CREATE_INDEX",
     "state": "SUCCEEDED",
     "start_date": "2026-02-10T20:00:00Z",
     "links": [
       {"rel": "self", "href": "/vecdb/vector-indexes/jobs/IDX_PRODUCTS_20260210/"},
       {"rel": "jobfile", "href": "/vecdb/vector-indexes/jobs/IDX_PRODUCTS_20260210/jobfile"}
     ]
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/jobs/INX_JOB_12345/" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

----

**GET /vecdb/vector-indexes/jobs/{index_job_name}/jobfile**

Retrieve the log output for an index build job.

Returns the detailed log file contents for diagnosing index creation issues
or monitoring progress.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``index_job_name``
     - string
     - Yes
     - Name of the index job.

**Returns**

JSON response containing log file metadata and contents.

.. code-block:: json
   :caption: Example 200 response

   {
     "log_date": "2026-02-10T20:15:00Z",
     "job_name": "IDX_PRODUCTS_20260210",
     "status": "INFO",
     "error#": 0,
     "additional_info": "Index created successfully",
     "actual_start_date": "2026-02-10T20:00:05Z",
     "run_duration": "+000 00:14:55.000",
     "links": []
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/jobs/INX_JOB_12345/jobfile" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

----

**POST /vecdb/vector-indexes/{vector_table_name}**

Rebuild an existing vector index with updated parameters.

Recreates the index, optionally with new configuration parameters. Useful for
optimizing search performance or adjusting to changed data distributions.
The rebuild runs asynchronously as a background job.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table whose index will be rebuilt.

**Request body** (optional)

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``indexParams``
     - object
     - No
     - New 26.2 index configuration. Use ``index_type`` to scope the rebuild to
       ``vector``, ``metadata``, or ``all``:

       .. code-block:: json

          {
            "index_type": "<vector | metadata | all>",
            "vector_index_params": {
              "organization": "<PARTITIONS | INMEMORY GRAPH>",
              "distance_metric": "<COSINE | MANHATTAN | HAMMING | JACCARD | DOT | EUCLIDEAN | L2_SQUARED | EUCLIDEAN_SQUARED>"
            },
            "metadata_index_params": {
              "include_paths": ["tenant"]
            },
            "parallel_creation": 4
          }

   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response containing the rebuild job ID and status.

.. code-block:: json
   :caption: Example 200 response

   {
     "job_name": "REBUILD_IDX_PRODUCTS_20260210",
     "job_creator": "VECDB_USER",
     "job_type": "SCHEDULED",
     "operation": "REBUILD_INDEX",
     "state": "SCHEDULED",
     "start_date": null,
     "links": [
       {"rel": "job", "href": "/vecdb/vector-indexes/jobs/REBUILD_IDX_PRODUCTS_20260210/"}
     ]
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/products" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "indexParams": {
         "index_type": "all",
         "parallel_creation": 4
       }
     }'

**Response 400** – the request body included invalid parameters.

**Response 404** – the vector table was not found.

----

**GET /vecdb/vector-indexes/{vector_table_name}**

Get the current status and configuration of a vector table's index.

Returns detailed information about the index including its type, parameters,
build status, and statistics.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table whose index to describe.

**Returns**

JSON response containing the index type (IVF, HNSW), build status (BUILDING, READY, FAILED), index parameters, and statistics (indexed vectors, memory usage).

.. code-block:: json
   :caption: Example 200 response

   {
     "Index Status": "VALID"
   }

.. code-block:: bash
   :caption: Example curl request

   curl -X GET \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/products" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>"

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>"

**Response 400** – the request body included invalid parameters.

**Response 404** – the vector table was not found.

----

**POST /vecdb/vector-indexes/{vector_table_name}/delete**

Drop the vector index from a table.

Removes the index while preserving the table and its data. Queries will
fall back to exact search until a new index is created.

**Path parameter**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``vector_table_name``
     - string
     - Yes
     - Name of the vector table whose index to drop.

**Request body**

.. list-table::
   :header-rows: 1
   :widths: 25 15 15 45

   * - Parameter
     - Type
     - Required
     - Description
   * - ``indexParams``
     - object
     - No
     - Use ``index_type`` to drop ``vector``, ``metadata``, or ``all`` indexes.
       Metadata drops can include ``metadata_index_params.include_paths`` to
       select paths.
   * - ``debugFlags``
     - object
     - No
     - See debugFlags note above.

**Returns**

JSON response confirming index deletion.

.. code-block:: json
   :caption: Example 200 response

   {
     "name": "IDX_PRODUCTS_IVF",
     "message": "Index drop request submitted."
   }

.. code-block:: bash
   :caption: Example curl request – Drop all indexes

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/products/delete" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     # Choose ONE authentication method:

     # Option 1: Basic authentication
     -u "<user>:<password>" \

     # Option 2: OAuth Bearer token
     # -H "Authorization: Bearer <access_token>" \

     -d '{
       "indexParams": {
         "index_type": "all"
       }
     }'

.. code-block:: bash
   :caption: Example curl request – Drop selected metadata indexes

   curl -X POST \
     "https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/vector-indexes/products/delete" \
     -H "Content-Type: application/json" \
     -H "Accept: application/json" \
     -u "<user>:<password>" \
     -d '{
       "indexParams": {
         "index_type": "metadata",
         "metadata_index_params": {
           "include_paths": ["tenant"]
         }
       }
     }'

**Response 400** – the request body included invalid parameters.

**Response 404** – the vector table was not found.

Error Catalogue
----------------

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Status Code
     - Description
   * - ``400 Bad Request``
     - Validation problems, incompatible payloads, or attempts to drop models still referenced by tables.
   * - ``404 Not Found``
     - Target model, table, index, or job does not exist.
   * - ``409 Conflict``
     - Resource already exists (for example, attempting to create a duplicate table).
