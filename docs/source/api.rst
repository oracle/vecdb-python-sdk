Python API Reference
====================

.. currentmodule:: oracle_vecdb.client

OracleVecDB Client
------------------

.. autoclass:: OracleVecDB
   :no-members:

Public Response Models
----------------------

Oracle VecDB facade methods return typed SDK response models. For new code,
prefer importing them from ``oracle_vecdb.data_types``.

- ``QueryResponse`` exposes search hits under ``items``.
- ``RerankResponse`` exposes rerank scores under ``items``.
- Use response attributes directly when application code needs a few fields.
- Use ``to_json()`` only when printing or writing a complete response, and
  ``to_dict()`` only when a complete Python dictionary is needed. Both create
  additional data proportional to the response size.

Large response guidance
~~~~~~~~~~~~~~~~~~~~~~~

Avoid serializing large responses unless they cross an application boundary.
Use pagination for collection methods, a bounded ``top_k`` for ``query``,
``output_selector`` for the metadata fields you need, and leave
``include_vectors=False`` unless vector values are required.

Models
------

- :meth:`OracleVecDB.list_models`
- :meth:`OracleVecDB.load_model`
- :meth:`OracleVecDB.describe_model`
- :meth:`OracleVecDB.drop_model`

.. automethod:: OracleVecDB.list_models
.. automethod:: OracleVecDB.load_model
.. automethod:: OracleVecDB.describe_model
.. automethod:: OracleVecDB.drop_model

Vector Tables
-------------

- :meth:`OracleVecDB.describe_vector_database`
- :meth:`OracleVecDB.list_vector_tables`
- :meth:`OracleVecDB.create_vector_table`
- :meth:`OracleVecDB.describe_vector_table`
- :meth:`OracleVecDB.drop_vector_table`
- :meth:`OracleVecDB.update_vector_table_annotation`

.. automethod:: OracleVecDB.describe_vector_database
.. automethod:: OracleVecDB.list_vector_tables
.. automethod:: OracleVecDB.create_vector_table
.. automethod:: OracleVecDB.describe_vector_table
.. automethod:: OracleVecDB.drop_vector_table
.. automethod:: OracleVecDB.update_vector_table_annotation

Manage Data
-----------

- :meth:`OracleVecDB.generate_embedding`
- :meth:`OracleVecDB.upsert_vectors`
- :meth:`OracleVecDB.list_vectors`
- :meth:`OracleVecDB.delete_vectors`
- :meth:`OracleVecDB.load_vectors`
- :meth:`OracleVecDB.list_vector_load_jobs`
- :meth:`OracleVecDB.describe_vector_load_job`
- :meth:`OracleVecDB.get_vector_load_job_log`

.. automethod:: OracleVecDB.generate_embedding
.. automethod:: OracleVecDB.upsert_vectors
.. automethod:: OracleVecDB.list_vectors
.. automethod:: OracleVecDB.delete_vectors
.. automethod:: OracleVecDB.load_vectors
.. automethod:: OracleVecDB.list_vector_load_jobs
.. automethod:: OracleVecDB.describe_vector_load_job
.. automethod:: OracleVecDB.get_vector_load_job_log

Search Data
-----------

- :meth:`OracleVecDB.query`
- :meth:`OracleVecDB.rerank`

.. automethod:: OracleVecDB.query
.. automethod:: OracleVecDB.rerank

Indexes
-------

- :meth:`OracleVecDB.create_index`
- :meth:`OracleVecDB.list_index_jobs`
- :meth:`OracleVecDB.describe_index_job`
- :meth:`OracleVecDB.get_index_job_log`
- :meth:`OracleVecDB.rebuild_index`
- :meth:`OracleVecDB.describe_index`
- :meth:`OracleVecDB.drop_index`

.. automethod:: OracleVecDB.create_index
.. automethod:: OracleVecDB.list_index_jobs
.. automethod:: OracleVecDB.describe_index_job
.. automethod:: OracleVecDB.get_index_job_log
.. automethod:: OracleVecDB.rebuild_index
.. automethod:: OracleVecDB.describe_index
.. automethod:: OracleVecDB.drop_index
