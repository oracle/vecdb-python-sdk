# Oracle VecDB Python SDK &nbsp;⚡️

<p align="center">
  <img src="https://img.shields.io/pypi/v/oracle-vecdb?color=%23f80000&label=PyPI&logo=python" alt="PyPI">
  <img src="https://img.shields.io/pypi/pyversions/oracle-vecdb.svg?logo=python&label=Python" alt="Python Versions">
  <img src="https://img.shields.io/badge/status-active-success?style=flat" alt="Status">
</p>

## 🚀 About

Oracle VecDB Python SDK is the Python client for the Oracle AI Database (26ai+). It covers both Autonomous AI Vector Database deployments and customer-managed Oracle AI Database instances where ORDS is enabled, offering simple APIs for vector table management, indexing, search, and inference operations.


## ✨ Highlights

- 🔐 Typed client with simple auth + configuration
- 📦 Manage vector tables, vector indexes, and metadata programmatically
- 🧠 Run embeddings & inference flows via Oracle AI Database models
- 🔄 Integrate vector search, filtering, and RAG-style pipelines quickly


## 📦 Installation

```bash
pip install oracle-vecdb
```

**Requires:** Python 3.10+


## 🚀 Quickstart

```python
from oracle_vecdb import OracleVecDB, Configuration

config = Configuration(
    rest_url="https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/",
    # choose one auth method
    access_token="<bearer-token>",
    # or username="<user>", password="<pass>",
)

vecdb = OracleVecDB(config)

vecdb.create_vector_table(
    name="demo",
    table_params={"auto_generate_id": True},
    embed_params={
        "model": "all_MiniLM_L12_v2",  # must be preloaded via Vector Database Console or load_model()
        "embed_metadata_jsonpath": "content",  # JSON field in metadata to extract text from for embedding
    },
)

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

```python
vecdb.create_vector_table(name="demo")
# Large inline datasets >32MB are automatically split into bounded requests.
# Batching preserves order but does not deduplicate IDs or guarantee avoidance
# of service rate limits.
response = vecdb.upsert_vectors(
    table_name="demo",
    vectors=[
        {"id": "1", "dense_vector": [0.1, 0.1], "metadata": {"genre": "comedy"}},
        {"id": "2", "dense_vector": [0.2, 0.2], "metadata": {"genre": "drama"}},
    ],
)
print(response.upserted_count)
```

For huge dataset, prefer asynchronous bulk loading from object
storage instead of sending a large inline JSON request. This avoids keeping
the complete dataset in the request body and is better suited to production
ingestion workloads:

```python
load_job = vecdb.load_vectors(
    table_name="demo",
    url="https://objectstorage.<region>.oraclecloud.com/<namespace>/<bucket>/vectors.csv",
    params={"credential": "<oci-credential-name>"},
)

status = vecdb.describe_vector_load_job(load_job.job_name)
print(status.state)
```

The CSV should contain `id`, `dense_vector`, and `metadata` columns. Use an
OCI credential configured for the database when the object is not publicly
readable. Do not place signed URLs or credentials directly in application
logs. `upsert_vectors` remains useful for small inline batches and is
automatically split below the service JSON limit, but it does not replace
bulk loading for large files.

```python
results = vecdb.query(
    table_name="demo",
    query_by={"vector": [0.15, 0.1]},
    filters={"genre": {"$eq": "drama"}},
    top_k=1,
)

for index in range(len(results)):
    item = results[index]
    row = item if isinstance(item, dict) else item.model_dump()
    print(row["metadata"]["genre"])

# Collection endpoints support ORDS pagination. Existing calls without these
# arguments retain the server's default page size.
tables_page = vecdb.list_vector_tables(limit=25, offset=25)
models_page = vecdb.list_models(limit=25, offset=0)
```

### 🔧 Indexing & tuning

Delay index creation until `create_index()`

```python
vecdb.create_vector_table(
    name="demo_byuser",
    index_params={
        "vector_index_params": {
            "auto_index": False,
        }
    },
)

vecdb.create_index(
    table_name="demo_byuser",
)
```

Create HNSW index instead of default IVF

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

Query-time HNSW tuning

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


## 🧪 Sample notebooks & apps

- [Sample notebooks](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb) – Guided notebooks for setup, table/index workflows, vector search, and inference via the SDK.
- [Sample applications](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb) – Oracle AI Developer Hub apps showcasing ingestion, embeddings, search, filtering, and FastAPI + React/Vite integration using this SDK.

## 📚 Documentation & Resources

Most SDK methods return typed response models. Import stable SDK response types
from `oracle_vecdb.data_types`, and use `.model_dump()` or `.to_dict()` when
you need a plain dictionary representation.

- [Autonomous AI Vector Database docs](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database)
- [Autonomous AI Vector Database setup guide](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vecdb/get-started-using-autonomous-ai-vector-database.html)
- [Customer-managed Oracle AI Database (26ai+) requirements](https://docs.oracle.com/en/database/oracle/oracle-rest-data-services/26.2/) – DB 23.26.3+ with ORDS 26.2.2+, plus TLS/ORDS notes for handling self-signed certificates
- [Quickstart guide](./docs/source/quickstart.rst)
- [Installation notes](./docs/source/installation.rst)
- [API reference](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/index.html)
- [Changelog](./CHANGELOG.rst)
- [Examples](./examples/test_client.py)



## 🤝 Contributing

This project welcomes contributions from the community. Before submitting a pull request, please [review our contribution guide](./CONTRIBUTING.md)

## 🔐 Security

Please consult the [security guide](./SECURITY.md) for our responsible security vulnerability disclosure process

## 📄 License

See [LICENSE.txt](./LICENSE.txt), [THIRD_PARTY_LICENSE.txt](./THIRD_PARTY_LICENSE.txt), and [NOTICE.txt](./NOTICE.txt).
