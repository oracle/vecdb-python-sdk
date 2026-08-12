# Oracle VecDB Python SDK &nbsp;⚡️

<p align="center">
  <img src="https://img.shields.io/pypi/v/oracle-vecdb?color=%23f80000&label=PyPI&logo=python" alt="PyPI">
  <img src="https://img.shields.io/pypi/pyversions/oracle-vecdb.svg?logo=python&label=Python" alt="Python Versions">
  <img src="https://img.shields.io/badge/status-active-success?style=flat" alt="Status">
</p>

## 🚀 About

Oracle VecDB Python SDK provides a Python-native interface for building vector search and AI applications with Oracle AI Database 23.26.3 and later. It supports both Autonomous AI Vector Database deployments and customer-managed Oracle AI Database instances exposed through ORDS 26.2.2 or later.

The SDK provides straightforward APIs for creating and managing vector tables and indexes, executing vector similarity searches, and invoking inference operations—allowing developers to integrate Oracle AI Database vector capabilities into Python applications with minimal setup and boilerplate.

## ✨ Highlights

- 🔐 Typed client with simple auth + configuration
- 📦 Manage vector tables, vector indexes, and metadata programmatically
- 🧠 Run embeddings & inference flows via Oracle AI Database models
- 🔄 Integrate vector search, filtering, and RAG-style pipelines quickly

## 📦 Installation

```bash
python -m pip install --upgrade oracle-vecdb
```

## 🚀 Quickstart

See the [Oracle VecDB documentation](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/quickstart.html)
for installation, pre-requisites, and the complete API reference.

This quickstart connects to Oracle VecDB, creates a table with integrated
embeddings, loads sample records, and runs a filtered similarity search.
Most SDK methods return typed response models. Import stable SDK response types
from `oracle_vecdb.data_types`, and use `.model_dump()` or `.to_dict()` when
you need a plain dictionary representation.

### 1. Configure the client

VecDB `rest_url` has this form but it might change based on the setup:

```text
https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/
```

**Note:** Ensure TLS is enabled and that the endpoint is reachable from your environment.

```python
from oracle_vecdb import OracleVecDB, Configuration

config = Configuration(
    rest_url="https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/",
    # choose one auth method
    access_token="<bearer-token>",
    # or username="<user>", password="<pass>",
)

vecdb = OracleVecDB(config)
```

For all constructor parameters and object attributes, see the
[Oracle VecDB documentation](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/configuration.html).

### 2. Create an integrated embedding vector table

Create a table that generates embeddings from text stored in metadata. The
configured model must already be available in Oracle AI Database.

```python
vecdb.create_vector_table(
    name="demo",
    table_params={"auto_generate_id": True},
    embed_params={
        "model": "all_MiniLM_L12_v2",  # must be preloaded via Vector Database Console or load_model()
        "embed_metadata_jsonpath": "content",  # JSON field in metadata to extract text from for embedding
    },
)
```

### 3. Load integrated embedding records

When an integrated embedding vector table is configured, provide text in the
metadata field selected by `embed_metadata_jsonpath`. The database generates
the vector during the upsert.

```python
vecdb.upsert_vectors(
    table_name="demo",
    vectors=[
        {
            "metadata": {
                "title": "Comedy movie review",
                "content": "A lighthearted comedy with fast-paced jokes.",  # text to embed
                "genre": "comedy",
            }
        },
        {
            "metadata": {
                "title": "Drama movie review",
                "content": "An emotional family drama with strong performances.",
                "genre": "drama",
            }
        },
    ],
)
```

### 4. Run a text query with filtering

A text query uses the table's configured embedding model to generate the query
vector.

```python
results = vecdb.query(
    table_name="demo",
    query_by={"text": "family drama"},  # uses integrated embeddings for the query text
    filters={"genre": {"$eq": "drama"}},
    top_k=1,
)

for index in range(len(results)):
    item = results[index]
    row = item if isinstance(item, dict) else item.model_dump()
    print(row["id"], row["distance"], row["metadata"])
```

### 📥 Ingestion Options

#### Bring your own vectors

For precomputed embeddings, omit `embed_params` when creating the vector table
and provide `dense_vector` values in each record.

