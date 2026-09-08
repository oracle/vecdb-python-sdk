Changelog
=========

All notable changes to this project will be documented in this file.

The format is based on the `Keep a Changelog <https://keepachangelog.com/en/1.1.0/>`__,
and this project adheres to `Semantic Versioning <https://semver.org/spec/v2.0.0.html>`__.

1.0.3 - 2026-09-07
------------------

Added
~~~~~

- Added verified public-operation defaults for omitted arguments, including
  ``create_vector_table.table_params.auto_generate_id``,
  ``list_vectors.limit``, and ``query.include_vectors``.
- Added transport-neutral validation for parameter values
  and cross-field combinations before requests are sent to ORDS.
- Added explicit authentication-mode detection for unauthenticated, basic,
  and bearer configurations, including validation of incomplete or conflicting
  credentials.

Changed
~~~~~~~

- Resource-name validation now rejects blank values and transport-unsafe NUL
  or double-quote characters while leaving database-specific identifier rules
  to Oracle Database.
- Upsert vector field names are normalized case-insensitively; unknown fields
  and duplicate fields with different casing now produce clear validation
  errors.
- Improved validation and error messages for vector index organizations,
  distribution settings, quantization, metadata paths, query modes, and other
  parameter dependencies.
- Improved ORDS exception normalization and diagnostics by redacting sensitive
  request and response data, preserving useful error categories, and avoiding
  duplicate raw transport exception context.

Fixed
~~~~~

- Fixed graph-index requests that omitted required distribution parameters from
  reaching the service with an invalid request shape.

1.0.2 - 2026-08-19
------------------

Changed
~~~~~~~

- Documentation-only release; no SDK API or runtime changes.
- Refreshed the README with direct links to runnable geospatial and semantic
  search, semantic code search, RAG document chat, and VecDB notebook examples.
- Improved the getting-started journey from SDK installation to hands-on
  applications and workflows.

1.0.1 - 2026-08-10
------------------

Changed
~~~~~~~

- Updated the README quickstart and sample snippets to match the published
  Python SDK quickstart, including requirements, BYOV ingestion, HNSW indexes,
  and query-time tuning.

1.0.0 - 2026-08-07
------------------

Added
~~~~~

- Initial public release of oracle_vecdb
- Support for vector table management, indexing, search, and inference operations in Oracle AI Database (26ai+). Refer this for detailed documentation -
 https://docs.oracle.com/en/cloud/paas/autonomous-vector-database/vcapi/overview.html


1.0.0b2 - 2026-04-30
------------------

Added
~~~~~

- Added support for automatic batching during large dataset upsert.
- Added support for case-insensitive input keys, allowing user data to use any capitalization for ID, DENSE_VECTOR, and METADATA.
- Updated the host URL validation pattern to work in ExaCC environments for pool mappings.
- Added "rest_url" as the preferred parameter and deprecated "host", with support for disabling "host" later via a feature toggle.

Changed
~~~~~~~

- Renamed `agent.md` to `AGENTS.md` and streamlined it around verified public SDK workflows.

Fixed
~~~~~

- Fixed the ``rerank`` API reference to mention results from ``query`` instead of ``query_vectors()``.

1.0.0b1 - 2026-03-24
------------------

Added
~~~~~

- Limited Availability release.
- Support for vector table management, indexing, search, and inference operations in Oracle AI Database (26ai+).
