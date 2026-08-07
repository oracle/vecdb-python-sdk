##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

import pytest

from oracle_vecdb.data_types import (
    DeleteVectorsResponse,
    DropIndexResponse,
    DropModelResponse,
    DropVectorTableResponse,
    IndexDetailsResponse,
    IndexDescriptionResponse,
    JobLogResponse,
    QueryResponse,
    QueryResultItem,
    RerankResponse,
    RerankResultItem,
    VectorTableResponse,
)
from oracle_vecdb.services.ords.models.query_vectors200_response import (
    QueryVectors200Response,
)
from oracle_vecdb.services.ords.models.vec_db_search_item import (
    VecDBSearchItem,
)


class AttributeItem:
    def __init__(self, **values):
        self.__dict__.update(values)


def test_query_response_wraps_result_items():
    response = {
        "results": [
            {
                "id": "vec-1",
                "metadata": {"genre": "drama"},
                "vector": None,
                "distance": 0.12,
            }
        ]
    }

    wrapped = QueryResponse.from_internal(response)

    assert wrapped.items[0].id == "vec-1"  # nosec B101
    assert wrapped.results[0].metadata == {"genre": "drama"}  # nosec B101
    assert wrapped.items[0].distance == 0.12  # nosec B101


def test_public_responses_preserve_generated_serialization_methods():
    response = QueryResponse.from_internal(
        {"results": [{"id": "vec-1", "distance": 0.25}]}
    )

    payload = response.to_dict()
    assert payload["items"][0]["id"] == "vec-1"  # nosec B101
    assert '"items"' in response.to_json()  # nosec B101
    assert "vec-1" in response.to_str()  # nosec B101


def test_query_response_rejects_missing_results_field():
    with pytest.raises(ValueError, match="missing required field 'results'"):
        QueryResponse.from_internal({"count": 0})


def test_message_response_rejects_missing_message_field():
    with pytest.raises(ValueError, match="missing required field 'message'"):
        DeleteVectorsResponse.from_internal({"status": "ok"})


def test_rerank_response_wraps_result_items():
    wrapped = RerankResponse.from_internal([AttributeItem(index=1, score=0.97)])

    assert wrapped.items[0].index == 1  # nosec B101
    assert wrapped[0].score == 0.97  # nosec B101


def test_message_response_helpers_use_stable_shapes():
    existing = DeleteVectorsResponse(message="existing")
    assert (
        DeleteVectorsResponse.from_internal(existing) is existing
    )  # nosec B101
    assert (
        DeleteVectorsResponse.from_internal({"message": "deleted"}).message
        == "deleted"
    )  # nosec B101
    assert (  # nosec B101
        DeleteVectorsResponse.from_internal(
            AttributeItem(message="deleted from object")
        ).message
        == "deleted from object"
    )
    assert (
        DropVectorTableResponse.from_internal({"message": "dropped"}).message
        == "dropped"
    )  # nosec B101
    assert (
        DropIndexResponse.from_internal({"message": "index dropped"}).message
        == "index dropped"
    )  # nosec B101


def test_job_log_response_normalizes_numeric_error_value():
    response = JobLogResponse.from_internal(
        {"job_name": "job1", "status": "COMPLETED", "error": 0}
    )

    assert response.job_name == "job1"  # nosec B101
    assert response.error == "0"  # nosec B101


def test_index_and_model_response_helpers_normalize_fields():
    index_response = IndexDescriptionResponse.from_internal(
        {"Index Status": "READY"}
    )
    existing_index = IndexDescriptionResponse(index_status="VALID")
    object_index = IndexDescriptionResponse.from_internal(
        AttributeItem(index_status="BUILDING")
    )
    model_response = DropModelResponse.from_internal(
        {"dropped": "test-model", "message": "ok"}
    )
    existing_model = DropModelResponse(dropped="existing", message="ok")
    object_model = DropModelResponse.from_internal(
        AttributeItem(dropped="object-model", message="done")
    )

    assert index_response.index_status == "READY"  # nosec B101
    assert (  # nosec B101
        IndexDescriptionResponse.from_internal(existing_index) is existing_index
    )
    assert object_index.index_status == "BUILDING"  # nosec B101
    assert model_response.dropped == "test-model"  # nosec B101
    assert model_response.message == "ok"  # nosec B101
    assert (
        DropModelResponse.from_internal(existing_model) is existing_model
    )  # nosec B101
    assert object_model.dropped == "object-model"  # nosec B101
    assert object_model.message == "done"  # nosec B101


