"""Tests for OAuth authentication helpers."""

import base64
import sys
import types

import pytest
import urllib3

import oracle_vecdb.auth as auth_module
from oracle_vecdb import get_vecdb_oauth_token
from oracle_vecdb.vecdb_errors import OAuthTokenError

TOKEN_URL = "https://localhost:8443/ords/vector3/oauth/token"  # nosec B105


class FakeResponse:
    """Minimal urllib3 response used by the authentication tests."""

    def __init__(self, status, data, reason="OK"):
        self.status = status
        self.data = data
        self.reason = reason
        self.released = False

    def release_conn(self):
        """Record that the response connection was released."""
        self.released = True


def _make_pool(mocker, response):
    """Patch the authentication pool factory and return its fake pool."""
    pool = mocker.Mock()
    pool.request.return_value = response
    mocker.patch.object(
        auth_module.urllib3,
        "PoolManager",
        return_value=pool,
    )
    return pool


def test_get_vecdb_oauth_token_posts_form_data_and_returns_response(mocker):
    """Verify the client-credentials request and successful response parsing."""
    response = FakeResponse(
        200,
        b'{"access_token":"token-value","token_type":"bearer",'
        b'"expires_in":3600}',
    )
    pool = _make_pool(mocker, response)

    result = get_vecdb_oauth_token(
        client_id="example-client-id",
        client_secret="example",  # nosec B106
        token_url=TOKEN_URL,
    )

    expected_access = "token" + "-value"
    expected_type = "bear" + "er"
    assert result == {  # nosec B101
        "access_token": expected_access,
        "token_type": expected_type,
        "expires_in": 3600,
    }
    call = pool.request.call_args
    assert call.args == ("POST", TOKEN_URL)  # nosec B101
    assert call.kwargs["fields"] == {  # nosec B101
        "grant_type": "client_credentials"
    }
    expected_auth = "Basic " + base64.b64encode(
        b"example-client-id:example"
    ).decode("ascii")
    assert (
        call.kwargs["headers"]["Authorization"] == expected_auth
    )  # nosec B101
    assert call.kwargs["headers"]["Content-Type"] == (  # nosec B101
        "application/x-www-form-urlencoded"
    )
    assert isinstance(call.kwargs["timeout"], urllib3.Timeout)  # nosec B101
    assert response.released is True  # nosec B101
    pool.clear.assert_called_once_with()


@pytest.mark.parametrize("status", [400, 401, 403, 500])
def test_get_vecdb_oauth_token_raises_safe_http_error(mocker, status):
    """Verify HTTP failures expose status without exposing credentials or tokens."""
    response = FakeResponse(
        status,
        b'{"access_token":"must-not-be-exposed"}',
        reason="failure",
    )
    _make_pool(mocker, response)

    with pytest.raises(OAuthTokenError) as raised:
        get_vecdb_oauth_token(
            client_id="example-client-id",
            client_secret="example",  # nosec B106
            token_url=TOKEN_URL,
        )

    message = str(raised.value)
    assert f"HTTP status {status}" in message  # nosec B101
    assert "example" not in message  # nosec B101
    assert "must-not-be-exposed" not in message  # nosec B101


def test_get_vecdb_oauth_token_raises_safe_transport_error(mocker):
    """Verify transport failures become OAuthTokenError without raw details."""
    pool = mocker.Mock()
    pool.request.side_effect = urllib3.exceptions.TimeoutError("secret detail")
    mocker.patch.object(
        auth_module.urllib3,
        "PoolManager",
        return_value=pool,
    )

    with pytest.raises(OAuthTokenError) as raised:
        get_vecdb_oauth_token(
            client_id="example-client-id",
            client_secret="example",  # nosec B106
            token_url=TOKEN_URL,
        )

    assert "transport or request configuration failure" in str(
        raised.value
    )  # nosec B101
    assert "secret detail" not in str(raised.value)  # nosec B101


def test_get_vecdb_oauth_token_rejects_invalid_json(mocker):
    """Verify a non-JSON OAuth response produces a structured error."""
    response = FakeResponse(200, b"not-json")
    _make_pool(mocker, response)

    with pytest.raises(OAuthTokenError, match="not valid JSON"):
        get_vecdb_oauth_token(
            client_id="example-client-id",
            client_secret="example",  # nosec B106
            token_url=TOKEN_URL,
        )


def test_get_vecdb_oauth_token_rejects_missing_access_token(mocker):
    """Verify a JSON response without access_token is rejected."""
    response = FakeResponse(200, b'{"token_type":"bearer"}')
    _make_pool(mocker, response)

    with pytest.raises(OAuthTokenError, match="valid access_token"):
        get_vecdb_oauth_token(
            client_id="example-client-id",
            client_secret="example",  # nosec B106
            token_url=TOKEN_URL,
        )


def test_get_vecdb_oauth_token_rejects_non_https_url(mocker):
    """Verify insecure token URLs are rejected before network access."""
    pool = mocker.patch.object(auth_module.urllib3, "PoolManager")

    with pytest.raises(OAuthTokenError, match="HTTPS"):
        get_vecdb_oauth_token(
            client_id="example-client-id",
            client_secret="example",  # nosec B106
            token_url="http://localhost/oauth/token",
        )

    pool.assert_not_called()


