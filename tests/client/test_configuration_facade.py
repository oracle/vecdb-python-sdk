##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

import copy
import http.client
import os
from pathlib import Path

import pytest
import oracle_vecdb.configuration as configuration_module
import oracle_vecdb.services.ords.configuration as generated_configuration

from oracle_vecdb.configuration import (
    Configuration,
    ORDSBaseConfiguration,
    ORDSConfiguration,
    apply_configuration_extensions,
)
from oracle_vecdb.vecdb_errors import (
    InsecureConnectionError,
    InvalidHostFormatError,
)

VALID_HOST = "https://example.com/ords/foo/_/db-api/stable/vecdb/"
VALID_HOST_WITH_PORT = (
    "https://example.com:8443/ords/foo/_/db-api/stable/vecdb/"
)
POOL_MAPPED_HOST = (
    "https://example.com/ords/pool-mapping/admin/_/db-api/stable/vecdb/"
)

if os.getenv("VECDB_REST_URL"):
    VALID_HOST = os.getenv("VECDB_REST_URL", VALID_HOST)


def _base_path(url: str) -> str:
    return url.removesuffix("/vecdb/").removesuffix("/")


def _reset_env_vars(monkeypatch):
    for key in (
        "VECDB_REST_URL",
        "VECDB_USERNAME",
        "VECDB_PASSWORD",
        "VECDB_VERIFY_SSL",
        "VECDB_PROXY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_configuration_rejects_removed_host_argument(monkeypatch):
    _reset_env_vars(monkeypatch)

    with pytest.raises(TypeError, match="unexpected keyword argument 'host'"):
        Configuration(host=VALID_HOST)


def test_configuration_facade_is_plain_selector():
    assert Configuration.__bases__ == (object,)  # nosec B101


def test_configuration_new_allows_subclass_construction():
    cfg = ORDSBaseConfiguration.__new__(ORDSBaseConfiguration)

    assert isinstance(cfg, ORDSBaseConfiguration)  # nosec B101


def test_configuration_module_missing_attribute_raises_attribute_error():
    with pytest.raises(AttributeError, match="does_not_exist"):
        getattr(configuration_module, "does_not_exist")


def test_configuration_extensions_are_combined_with_public_facade():
    assert callable(apply_configuration_extensions)  # nosec B101
    assert (  # nosec B101
        apply_configuration_extensions.__module__
        == "oracle_vecdb.configuration"
    )


def test_public_configuration_extends_generated_ords_base():
    assert (  # nosec B101
        ORDSBaseConfiguration.__module__ == "oracle_vecdb.configuration"
    )
    assert issubclass(  # nosec B101
        ORDSBaseConfiguration, generated_configuration.Configuration
    )
    assert issubclass(ORDSConfiguration, ORDSBaseConfiguration)  # nosec B101
    assert hasattr(ORDSBaseConfiguration, "has_rest_url")  # nosec B101


def test_generated_configuration_does_not_apply_public_extensions():
    source = Path(generated_configuration.__file__).read_text()

    assert "apply_configuration_extensions" not in source  # nosec B101


def test_configuration_uses_rest_url_alias(monkeypatch):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(rest_url=VALID_HOST)

    assert cfg.rest_url == _base_path(VALID_HOST)  # nosec B101
    assert cfg.server_index is None  # nosec B101
    assert isinstance(cfg, ORDSConfiguration)  # nosec B101
    assert type(cfg).__module__ == "oracle_vecdb.ords"  # nosec B101


def test_configuration_rejects_positional_endpoint(monkeypatch):
    _reset_env_vars(monkeypatch)

    with pytest.raises(ValueError, match="Please provide an ORDS endpoint"):
        Configuration(VALID_HOST)


@pytest.mark.parametrize("timeout", [True, 0, (1, False), (1, -1)])
def test_configuration_rejects_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="timeout"):
        Configuration(rest_url=VALID_HOST, timeout=timeout)


def test_generated_configuration_without_rest_url_reports_false():
    cfg = ORDSBaseConfiguration.__new__(ORDSBaseConfiguration)

    assert cfg.has_rest_url is False  # nosec B101
    assert cfg.rest_url == ""  # nosec B101


def test_direct_ords_configuration_initializes(monkeypatch):
    _reset_env_vars(monkeypatch)

    cfg = ORDSConfiguration(rest_url=VALID_HOST)

    assert cfg.rest_url == _base_path(VALID_HOST)  # nosec B101


