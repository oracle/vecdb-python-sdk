##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

"""Compatibility patches layered on top of regenerated OpenAPI runtime code."""

from __future__ import annotations

import importlib
import os
import re
import sys
import tempfile
import types
from typing import Any, Dict, Mapping, Optional

DEFAULT_ORDS_AUTH_SETTINGS = [
    "OAuth2",
    "OAuth2",
    "OAuth2",
    "BasicAuth",
    "BearerAuth",
]

_ApiException: Any = None
_ApiResponse: Any = None
_ORIGINAL_PARAM_SERIALIZE: Any = None


def _import_optional_module(module_name: str) -> Optional[Any]:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return None
        raise


def _resolve_attr(
    module_name: str, attr_name: str, *, required: bool = True
) -> Any:
    module = _import_optional_module(module_name)
    if module is None:
        if required:
            raise RuntimeError(f"Generated module not found: {module_name}")
        return None

    value = getattr(module, attr_name, None)
    if value is None and required:
        raise RuntimeError(
            f"Generated attribute not found: {module_name}.{attr_name}"
        )
    return value


def _api_exception_cls() -> Any:
    global _ApiException

    if _ApiException is None:
        _ApiException = _resolve_attr(
            "oracle_vecdb.services.ords.exceptions", "ApiException"
        )
    return _ApiException


def _api_response_cls() -> Any:
    global _ApiResponse

    if _ApiResponse is None:
        _ApiResponse = _resolve_attr(
            "oracle_vecdb.services.ords.api_response", "ApiResponse"
        )
    return _ApiResponse


def _camel_to_snake(name: str) -> str:
    partial = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", partial).lower()


def _resolve_model_class(class_name: str, module_name: str) -> Any:
    models_pkg = _import_optional_module("oracle_vecdb.services.ords.models")
    if models_pkg is not None:
        model_cls = getattr(models_pkg, class_name, None)
        if model_cls is not None:
            return model_cls

    return _resolve_attr(
        f"oracle_vecdb.services.ords.models.{module_name}",
        class_name,
        required=False,
    )


def _install_model_alias(
    class_name: str, target_cls: Any, module_name: Optional[str] = None
) -> None:
    resolved_module_name = module_name or _camel_to_snake(class_name)
    models_pkg = _resolve_attr("oracle_vecdb.services.ords", "models")
    setattr(models_pkg, class_name, target_cls)

    alias_module_name = (
        f"oracle_vecdb.services.ords.models.{resolved_module_name}"
    )
    alias_module = sys.modules.get(alias_module_name)
    if alias_module is None:
        alias_module = types.ModuleType(alias_module_name)
        alias_module.__package__ = "oracle_vecdb.services.ords.models"
        sys.modules[alias_module_name] = alias_module

    setattr(alias_module, class_name, target_cls)
    setattr(alias_module, "__all__", [class_name])


def _model_payload(model: Any) -> Any:
    to_dict = getattr(model, "to_dict", None)
    if callable(to_dict):
        return to_dict()

    model_dump = getattr(model, "model_dump", None)
    if callable(model_dump):
        return model_dump(by_alias=True, exclude_none=True)

    return model