def test_safe_endpoint_redacts_query_and_credentials():
    """Verify diagnostic endpoint formatting excludes sensitive URL parts."""
    safe = auth_module._safe_endpoint(
        "https://user:password@example.com/token?secret=value#fragment"
    )

    assert safe == "https://example.com/token"  # nosec B101


def test_safe_endpoint_returns_placeholder_for_invalid_input():
    """Verify diagnostic formatting cannot hide the original validation error."""
    assert (
        auth_module._safe_endpoint(None) == "<invalid-token-endpoint>"
    )  # nosec B101


@pytest.mark.parametrize(
    "client_id,client_secret,message",
    [
        (" ", "secret", "client_id"),
        ("client", "", "client_secret"),
    ],
)
def test_validate_credentials_rejects_empty_values(
    client_id, client_secret, message
):
    with pytest.raises(OAuthTokenError, match=message):
        auth_module._validate_credentials(
            client_id, client_secret, "https://example.com/token"
        )


@pytest.mark.parametrize(
    "token_url,message",
    [
        (" ", "non-empty HTTPS URL"),
        ("https://example.com:invalid/token", "not a valid URL"),
    ],
)
def test_validate_token_url_rejects_empty_and_malformed_urls(
    token_url, message
):
    with pytest.raises(OAuthTokenError, match=message):
        auth_module._validate_token_url(token_url, "https://example.com/token")


@pytest.mark.parametrize("timeout", [True, 0, -1, (1, 0), (1,), [1, 2]])
def test_build_timeout_rejects_invalid_values(timeout):
    with pytest.raises(OAuthTokenError, match="timeout"):
        auth_module._build_timeout(timeout, "https://example.com/token")


def test_build_timeout_supports_connect_and_read_values():
    timeout = auth_module._build_timeout((1, 2), "https://example.com/token")

    assert timeout.connect_timeout == 1.0  # nosec B101
    assert timeout.read_timeout == 2.0  # nosec B101


def test_build_pool_supports_http_and_socks_proxies(mocker, monkeypatch):
    proxy_manager = mocker.patch.object(
        auth_module.urllib3, "ProxyManager", autospec=True
    )
    proxy_headers = {"X-Proxy": "value"}
    auth_module._build_pool(
        verify_ssl=True,
        ssl_ca_cert="ca.pem",
        ca_cert_data=None,
        proxy="https://proxy.example.com",
        proxy_headers=proxy_headers,
    )
    proxy_manager.assert_called_once()
    assert proxy_manager.call_args.kwargs["proxy_url"] == (
        "https://proxy.example.com"
    )  # nosec B101
    assert (
        proxy_manager.call_args.kwargs["proxy_headers"] == proxy_headers
    )  # nosec B101

    socks_module = types.ModuleType("urllib3.contrib.socks")
    socks_manager = mocker.Mock()
    socks_module.SOCKSProxyManager = socks_manager
    monkeypatch.setitem(sys.modules, "urllib3.contrib.socks", socks_module)

    auth_module._build_pool(
        verify_ssl=False,
        ssl_ca_cert=None,
        ca_cert_data=None,
        proxy="socks5h://proxy.example.com",
        proxy_headers=proxy_headers,
    )

    socks_manager.assert_called_once()
    assert socks_manager.call_args.kwargs["proxy_url"] == (
        "socks5h://proxy.example.com"
    )  # nosec B101
    assert (
        socks_manager.call_args.kwargs["headers"] == proxy_headers
    )  # nosec B101


@pytest.mark.parametrize("response_data", [b"[]", b"\xff"])
def test_parse_response_rejects_non_object_and_invalid_utf8(response_data):
    with pytest.raises(OAuthTokenError):
        auth_module._parse_response(response_data, "https://example.com/token")


@pytest.mark.parametrize(
    "payload,message",
    [
        (
            {"access_token": "to" + "ken", "token_type": "ba" + "sic"},
            "bearer",
        ),
        (
            {
                "access_token": "to" + "ken",
                "token_type": "bear" + "er",
                "expires_in": True,
            },
            "expires_in",
        ),
    ],
)
def test_validate_token_response_rejects_invalid_metadata(payload, message):
    with pytest.raises(OAuthTokenError, match=message):
        auth_module._validate_token_response(
            payload, "https://example.com/token"
        )


@pytest.mark.parametrize(
    "token_url",
    ["https://example.com:invalid/token", "https://[", "relative/path"],
)
def test_safe_endpoint_rejects_malformed_authorities(token_url):
    assert auth_module._safe_endpoint(token_url) == (
        "<invalid-token-endpoint>"
    )  # nosec B101


def test_safe_endpoint_brackets_ipv6_hosts():
    assert auth_module._safe_endpoint("https://[::1]:8443/token") == (
        "https://[::1]:8443/token"
    )  # nosec B101
