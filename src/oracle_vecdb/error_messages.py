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
        "message": "Invalid table name: '{table_name}'.",
        "cause": "The table name must be non-empty text and must not contain NUL or double-quote characters.",
        "action": 'Provide a non-empty table name without NUL (`\\x00`) or double-quote (`"`) characters. Other character and length restrictions are determined by the configured Oracle Database.',
    },
    "VECDB-004": {
        "message": "Invalid model name format: '{model_name}'.",
        "cause": "The model name must be non-empty text and must not contain NUL or double-quote characters.",
        "action": 'Provide a non-empty model name without NUL (`\\x00`) or double-quote (`"`) characters. Other character and length restrictions are determined by the configured Oracle Database.',
    },
    "VECDB-005": {
        "message": "Invalid load job name format: '{load_job_name}'.",
        "cause": "The load job name must be non-empty text and must not contain NUL or double-quote characters.",
        "action": 'Provide a non-empty load job name without NUL (`\\x00`) or double-quote (`"`) characters. Other character and length restrictions are determined by the configured Oracle Database.',
    },
    "VECDB-006": {
        "message": "Invalid index job name format: '{index_job_name}'.",
        "cause": "The index job name must be non-empty text and must not contain NUL or double-quote characters.",
        "action": 'Provide a non-empty index job name without NUL (`\\x00`) or double-quote (`"`) characters. Other character and length restrictions are determined by the configured Oracle Database.',
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
    "VECDB-012": {
        "message": (
            "CommonSpec defaults for '{function_name}' do not match public "
            "parameters: {parameter_names}."
        ),
        "cause": (
            "The CommonSpec catalog references a parameter that the decorated "
            "function does not accept."
        ),
        "action": (
            "Update CommonSpec or the function signature so their parameter "
            "names match."
        ),
    },
    "VECDB-013": {
        "message": "Invalid value or combination for {parameter_name}: {detail}",
        "cause": "The request violates a deterministic parameter constraint defined by the VecDB PL/SQL API.",
        "action": "Correct the parameter value or combination and retry the operation.",
    },
}
