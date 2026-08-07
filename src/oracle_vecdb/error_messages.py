"""English error-message catalog for the public SDK errors."""

from typing import Mapping

ERROR_MESSAGES: Mapping[str, Mapping[str, str]] = {
    "VECDB-001": {
        "message": "Insecure REST URL: {rest_url}. HTTPS is required.",
        "cause": "Plain-text HTTP can expose authentication details in transit.",
        "action": "Set rest_url to an endpoint that starts with 'https://'.",
    },
    "VECDB-002": {
        "message": "Invalid REST URL format: {rest_url}.",
        "cause": "The REST URL does not match the required VecDB URL structure.",
        "action": "Use https://<host>:<port>/ords/<schema>/_/db-api/(stable|<version>)/vecdb/.",
    },
    "VECDB-003": {
        "message": "Invalid table name format: '{table_name}'.",
        "cause": "The table name does not match the required format.",
        "action": "Use only letters, digits, and underscore (_).",
    },
    "VECDB-004": {
        "message": "Invalid model name format: '{model_name}'.",
        "cause": "The model name does not match the required format.",
        "action": "Use only letters, digits, and underscore (_).",
    },
    "VECDB-005": {
        "message": "Invalid load job name format: '{load_job_name}'.",
        "cause": "The load job name does not match the required format.",
        "action": "Use only letters, digits, and underscore (_).",
    },
    "VECDB-006": {
        "message": "Invalid index job name format: '{index_job_name}'.",
        "cause": "The index job name does not match the required format.",
        "action": "Use only letters, digits, and underscore (_).",
    },
    "VECDB-007": {
        "message": (
            "A single vector payload is too large for the upsert operation. "
            "Size: {payload_size} bytes; maximum safe payload size: "
            "{maximum_size} bytes."
        ),
        "cause": "One vector exceeds the size the SDK can safely send in a single request.",
        "action": "Reduce the vector or metadata size, or use load_vectors for bulk ingestion.",
    },
    "VECDB-008": {
        "message": "At least one vector record is required for upsert.",
        "cause": "The vectors argument is None or empty.",
        "action": "Pass a non-empty list of vector records.",
    },
    "VECDB-009": {
        "message": "Resource not found: '{resource_name}'.",
        "cause": "The requested resource does not exist.",
        "action": "Verify the resource name and try again.",
    },
    "VECDB-010": {
        "message": (
            "Cannot fetch the log for load job '{load_job_name}' because "
            "its state is '{state}', which is not terminal."
        ),
        "cause": "The load job has not finished yet.",
        "action": "Wait until the load job reaches a terminal state before fetching its log.",
    },
    "VECDB-011": {
        "message": (
            "Cannot fetch the log for index job '{index_job_name}' because "
            "its state is '{state}', which is not terminal."
        ),
        "cause": "The index job has not finished yet.",
        "action": "Wait until the index job reaches a terminal state before fetching its log.",
    },
}