def _make_rebuild_index_request_wrapper(
    generated_request_cls: Any, create_index_params_cls: Any
) -> Any:
    class RebuildIndexRequest(generated_request_cls):
        """Compatibility wrapper for older generated index param models."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            field_name = (
                "index_params" if "index_params" in kwargs else "indexParams"
            )
            original_index_params = kwargs.get(field_name)

            if isinstance(original_index_params, create_index_params_cls):
                compat_kwargs = dict(kwargs)
                compat_kwargs[field_name] = _model_payload(
                    original_index_params
                )
                super().__init__(*args, **compat_kwargs)
                object.__setattr__(self, "index_params", original_index_params)
                return

            super().__init__(*args, **kwargs)

    RebuildIndexRequest.__name__ = "RebuildIndexRequest"
    RebuildIndexRequest.__qualname__ = "RebuildIndexRequest"
    RebuildIndexRequest.__module__ = generated_request_cls.__module__
    return RebuildIndexRequest


def _patch_index_param_models() -> None:
    vector_index_params_cls = _resolve_model_class(
        "VectorIndexParams", "vector_index_params"
    )
    create_index_params_cls = _resolve_model_class(
        "CreateIndexRequestIndexParams", "create_index_request_index_params"
    )
    rebuild_index_params_cls = _resolve_model_class(
        "RebuildIndexRequestIndexParams", "rebuild_index_request_index_params"
    )
    rebuild_index_request_cls = _resolve_model_class(
        "RebuildIndexRequest", "rebuild_index_request"
    )

    if create_index_params_cls is None and vector_index_params_cls is not None:
        create_index_params_cls = vector_index_params_cls
        _install_model_alias(
            "CreateIndexRequestIndexParams",
            create_index_params_cls,
            "create_index_request_index_params",
        )

    if rebuild_index_params_cls is None and vector_index_params_cls is not None:
        rebuild_index_params_cls = vector_index_params_cls
        _install_model_alias(
            "RebuildIndexRequestIndexParams",
            rebuild_index_params_cls,
            "rebuild_index_request_index_params",
        )

    if (
        rebuild_index_request_cls is not None
        and create_index_params_cls is not None
        and rebuild_index_params_cls is not None
        and create_index_params_cls is not rebuild_index_params_cls
    ):
        rebuild_index_request_cls = _make_rebuild_index_request_wrapper(
            rebuild_index_request_cls, create_index_params_cls
        )
        _install_model_alias(
            "RebuildIndexRequest",
            rebuild_index_request_cls,
            "rebuild_index_request",
        )


def _response_headers(response: Any) -> Mapping[str, Any]:
    headers = getattr(response, "headers", None)
    if headers is not None:
        return headers

    getheaders = getattr(response, "getheaders", None)
    if callable(getheaders):
        resolved = getheaders() or {}
        if isinstance(resolved, Mapping):
            return resolved
        try:
            return dict(resolved)
        except (TypeError, ValueError):
            return {}

    return {}


def _header_value(
    headers: Mapping[str, Any], name: str, default: Optional[str] = None
) -> Optional[str]:
    if name in headers:
        value = headers[name]
        return value if isinstance(value, str) else default

    lowered = name.lower()
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == lowered:
            return value if isinstance(value, str) else default
    return default


def _patched_response_deserialize(
    self: Any,
    response_data: Any,
    response_types_map: Optional[Dict[str, Any]] = None,
) -> Any:
    msg = (
        "RESTResponse.read() must be called before passing it to "
        "response_deserialize()"
    )
    if response_data.data is None:
        raise AssertionError(msg)

    resolved_types = response_types_map or {}
    response_type = resolved_types.get(str(response_data.status), None)
    if (
        not response_type
        and isinstance(response_data.status, int)
        and 100 <= response_data.status <= 599
    ):
        response_type = resolved_types.get(
            str(response_data.status)[0] + "XX", None
        )

    headers = _response_headers(response_data)
    response_text = None
    return_data = None
    try:
        if response_type in ("bytearray", "bytes"):
            return_data = response_data.data
        elif response_type == "file":
            return_data = self._ApiClient__deserialize_file(response_data)
        elif response_type is not None:
            match = None
            content_type = _header_value(headers, "content-type")
            if content_type is not None:
                match = re.search(
                    r"charset=([a-zA-Z\-\d]+)[\s;]?", content_type
                )
            encoding = match.group(1) if match else "utf-8"
            response_text = response_data.data.decode(encoding)
            return_data = self.deserialize(
                response_text, response_type, content_type
            )
    finally:
        if not 200 <= response_data.status <= 299:
            raise _api_exception_cls().from_response(
                http_resp=response_data,
                body=response_text,
                data=return_data,
            )

    return _api_response_cls()(
        status_code=response_data.status,
        data=return_data,
        headers=dict(headers),
        raw_data=response_data.data,
    )


def _patched_deserialize_file(self: Any, response: Any) -> str:
    fd, path = tempfile.mkstemp(dir=self.configuration.temp_folder_path)
    os.close(fd)
    os.remove(path)

    headers = _response_headers(response)
    content_disposition = _header_value(headers, "content-disposition")
    if content_disposition:
        match = re.search(
            r'filename=[\'"]?([^\'"\s]+)[\'"]?', content_disposition
        )
        if match is None:
            raise AssertionError(
                "Unexpected 'content-disposition' header value"
            )
        filename = os.path.basename(match.group(1))
        if filename in ("", ".", ".."):
            filename = os.path.basename(path)
        path = os.path.join(os.path.dirname(path), filename)

    with open(path, "wb") as file_handle:
        file_handle.write(response.data)

    return path


def _patched_api_exception_init(
    self: Any,
    status: Optional[int] = None,
    reason: Optional[str] = None,
    http_resp: Optional[Any] = None,
    *,
    body: Optional[str] = None,
    data: Optional[Any] = None,
) -> None:
    self.status = status
    self.reason = reason
    self.body = body
    self.data = data
    self.headers = None

    if http_resp:
        if self.status is None:
            self.status = http_resp.status
        if self.reason is None:
            self.reason = http_resp.reason
        if self.body is None:
            try:
                self.body = http_resp.data.decode("utf-8")
            except Exception:
                self.body = None
        self.headers = dict(_response_headers(http_resp))


def _patched_param_serialize(self: Any, *args: Any, **kwargs: Any) -> Any:
    auth_settings = kwargs.get("auth_settings")
    if auth_settings == [] and kwargs.get("_request_auth") is None:
        compat_kwargs = dict(kwargs)
        compat_kwargs["auth_settings"] = list(DEFAULT_ORDS_AUTH_SETTINGS)
        return _ORIGINAL_PARAM_SERIALIZE(self, *args, **compat_kwargs)
    return _ORIGINAL_PARAM_SERIALIZE(self, *args, **kwargs)


def _patched_create_vector_table_serialize(
    self: Any,
    create_vector_table_request: Any,
    _request_auth: Optional[Dict[str, Any]],
    _content_type: Optional[str],
    _headers: Optional[Dict[str, Any]],
    _host_index: int,
) -> Any:
    del _host_index

    _header_params: Dict[str, Optional[str]] = _headers or {}
    _body_params = create_vector_table_request

    if "Accept" not in _header_params:
        _header_params["Accept"] = self.api_client.select_header_accept(
            ["application/json", "application/problem+json"]
        )

    if _content_type:
        _header_params["Content-Type"] = _content_type
    else:
        default_content_type = self.api_client.select_header_content_type(
            ["application/json"]
        )
        if default_content_type is not None:
            _header_params["Content-Type"] = default_content_type

    return self.api_client.param_serialize(
        method="POST",
        resource_path="/vecdb/vector-tables/",
        path_params={},
        query_params=[],
        header_params=_header_params,
        body=_body_params,
        post_params=[],
        files={},
        auth_settings=list(DEFAULT_ORDS_AUTH_SETTINGS),
        collection_formats={},
        _host=None,
        _request_auth=_request_auth,
    )


def apply_runtime_compatibility() -> None:
    """Patch regenerated runtime behavior to preserve SDK compatibility."""

    global _ORIGINAL_PARAM_SERIALIZE

    api_client_cls = _resolve_attr(
        "oracle_vecdb.services.ords.api_client", "ApiClient"
    )
    api_exception_cls = _api_exception_cls()
    vector_tables_api_cls = _resolve_attr(
        "oracle_vecdb.services.ords.api.vector_database_vector_tables_api",
        "VectorDatabaseVectorTablesApi",
    )

    if _ORIGINAL_PARAM_SERIALIZE is None:
        current_param_serialize = api_client_cls.param_serialize
        _ORIGINAL_PARAM_SERIALIZE = getattr(
            current_param_serialize,
            "_oracle_vecdb_original",
            current_param_serialize,
        )

    setattr(
        _patched_param_serialize,
        "_oracle_vecdb_original",
        _ORIGINAL_PARAM_SERIALIZE,
    )

    api_client_cls.response_deserialize = _patched_response_deserialize
    api_client_cls._ApiClient__deserialize_file = _patched_deserialize_file
    api_client_cls.param_serialize = _patched_param_serialize
    api_exception_cls.__init__ = _patched_api_exception_init
    vector_tables_api_cls._create_vector_table_serialize = (
        _patched_create_vector_table_serialize
    )

    _patch_index_param_models()