def test_configuration_accepts_rest_url_with_port(monkeypatch):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(rest_url=VALID_HOST_WITH_PORT)

    assert cfg.rest_url == _base_path(VALID_HOST_WITH_PORT)  # nosec B101


def test_configuration_falls_back_to_rest_url_environment(monkeypatch):
    _reset_env_vars(monkeypatch)
    monkeypatch.setenv("VECDB_REST_URL", VALID_HOST)

    cfg = Configuration()

    assert cfg.rest_url == _base_path(VALID_HOST)  # nosec B101
    assert cfg.server_index is None  # nosec B101


def test_configuration_rejects_empty_rest_url_environment(monkeypatch):
    _reset_env_vars(monkeypatch)
    monkeypatch.setenv("VECDB_REST_URL", "")

    with pytest.raises(
        ValueError,
        match="VECDB_REST_URL.*empty.*valid rest_url",
    ):
        Configuration()


def test_configuration_requires_ords_endpoint(monkeypatch):
    _reset_env_vars(monkeypatch)

    with pytest.raises(ValueError, match="Please provide an ORDS endpoint"):
        Configuration()


def test_configuration_rejects_removed_connection_parameter(monkeypatch):
    _reset_env_vars(monkeypatch)

    with pytest.raises(
        TypeError, match="unexpected keyword argument 'connection'"
    ):
        Configuration(connection=object())


def test_configuration_rejects_empty_rest_url_parameter(monkeypatch):
    _reset_env_vars(monkeypatch)

    with pytest.raises(
        ValueError,
        match="rest_url.*empty.*valid rest_url",
    ):
        Configuration(rest_url="")


def test_configuration_accepts_exacc_pool_mapping_rest_url(monkeypatch):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(rest_url=POOL_MAPPED_HOST)

    assert cfg.rest_url == _base_path(POOL_MAPPED_HOST)  # nosec B101


def test_configuration_rejects_invalid_host(monkeypatch):
    _reset_env_vars(monkeypatch)

    with pytest.raises(InvalidHostFormatError):
        Configuration(rest_url="https://example.com/not-valid")


def test_configuration_rejects_base_path_without_scheme(monkeypatch):
    _reset_env_vars(monkeypatch)

    with pytest.raises(InvalidHostFormatError):
        Configuration(rest_url="example.com/ords/foo/_/db-api/stable/vecdb/")


def test_configuration_rejects_http_without_override(monkeypatch):
    _reset_env_vars(monkeypatch)

    with pytest.raises(InsecureConnectionError):
        Configuration(
            rest_url="http://example.com/ords/foo/_/db-api/stable/vecdb/"
        )


def test_configuration_rest_url_setter_updates_base_path(monkeypatch):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(rest_url=VALID_HOST)

    new_rest_url = "https://example.org/ords/foo/_/db-api/25.4"
    cfg.rest_url = new_rest_url

    assert cfg._base_path == new_rest_url  # nosec B101
    assert cfg.server_index is None  # nosec B101
    assert cfg.rest_url == new_rest_url  # nosec B101


def test_configuration_host_setter_cannot_bypass_rest_url_validation(
    monkeypatch,
):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(rest_url=VALID_HOST)
    original_base_path = cfg.rest_url

    with pytest.raises(AttributeError, match="rest_url"):
        cfg.host = "http://127.0.0.1:9/ords/foo/_/db-api/stable/vecdb/"

    assert cfg.rest_url == original_base_path  # nosec B101


@pytest.mark.parametrize(
    "value, expected_exception",
    [
        (
            "http://example.com/ords/foo/_/db-api/stable/vecdb/",
            InsecureConnectionError,
        ),
        ("https://example.com/not-valid", InvalidHostFormatError),
    ],
)
def test_configuration_rest_url_setter_rejects_invalid_base_paths(
    monkeypatch, value, expected_exception
):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(rest_url=VALID_HOST)
    original_base_path = cfg._base_path

    with pytest.raises(expected_exception):
        cfg.rest_url = value

    assert cfg._base_path == original_base_path  # nosec B101
    assert cfg.rest_url == original_base_path  # nosec B101


def test_api_key_with_prefix(monkeypatch):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(
        rest_url=VALID_HOST,
        api_key={"BearerAuth": "token"},
        api_key_prefix={"BearerAuth": "Bearer"},
    )

    assert (
        cfg.get_api_key_with_prefix("BearerAuth") == "Bearer token"
    )  # nosec B101


