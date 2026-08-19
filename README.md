# Oracle VecDB Python SDK

**Build vector search, RAG, and AI applications on Oracle AI Database - from Python.**
Keep vectors alongside your operational data, combine semantic similarity with relational and spatial filtering, and build retrieval applications without introducing a separate vector database.

[![PyPI](https://img.shields.io/pypi/v/oracle-vecdb)](https://pypi.org/project/oracle-vecdb/)
[![Python](https://img.shields.io/pypi/pyversions/oracle-vecdb)](https://pypi.org/project/oracle-vecdb/)
[![License](https://img.shields.io/github/license/oracle/vecdb-python-sdk)](LICENSE.txt)

**⭐ [Star `oracle/vecdb-python-sdk`](https://github.com/oracle/vecdb-python-sdk) to follow the project and help more developers discover it.**

**[Quickstart](#-quickstart) · [Sample Apps](#-see-what-you-can-build) · [Notebooks](#-hands-on-notebooks) · [Docs](#-documentation) · [Releases](https://github.com/oracle/vecdb-python-sdk/releases)**

---

## 🚀 Quickstart

### Requirements

- **Python:** 3.10+
- **Oracle AI Database:** 23.26.3+
- **ORDS:** 26.2.2+

### Installation

Install with `pip` or `uv`:

```bash
# pip
pip install oracle-vecdb

# uv
uv add oracle-vecdb
```

### Connect

```python
from oracle_vecdb import OracleVecDB, Configuration

config = Configuration(
    rest_url="https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/",
    access_token="<access-token>",
)

vecdb = OracleVecDB(config)
```

### Run a semantic search with metadata filtering

> This example assumes a vector table named demo already exists and contains data. See the [full quickstart](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/quickstart.html) for create_vector_table() and upsert().

```python
results = vecdb.query(
    table_name="demo",
    query_by={"text": "family film"},  # uses integrated embeddings for the query text
    filters={"genre": {"$eq": "drama"}},
    top_k=3,
)

for index in range(len(results)):
    item = results[index]
    row = item if isinstance(item, dict) else item.model_dump()
    print(row["id"], row["distance"], row["metadata"])
```

### ⚡ **Integrated embeddings. Automatic vector indexing. Semantic search + structured filtering. One Python SDK.**

[Read the full quickstart →](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/quickstart.html)

---

# 🧪 See what you can build

Complete applications built with `oracle-vecdb` are available in the [Oracle AI Developer Hub](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb).

## 🌲 Semantic + Geospatial Search

**Combine vector similarity with spatial filtering in one application.**

Semantic search plus geographic and structured constraints, powered by Oracle AI Database.

![Ask the Parks — semantic, metadata, and spatial search with Oracle VecDB](https://raw.githubusercontent.com/oracle-devrel/oracle-ai-developer-hub/main/apps/vecdb/vecdb_ask_parks/static/assets/ask_the_parks_demo.gif)

**Oracle Spatial · Vector Search · Oracle VecDB**

[View the sample app →](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb/vecdb_ask_parks)

---

## 💻 Semantic Code Search

**Search source code by meaning, not just keywords.**

Use natural-language queries to find relevant functions, files, and surrounding code.

![Semantic Code Search - natural-language query, ranked code results, repository navigation, and highlighted source code](https://raw.githubusercontent.com/oracle-devrel/oracle-ai-developer-hub/main/apps/vecdb/semantic_code_search/images/semantic_code_search.gif)

**FastAPI · React · Jina Embeddings · Oracle VecDB**

[View the sample app →](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb/semantic_code_search)

---

## 🤖 RAG Document Chatbot

**Upload documents and ask grounded questions over their content.**

Chunk documents, generate embeddings, retrieve relevant context, and pass it to an LLM for grounded answers.

![Document Chatbot UI showing uploaded documents, a user question, retrieved context, and a grounded answer](https://raw.githubusercontent.com/oracle-devrel/oracle-ai-developer-hub/main/apps/vecdb/doc_chatbot/images/doc_chat_bot.gif)

**Streamlit · OpenAI / Ollama · Oracle VecDB**

[View the sample app →](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb/doc_chatbot)

---

**More examples:** Multi-Modal Product Search, Product Recommendations · hands-on notebooks

[Explore all sample applications →](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb)

---

# 💡 Why Oracle VecDB?

Modern AI applications often need vector search plus the structured data around each result.

Oracle VecDB lets Python applications use vector search alongside relational, spatial, and all other capabilities of the Oracle AI Database.

Use Oracle VecDB to:

- 🔎 Run semantic and similarity search
- 🌍 Combine vector search with spatial and structured queries
- 🤖 Build RAG applications and AI agents
- 🧠 Use integrated embeddings or bring your own vectors
- ⚡ Create vector indexes automatically by default
- 🎛️ Tune HNSW and embedding settings when needed

If you're building enterprise AI apps, the data you need is probably already in an Oracle AI Database, VecDB can reduce the need to move or synchronize that data into a separate vector database.

---

# 📓 Hands-on notebooks

Learn Oracle VecDB hands-on. The Oracle AI Developer Hub includes runnable notebooks that take you from first query to production-oriented tuning.

## 🧠 Embeddings & RAG

- **Integrated embeddings** — generate embeddings as part of the VecDB workflow
- **Bring Your Own Vectors** — use embeddings from your preferred model or provider
- **Gemini RAG** — build retrieval-augmented generation with Gemini
- **OCI Generative AI embeddings** — use OCI-hosted embedding models with VecDB
- **Oracle Private AI Services Container** - use in an air-gapped environment with OpenAI-style inference layer

[Explore embeddings & RAG notebooks →](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb)

## 🔎 Search & filtering

- **Semantic search** — retrieve results by meaning rather than keywords
- **Metadata filtering** — combine vector similarity with structured constraints
- **Search diagnostics** — inspect and understand vector-search behavior
- **Financial-data search** — apply vector retrieval to structured financial datasets

[Explore search notebooks →](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb)

## ⚡ Performance & scale

- **HNSW tuning** — understand and tune vector-index search parameters
- **Bulk vector loading** — compare approaches for loading larger datasets
- **Index management** — create, inspect, and manage vector indexes
- **Maintenance workflows** — operate vector tables and indexes over time

[Explore performance notebooks →](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb)

> **New to Oracle VecDB?** Start with integrated embeddings and semantic search, then move on to filtering and HNSW tuning.

[Browse all VecDB notebooks →](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb)

---

## Examples

- Samples can be found in the [/examples](./examples/) directory.
- [Sample notebooks](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb) – Guided notebooks for setup, table/index workflows, vector search, and inference via the SDK.
- [Sample applications](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb) – Oracle AI Developer Hub apps showcasing ingestion, embeddings, search, filtering, and FastAPI + React/Vite integration using this SDK.

---

# 📚 Documentation

- **[Getting Started](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/quickstart.html)**
- **[Python API Reference](https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/python-api-reference.html)**
- **[Sample Applications](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb)**
- **[Hands-on Notebooks](https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb)**
- **[GitHub Releases](https://github.com/oracle/vecdb-python-sdk/releases)**
- **[Locally-managed REST](https://docs.oracle.com/en/database/oracle/oracle-rest-data-services/26.2/)**

---

## Help

Questions can be asked in [GitHub Discussions](https://github.com/oracle/vecdb-python-sdk/discussions).

Problem reports can be raised in [GitHub Issues](https://github.com/oracle/vecdb-python-sdk/issues).

---

## 🤝 Contributing

This project welcomes contributions from the community. Before submitting a pull request, please [review our contribution guide](./CONTRIBUTING.md)

[Open an issue →](https://github.com/oracle/vecdb-python-sdk/issues)

---

## 🔐 Security

Please consult the [security guide](./SECURITY.md) for our responsible security vulnerability disclosure process

---

## 📄 License

See [LICENSE.txt](./LICENSE.txt), [THIRD_PARTY_LICENSE.txt](./THIRD_PARTY_LICENSE.txt), and [NOTICE.txt](./NOTICE.txt).

---

## ⭐ Like Oracle VecDB?

**[Star `oracle/vecdb-python-sdk` →](https://github.com/oracle/vecdb-python-sdk)**

It helps you follow the project and helps other Python and AI developers discover it.
