# Agent Guide: vecdb-python-sdk

## Purpose

- This repository owns the Oracle VecDB Python SDK, its public Python API,
  examples, package metadata, tests, and changelog.

## Workspace Setup

- Python 3.10+ is the user-facing requirement from `README.md` and
  `pyproject.toml`.
- Keep real hosts, tokens, usernames, passwords, and production table names out
  of committed examples, tests, issues, and reviews.
- Prefer `Configuration.access_token` when bearer tokens are available; use
  username/password only when the target environment requires it.
- Use host placeholders that preserve the documented ORDS VecDB URL shape:
  `https://<host>/ords/<schema>/_/db-api/stable/vecdb/`.

## API Surface (OracleVecDB)

- Table management (`create_vector_table`, `describe_vector_table`,
  `drop_vector_table`, `list_vector_tables`, `update_vector_table_annotation`).
- Index lifecycle (`create_index`, `describe_index`, `describe_index_job`,
  `list_index_jobs`, `get_index_job_log`, `rebuild_index`, `drop_index`).
- Inference (`generate_embedding`, `rerank`).
- Model orchestration (`load_model`, `list_models`, `describe_model`,
  `drop_model`).
- Vector operations (`upsert_vectors`, `list_vectors`, `delete_vectors`,
  `load_vectors`, `describe_vector_load_job`, `get_vector_load_job_log`,
  `list_vector_load_jobs`).
- Search (`query`).
- Summary (`describe_vector_database`).

## Capability Workflows

- Authentication and configuration: construct `Configuration` with a VecDB ORDS
  host and either `access_token` or `username`/`password`, then pass it to
  `OracleVecDB`.
- Model management: use `list_models` and `describe_model` before binding a
  model to table or rerank workflows. Use `load_model` and `drop_model` only
  when the task explicitly includes model lifecycle work.
- Vector tables: use `describe_vector_database` and `list_vector_tables` for
  discovery, `create_vector_table` for storage, `describe_vector_table` for
  schema/index checks, `update_vector_table_annotation` for metadata updates,
  and `drop_vector_table` for cleanup when the workflow owns the table.
- Ingestion: use `upsert_vectors` for inline batches, `delete_vectors` for
  removing known records, `list_vectors` for inspection, and `load_vectors`
  for object-storage bulk ingestion. Monitor bulk jobs with
  `list_vector_load_jobs`, `describe_vector_load_job`, and
  `get_vector_load_job_log`.
- Embeddings and reranking: use hosted VecDB model flows through
  `generate_embedding`, integrated table embedding configuration, `query`, and
  `rerank`.
- Search: use `query` with `query_by`, `top_k`, and verified `filters`. Query
  examples may search by text, vector, or record ID only when that shape is
  verified from README, docs, source, tests, or explicit checked instruction.
- Index lifecycle: use `create_index`, `list_index_jobs`,
  `describe_index_job`, `get_index_job_log`, `rebuild_index`,
  `describe_index`, and `drop_index` for index build, monitoring, tuning, and
  cleanup workflows.

## Query Filters

The public `query` method accepts a filter dictionary and forwards it through
the SDK request model. The REST documentation lists these filter operators:

```python
filters = {
    "$and": [
        {"ACCOUNT_CATEGORY": {"$eq": "Savings"}},
        {"ELIGIBILITY": {"$eq": "Student"}},
        {"MONTHLY_FEE": {"$lte": 5}},
    ]
}
```

Use only filter operators documented in `docs/source/rest_api.rst` or verified
by SDK tests. Do not copy filter syntax from another vector database product.

## Quick Start

- Use the `README.md` Quickstart as the source of truth for runnable
  quick-start examples.
- Use the README Quickstart for integrated embedding flows and the README
  "Bring your own vectors" section for BYOV examples.
- If a quick-start flow changes, update `README.md` first and keep this section
  as a pointer rather than duplicating runnable snippets.
- Verify any adapted quick-start code against the public SDK surface in this
  repo before publishing it.

## Workflow Pointers

- For SDK consumer examples, start with `README.md` and `docs/source/`.
- For public method availability, inspect `OracleVecDB` in
  `src/oracle_vecdb/client.py` and existing tests.
- For request or response details, prefer typed SDK models and tests over
  copied REST payloads.
- For examples that create resources, include cleanup when it is part of the
  demonstrated workflow and does not obscure the main point.

## Troubleshooting

- 401 or 403: check credentials, token freshness, endpoint privileges, and
  schema access without exposing secret values.
- 404: verify the ORDS URL shape, schema segment, table name, model name, index
  name, and job name.
- 409 or job conflicts: inspect existing load or index jobs before retrying.
- Embedding or rerank failures: verify model availability and the public SDK
  request shape before suggesting code changes.
- Large payloads: prefer `load_vectors` over massive inline upserts when the
  input is already staged in object storage.
- Slow or unexpected search results: inspect table, index, filter, and query
  configuration using public SDK methods before recommending service tuning.