```python
vecdb.create_vector_table(name="demo_byov")
vecdb.upsert_vectors(
    table_name="demo_byov",
    vectors=[
        {"id": "1", "dense_vector": [0.1, 0.1], "metadata": {"genre": "comedy"}},
        {"id": "2", "dense_vector": [0.2, 0.2], "metadata": {"genre": "drama"}},
    ],
)
results = vecdb.query(
    table_name="demo_byov",
    query_by={"vector": [0.15, 0.1]},
    filters={"genre": {"$eq": "drama"}},
    top_k=1,
)

for index in range(len(results)):
    item = results[index]
    row = item if isinstance(item, dict) else item.model_dump()
    print(row["metadata"]["genre"])
```

### 🔧 Indexing and tuning

#### Create indexes after loading data

Create the table first and build its index explicitly when the data-loading
workflow is complete.

```python
vecdb.create_vector_table(
    name="demo_manual",
    index_params={"vector_index_params": {"auto_index": False}},
)

vecdb.create_index(table_name="demo_manual")
```

#### Create an HNSW index

Use `INMEMORY GRAPH` organization for an HNSW (Hierarchical Navigable Small
World) vector index.

```python
vecdb.create_vector_table(
    name="demo_hnsw",
    index_params={
        "vector_index_params": {
            "auto_index": True,
            "organization": "INMEMORY GRAPH",  # HNSW-style index organization
            "distance_metric": "COSINE",
            "advanced_params": {
                "neighbors": 32,  # higher = better recall, more memory
                "efConstruction": 200,  # higher = better recall, slower index build
            },
        },
    },
)
```

#### Query-time HNSW tuning

Use `advanced_options` to adjust HNSW runtime search behavior. `efsearch` is
HNSW-only; use it to control the candidate pool size and balance recall against
query latency without rebuilding the index.

```python
results = vecdb.query(
    table_name="demo",
    query_by={"text": "family drama"},
    filters={"genre": {"$eq": "drama"}},
    top_k=1,
    advanced_options={
        "idx_parameters": {
            "efsearch": 64,  # number of candidates explored (higher = better recall, higher latency)
        }
    },
)
```

## Examples

- Samples can be found in the [/examples](./examples/) directory.
- [Sample notebooks](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb) – Guided notebooks for setup, table/index workflows, vector search, and inference via the SDK.
- [Sample applications](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb) – Oracle AI Developer Hub apps showcasing ingestion, embeddings, search, filtering, and FastAPI + React/Vite integration using this SDK.

## Dependencies and Interoperability

- Python 3.10 or later.
- Oracle AI Database 23.26.3 or later with ORDS 26.2.2+ enabled.
- An Oracle ORDS VecDB endpoint configured with either bearer-token or HTTP Basic authentication.

The SDK can be used in applications, notebooks, retrieval-augmented generation
(RAG) pipelines, and other Python services that need Oracle vector search.
For setup instructions and guidance on getting started with the VecDB APIs, see the [Oracle VecDB documentation](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/overview.html)

## 📚 Documentation and Resources

- [Oracle VecDB documentation](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/overview.html) - for detailed API documentation, including features, usage, and reference information.
- [Customer-managed Oracle AI Database (26ai+) requirements](https://docs.oracle.com/en/database/oracle/oracle-rest-data-services/26.2/) – DB 23.26.3+ with ORDS 26.2.2+, plus TLS/ORDS notes for handling self-signed certificates.

## Help

Questions can be asked in [GitHub Discussions](https://github.com/oracle/vecdb-python-sdk/discussions).

Problem reports can be raised in [GitHub Issues](https://github.com/oracle/vecdb-python-sdk/issues).

## 🤝 Contributing

This project welcomes contributions from the community. Before submitting a pull request, please [review our contribution guide](./CONTRIBUTING.md)

## 🔐 Security

Please consult the [security guide](./SECURITY.md) for our responsible security vulnerability disclosure process

## 📄 License

See [LICENSE.txt](./LICENSE.txt), [THIRD_PARTY_LICENSE.txt](./THIRD_PARTY_LICENSE.txt), and [NOTICE.txt](./NOTICE.txt).
