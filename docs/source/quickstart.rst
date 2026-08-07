Quick Start Guide
=================

This quickstart walks through installing the SDK, configuring a client, creating a table, loading sample vectors, and running a similarity query. Use it to sanity-check your Oracle VecDB (26ai+) environment before building more advanced apps.

Requirements
------------

- Python 3.10+
- Access to an Oracle VecDB endpoint (hosted through Oracle AI Database 26ai+)
- Authentication (either bearer token or username/password)

Installation
------------

.. code-block:: bash

   pip install oracle-vecdb

.. note::
   Hosts typically look like ``https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/``. Ensure TLS (HTTPS) is enabled and the URL is reachable from your environment.

1. Configure the client
-----------------------

.. code-block:: python

   from oracle_vecdb import OracleVecDB, Configuration

   config = Configuration(
       rest_url="https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/",
       # choose one auth method
       access_token="<bearer-token>",
       # or username="<user>", password="<pass>",
   )

   vecdb = OracleVecDB(config)

2. Create a table
-----------------

.. code-block:: python

   vecdb.create_vector_table(name="demo")

3. Load example vectors
-----------------------

.. code-block:: python

   vecdb.upsert_vectors(
       table_name="demo",
       vectors=[
           {"id": "1", "dense_vector": [0.1, 0.1], "metadata": {"genre": "comedy"}},
           {"id": "2", "dense_vector": [0.2, 0.2], "metadata": {"genre": "drama"}},
       ],
   )

Large inline datasets are automatically split into requests below the service
limit::

   large_vector_list = [...]  # the complete inline dataset
   response = vecdb.upsert_vectors(
       table_name="demo",
       vectors=large_vector_list,
   )
   print(response.upserted_count)

The SDK preserves vector order and aggregates the batch counts. Batching does
not deduplicate IDs or guarantee that service rate limits will not be reached;
duplicate IDs and transient HTTP 429 responses remain service conditions. A
single vector larger than 32 MiB is rejected before any request is sent.

4. Run a similarity query
-------------------------

.. code-block:: python

   results = vecdb.query(
       table_name="demo",
       query_by={"vector": [0.15, 0.1]},
       top_k=1,
   )

   for index in range(len(results)):
       item = results[index]
       row = item if isinstance(item, dict) else item.model_dump()
       print(row["id"], row["distance"], row["metadata"])

Sample output::

   2 0.08 {'genre': 'drama'}

.. note::
   Most SDK methods return typed response models rather than raw JSON strings.
   Access response attributes directly when you need a few values. Use
   ``response.model_dump()`` or ``response.to_json()`` only when printing or writing a complete response,
   and ``response.to_dict()`` only when a complete Python dictionary is
   required; both create additional data proportional to the response size.
   Keep ``top_k`` small, leave ``include_vectors=False`` unless needed, and use
   ``output_selector`` to reduce large query responses. Query result rows
   support list-style indexing.

Next steps
----------

- Explore the :doc:`installation` guide for environment-specific setup.
- Follow the :doc:`api` reference to discover table/index operations, search options, and model endpoints.
- Try the `sample applications <https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/apps/vecdb>`_ or `sample notebooks <https://github.com/oracle-devrel/oracle-ai-developer-hub/tree/main/notebooks/vecdb>`_ to see full-stack and notebook workflows.
