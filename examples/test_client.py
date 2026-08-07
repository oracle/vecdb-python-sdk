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

    try:
        vecdb.create_vector_table(name="TEST_DB")
        vecdb.upsert_vectors(
            table_name="TEST_DB",
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
        result = vecdb.query(
            table_name="TEST_DB",
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
            top_k=2,
        )

        print(result)
    except Exception as exc:
        print("An error occurred:", exc)


if __name__ == "__main__":
    main()
