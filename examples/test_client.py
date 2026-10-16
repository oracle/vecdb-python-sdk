##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

from getpass import getpass

from oracle_vecdb import Configuration, OracleVecDB, get_vecdb_oauth_token


def main():
    # Replace these example values with your ORDS host, port, and schema.
    host = "example.com"
    port = 8443
    schema = "foo"
    ords_url = f"https://{host}:{port}/ords/{schema}"
    rest_url = f"{ords_url}/_/db-api/stable/vecdb/"

    # Choose OAuth client credentials or basic authentication.
    ords_oauth = True

    if ords_oauth:
        # Create or obtain an OAuth client in ORDS. The client ID is entered
        # visibly; getpass hides the client secret while you type it.
        # TLS certificate verification is on by default. For a private CA,
        # provide its bundle with the optional ssl_ca_cert argument below.
        token_response = get_vecdb_oauth_token(
            client_id=input("ORDS OAuth client ID: "),
            client_secret=getpass("ORDS OAuth client secret: "),
            token_url=f"{ords_url}/oauth/token",
            timeout=(5, 30),  # connect timeout, then read timeout
            # ssl_ca_cert="/path/to/ca-bundle.pem",
        )
        config = Configuration(
            rest_url=rest_url,
            access_token=token_response["access_token"],
        )
    else:
        # Use this branch only when your ORDS deployment requires basic auth.
        config = Configuration(
            rest_url=rest_url,
            username=input("Vector DB Username: "),
            password=getpass("Vector DB Password: "),
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