def test_api_key_with_prefix_uses_alias(monkeypatch):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(
        rest_url=VALID_HOST,
        api_key={"BearerAuth": "token"},
        api_key_prefix={"BearerAuth": "Bearer"},
    )

    assert (
        cfg.get_api_key_with_prefix("Unknown", alias="BearerAuth") == "token"
    )  # nosec B101


def test_auth_settings_with_access_token_only(monkeypatch):
    _reset_env_vars(monkeypatch)
    monkeypatch.setenv("VECDB_ACCESS_TOKEN", "abc123")

    cfg = Configuration(
        rest_url=VALID_HOST, access_token=os.getenv("VECDB_ACCESS_TOKEN")
    )

    auth = cfg.auth_settings()

    assert "BasicAuth" not in auth  # nosec B101
    assert auth["BearerAuth"]["value"] == "Bearer abc123"  # nosec B101
    assert auth["OAuth2"]["value"] == "Bearer abc123"  # nosec B101


def test_configuration_uses_env_credentials(monkeypatch):
    _reset_env_vars(monkeypatch)
    monkeypatch.setenv("VECDB_USERNAME", "env_user")
    monkeypatch.setenv("VECDB_PASSWORD", "env_pass")

    cfg = Configuration(rest_url=VALID_HOST)

    assert cfg.username == "env_user"  # nosec B101
    assert cfg.get_basic_auth_token() is not None  # nosec B101


def test_get_host_from_settings_invalid_index(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST)

    with pytest.raises(ValueError):
        cfg.get_host_from_settings(5)


def test_logger_file_sets_file_handler(tmp_path, monkeypatch):
    _reset_env_vars(monkeypatch)

    cfg = Configuration(rest_url=VALID_HOST)
    log_file = tmp_path / "vecdb.log"

    cfg.logger_file = str(log_file)

    assert cfg.logger_file_handler is not None  # nosec B101
    assert Path(cfg.logger_file_handler.baseFilename) == log_file  # nosec B101


def test_configuration_deepcopy_preserves_logger_settings(
    tmp_path, monkeypatch
):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST, debug=True)
    cfg.logger_file = str(tmp_path / "copy.log")

    clone = copy.deepcopy(cfg)

    assert clone is not cfg  # nosec B101
    assert clone.logger is not cfg.logger  # nosec B101
    assert clone.logger_file == cfg.logger_file  # nosec B101
    assert clone.debug is True  # nosec B101
    clone.debug = False


def test_logger_file_unwritable(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST)

    def boom(*_, **__):
        raise OSError("nope")

    monkeypatch.setattr("logging.FileHandler", boom)

    with pytest.raises(OSError):
        cfg.logger_file = "/root/forbidden.log"


def test_get_basic_auth_token_handles_missing_fields(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST, username=None, password=None)

    token = cfg.get_basic_auth_token()

    assert token is not None  # nosec B101

    cfg.username = "user"
    cfg.password = None
    assert cfg.get_basic_auth_token() is not None  # nosec B101


def test_api_key_with_prefix_alias_missing(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST)

    assert (
        cfg.get_api_key_with_prefix("Missing", alias="AlsoMissing") is None
    )  # nosec B101


def test_api_key_refresh_hook_and_unprefixed_key(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST)

    def refresh(target):
        target.api_key["BearerAuth"] = "fresh-token"

    cfg.refresh_api_key_hook = refresh

    assert (
        cfg.get_api_key_with_prefix("BearerAuth") == "fresh-token"
    )  # nosec B101


def test_auth_settings_with_basic_and_debug_report(monkeypatch):
    _reset_env_vars(monkeypatch)
    credential_value = "pass"
    cfg = Configuration(
        rest_url=VALID_HOST, username="user", password=credential_value
    )

    auth = cfg.auth_settings()
    report = cfg.to_debug_report()

    assert auth["BasicAuth"]["type"] == "basic"  # nosec B101
    assert auth["BasicAuth"]["value"]  # nosec B101
    assert "Python SDK Debug Report" in report  # nosec B101
    assert "ORDS Release Version: " in report  # nosec B101