def test_vector_table_indexes_use_object_contract():
    response = VectorTableResponse.from_internal(
        {
            "table_name": "docs",
            "indexes": {
                "dense_idx_name": "VECIDX$12345",
                "indexed_metadata_json_paths": ["active", "brand", "price"],
            },
        }
    )

    assert response.indexes.dense_idx_name == "VECIDX$12345"  # nosec B101
    assert response.indexes["dense_idx_name"] == "VECIDX$12345"  # nosec B101
    assert response.to_dict()["indexes"] == {  # nosec B101
        "dense_idx_name": "VECIDX$12345",
        "indexed_metadata_json_paths": ["active", "brand", "price"],
    }


def test_vector_table_indexes_normalize_generated_objects():
    from oracle_vecdb.services.ords.models.vec_db_table_base_no_links_indexes import (
        VecDBTableBaseNoLinksIndexes,
    )

    generated = VecDBTableBaseNoLinksIndexes.from_dict(
        {
            "dense_idx_name": "VECDB_IDX_123",
            "indexed_metadata_json_paths": ["tenant"],
        }
    )
    response = VectorTableResponse.from_internal({"indexes": generated})

    assert isinstance(response.indexes, IndexDetailsResponse)  # nosec B101
    assert response.indexes.indexed_metadata_json_paths == [
        "tenant"
    ]  # nosec B101


def test_query_result_item_normalizes_existing_and_object_values():
    existing = QueryResultItem(id="vec-existing", distance=0.1)
    object_item = AttributeItem(
        id="vec-object",
        metadata={"kind": "object"},
        vector=[0.1, 0.2],
        distance=0.3,
    )

    assert QueryResultItem.from_internal(existing) is existing  # nosec B101
    wrapped = QueryResultItem.from_internal(object_item)

    assert wrapped.id == "vec-object"  # nosec B101
    assert wrapped.metadata == {"kind": "object"}  # nosec B101
    assert wrapped.vector == [0.1, 0.2]  # nosec B101
    assert wrapped.distance == 0.3  # nosec B101


def test_query_response_normalizes_items_attribute_sequence_and_existing():
    existing = QueryResponse(items=[QueryResultItem(id="existing")])
    object_response = AttributeItem(
        items=[AttributeItem(id="from-items", metadata={}, distance=0.2)]
    )
    sequence_response = [
        {"id": "from-sequence", "metadata": {"a": 1}, "distance": 0.4}
    ]

    assert QueryResponse.from_internal(existing) is existing  # nosec B101
    assert len(existing) == 1  # nosec B101
    assert (
        QueryResponse.from_internal(object_response)[0].id == "from-items"
    )  # nosec B101
    assert (  # nosec B101
        QueryResponse.from_internal(sequence_response).items[0].id
        == "from-sequence"
    )


def test_query_response_from_generated_query_vectors_response():
    internal = QueryVectors200Response(
        results=[VecDBSearchItem(id="vec-generated", distance=0.5)]
    )

    response = QueryResponse.from_internal(internal)

    assert response.items[0].id == "vec-generated"  # nosec B101
    assert response.items[0].distance == 0.5  # nosec B101


def test_rerank_result_and_response_normalize_dict_and_existing_values():
    existing_item = RerankResultItem(index=0, score=0.5)
    existing_response = RerankResponse(items=[existing_item])

    assert (
        RerankResultItem.from_internal(existing_item) is existing_item
    )  # nosec B101
    assert (
        RerankResultItem.from_internal({"index": 2, "score": 0.8}).score == 0.8
    )  # nosec B101
    assert len(existing_response) == 1  # nosec B101
    assert existing_response[0] is existing_item  # nosec B101
