##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""PL/SQL-grounded default arguments shared by VecDB client transports.

The public facade can use this catalog before delegating to either ORDS or a
native SQL*Net backend.  Entries use public Python method and parameter names,
not names from legacy PL/SQL overloads or transport-specific request fields.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, ClassVar, Mapping


class DefaultSettings:
    """Return independent copies of verified public-operation defaults.

    The values below come from the current canonical ``DBMS_VECTOR_DATABASE``
    entry points in ``prvtvectordb.sql``.  Only defaults that are meaningful to
    materialize in the public Python call are included.  ``None`` defaults are
    deliberately omitted: the future decorator must preserve the distinction
    between an omitted value and a caller explicitly supplying ``None``.
    """

    # This catalog contains unconditional, sensible defaults for public
    # operations.  They can be applied without inspecting another argument
    # in the same request (for example, list_vectors.limit).
    #
    # Defaults such as distribute_method="AUTO" do not belong here because
    # they are operation-dependent nested values: they are meaningful only
    # after the caller selects an INMEMORY GRAPH index organization.
    _DEFAULT_ARGUMENTS: ClassVar[Mapping[str, Mapping[str, Any]]] = {
        # create_vector_table(..., table_params JSON DEFAULT NULL) normalizes
        # an omitted table_params value to auto_generate_id=false.
        "create_vector_table": {
            "table_params": {"auto_generate_id": False},
        },
        # list_vectors(..., limit IN NUMBER DEFAULT 15, ...).
        "list_vectors": {
            "limit": 15,
        },
        # OracleVecDB.query maps to DBMS_VECTOR_DATABASE.search, whose
        # include_vectors parameter defaults to FALSE.
        "query": {
            "include_vectors": False,
        },
    }

    @classmethod
    def get_default_args_for(cls, function_name: str) -> dict[str, Any]:
        """Return defaults for ``function_name`` without sharing mutables.

        Unknown operations intentionally return an empty dictionary so the
        decorator can be applied to every public facade method safely.
        """
        return deepcopy(dict(cls._DEFAULT_ARGUMENTS.get(function_name, {})))

    @classmethod
    def apply_operation_aware_defaults(
        cls,
        function_name: str,
        arguments: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return arguments with any operation-aware defaults materialized.

        Index distribution is intentionally not defaulted.  Callers selecting
        ``INMEMORY GRAPH`` must explicitly choose a valid
        ``distribute_method`` so the SDK does not hide an incomplete request.
        The hook remains for future verified operation-aware defaults.
        """
        del function_name
        return dict(arguments)