def test_environment_overrides(monkeypatch):
    _reset_env_vars(monkeypatch)
    monkeypatch.setenv("VECDB_VERIFY_SSL", "false")
    monkeypatch.setenv("VECDB_PROXY", "http://proxy.example")

    cfg = Configuration(rest_url=VALID_HOST)

    assert cfg.verify_ssl is True  # nosec B101
    assert cfg.proxy is None  # nosec B101


def test_proxy_settings_constructor(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST)
    cfg.proxy = "http://proxy"
    cfg.proxy_headers = {"Authorization": "Basic abc"}

    assert cfg.proxy == "http://proxy"  # nosec B101
    assert cfg.proxy_headers["Authorization"] == "Basic abc"  # nosec B101


def test_debug_property_does_not_toggle_process_global_http_debug(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST)

    import http.client

    original = http.client.HTTPConnection.debuglevel
    http.client.HTTPConnection.debuglevel = 7
    try:
        cfg.debug = True
        assert http.client.HTTPConnection.debuglevel == 7  # nosec B101
        cfg.debug = False
        assert http.client.HTTPConnection.debuglevel == 7  # nosec B101
    finally:
        http.client.HTTPConnection.debuglevel = original


def test_generated_configuration_debug_does_not_toggle_global_http_debug_or_log_credentials(
    caplog,
):
    original = http.client.HTTPConnection.debuglevel
    username = "test-user"
    password = "test-password"  # nosec B105
    try:
        http.client.HTTPConnection.debuglevel = 7
        cfg = generated_configuration.Configuration(
            host=VALID_HOST,
            username=username,
            password=password,
        )
        cfg.debug = True
        cfg.logger["package_logger"].debug("generated configuration debug")

        assert http.client.HTTPConnection.debuglevel == 7  # nosec B101
        assert username not in caplog.text  # nosec B101
        assert password not in caplog.text  # nosec B101
        cfg.debug = False
        assert http.client.HTTPConnection.debuglevel == 7  # nosec B101
    finally:
        http.client.HTTPConnection.debuglevel = original


def test_debug_true_does_not_log_configured_credentials(caplog, monkeypatch):
    _reset_env_vars(monkeypatch)
    access_token = "Bearer test-token-that-must-not-be-logged"  # nosec B105
    cfg = Configuration(
        rest_url=VALID_HOST,
        access_token=access_token,
        username="test-user",
        password="test-password",  # nosec B106
    )

    with caplog.at_level("DEBUG"):
        cfg.debug = True
        cfg.logger["package_logger"].debug("SDK debug logging enabled")

    assert access_token not in caplog.text  # nosec B101
    assert "test-password" not in caplog.text  # nosec B101


def test_configuration_debug_constructor_sets_debug(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST, debug=True)

    assert cfg.debug is True  # nosec B101
    cfg.debug = False


def test_configuration_default_cache_uses_direct_base_class(monkeypatch):
    _reset_env_vars(monkeypatch)
    monkeypatch.setenv("VECDB_REST_URL", VALID_HOST)
    original_default = ORDSBaseConfiguration._default
    ORDSBaseConfiguration.set_default(None)

    try:
        cfg = ORDSBaseConfiguration.get_default()

        assert isinstance(cfg, ORDSBaseConfiguration)  # nosec B101
        assert ORDSBaseConfiguration.get_default_copy() is cfg  # nosec B101
    finally:
        ORDSBaseConfiguration.set_default(original_default)


def test_get_host_from_settings_substitutes_variables(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = Configuration(rest_url=VALID_HOST)
    servers = [
        {
            "url": "https://{region}.example.com/ords/foo/_/db-api/stable",
            "description": "templated",
            "variables": {
                "region": {
                    "description": "region",
                    "default_value": "us",
                    "enum_values": ["us", "eu"],
                }
            },
        }
    ]

    assert (  # nosec B101
        cfg.get_host_from_settings(0, {"region": "eu"}, servers)
        == "https://eu.example.com/ords/foo/_/db-api/stable"
    )
    with pytest.raises(ValueError, match="invalid value"):
        cfg.get_host_from_settings(0, {"region": "ap"}, servers)


def test_ords_base_configuration_properties(monkeypatch):
    _reset_env_vars(monkeypatch)
    cfg = ORDSBaseConfiguration(rest_url=VALID_HOST)

    assert cfg.has_rest_url is True  # nosec B101
    assert cfg.logger_file is None  # nosec B101
    assert "%(levelname)s" in cfg.logger_format  # nosec B101
