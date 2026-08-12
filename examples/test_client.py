##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

import os

from oracle_vecdb import OracleVecDB, Configuration


def main():
    # Use a valid HTTPS ORDS VecDB endpoint. Example pattern:
    # https://<host>:<port>/ords/<schema>/_/db-api/stable/vecdb/
    config = Configuration(
        rest_url="https://example.com/ords/foo/_/db-api/stable/vecdb/",
        username="username",
        password=os.getenv("DB_PASSWORD"),
    )

    vecdb = OracleVecDB(config)
    table_name = "TEST_TABLE"
    table_created = False

    try:
        print("Vector database summary:")
        print(vecdb.describe_vector_database())
        vecdb.create_vector_table(
            name=table_name,
            comment="Oracle VecDB Python SDK example",
            annotations={"application": "sdk-example"},
        )
        table_created = True

        print(f"Created table:{table_name}")
        print(vecdb.describe_vector_table(name=table_name))

        upsert_result = vecdb.upsert_vectors(
            table_name=table_name,
            vectors=[
                {
                    "id": "A",
                    "dense_vector": [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
                    "metadata": {"genre": "comedy", "year": 2020},
                },
                {
                    "id": "B",
                    "dense_vector": [0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2],
                    "metadata": {"genre": "documentary", "year": 2019},
                },
                {
                    "id": "C",
                    "dense_vector": [0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3],
                    "metadata": {"genre": "comedy", "year": 2019},
                },
                {
                    "id": "D",
                    "dense_vector": [0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4],
                    "metadata": {"genre": "drama"},
                },
            ],
        )
        print("Upsert result:")
        print(upsert_result)

        print("Vectors in the table:")
        print(vecdb.list_vectors(table_name=table_name, limit=10))

        vecdb.update_vector_table_annotation(
            name=table_name,
            comment="Updated Oracle VecDB Python SDK example",
            annotations={
                "application": "sdk-example",
                "stage": "demonstration",
            },
        )
        print("Updated table metadata:")
        print(vecdb.describe_vector_table(name=table_name))

        result = vecdb.query(
            table_name=table_name,
            query_by={
                "vector": [
                    -0.00337490835,
                    0.0575999133,
                    -0.0147442026,
                    -0.0645009279,
                    0.0645009279,
                    0.0645009279,
                    0.0645009279,
                    0.0645009279,
                ]
            },
            filters={"genre": {"$eq": "comedy"}},
            top_k=2,
        )

        print("Filtered query results:")
        print(result)

        delete_result = vecdb.delete_vectors(table_name=table_name, ids=["D"])
        print("Delete result:")
        print(delete_result)

        print("Vectors after deletion:")
        print(vecdb.list_vectors(table_name=table_name, limit=10))
    except Exception as exc:
        print("An error occurred:", exc)
    finally:
        if table_created:
            try:
                vecdb.drop_vector_table(name=table_name)
                print(f"Dropped table: {table_name}")
            except Exception as exc:
                print(f"Could not drop table {table_name}: {exc}")


if __name__ == "__main__":
    main()
