"""Authentication helpers for Oracle VecDB."""

from __future__ import annotations

import json
import ssl
from typing import Any, Dict, Mapping, Optional, Tuple, Union
from urllib.parse import urlsplit

import urllib3

from .vecdb_errors import OAuthTokenError

Timeout = Union[float, Tuple[float, float]]
OAuthTokenResponse = Dict[str, Any]

_SUPPORTED_SOCKS_PROXIES = frozenset({"socks5", "socks5h", "socks4", "socks4a"})


def get_vecdb_oauth_token(
    *,
    client_id: str,
    client_secret: str,
    token_url: str,
    timeout: Timeout = 30.0,
    verify_ssl: bool = True,
    ssl_ca_cert: Optional[str] = None,
    ca_cert_data: Optional[Union[str, bytes]] = None,
    proxy: Optional[str] = None,
    proxy_headers: Optional[Mapping[str, str]] = None,
) -> OAuthTokenResponse:
    """Request an OAuth bearer token using client credentials.

    Args:
        client_id: OAuth client identifier.
        client_secret: OAuth client secret.
        token_url: HTTPS URL of the OAuth token endpoint.
        timeout: Request timeout in seconds, or ``(connect, read)`` seconds.
        verify_ssl: Whether to verify the TLS certificate.
        ssl_ca_cert: Optional path to a custom CA certificate bundle.
        ca_cert_data: Optional CA certificate data.
        proxy: Optional HTTP, HTTPS, or SOCKS proxy URL.
        proxy_headers: Optional headers for the proxy request.

    Returns:
        The OAuth token response, including ``access_token``,
        ``token_type``, and ``expires_in``.

    Raises:
        OAuthTokenError: If validation, transport, HTTP, JSON, or token
            response validation fails.

    Example:

        .. code-block:: python

            from oracle_vecdb import Configuration, OracleVecDB
            from oracle_vecdb.auth import get_vecdb_oauth_token

            token_response = get_vecdb_oauth_token(
                client_id="example-client-id",
                client_secret="example",
                token_url=(
                    "https://localhost:8443/ords/vector3/oauth/token"
                ),
            )

            config = Configuration(
                rest_url=(
                    "https://<host>/ords/<schema>/_/db-api/"
                    "stable/vecdb/"
                ),
                access_token=token_response["access_token"],
            )

            client = OracleVecDB(config)

        For a local server with a self-signed certificate, prefer
        ``ssl_ca_cert``. Set ``verify_ssl=False`` only as an explicit
        development-only exception.
    """
    safe_endpoint = _safe_endpoint(token_url)

    _validate_credentials(client_id, client_secret, safe_endpoint)
    _validate_token_url(token_url, safe_endpoint)
    request_timeout = _build_timeout(timeout, safe_endpoint)

    pool = None
    response = None
    transport_failed = False

    try:
        pool = _build_pool(
            verify_ssl=verify_ssl,
            ssl_ca_cert=ssl_ca_cert,
            ca_cert_data=ca_cert_data,
            proxy=proxy,
            proxy_headers=proxy_headers,
        )

        authorization = urllib3.util.make_headers(
            basic_auth=f"{client_id}:{client_secret}"
        )["authorization"]

        response = pool.request(
            "POST",
            token_url,
            headers={
                "Authorization": authorization,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            fields={"grant_type": "client_credentials"},
            encode_multipart=False,
            timeout=request_timeout,
            preload_content=True,
        )

        if not 200 <= response.status < 300:
            raise OAuthTokenError(
                safe_endpoint,
                f"HTTP {response.status} response",
                status=response.status,
            )

        payload = _parse_response(response.data, safe_endpoint)
        _validate_token_response(payload, safe_endpoint)
        return payload

    except OAuthTokenError:
        raise
    except (urllib3.exceptions.HTTPError, OSError, ValueError):
        transport_failed = True
    finally:
        if response is not None:
            response.release_conn()
        if pool is not None:
            pool.clear()

    if transport_failed:
        raise OAuthTokenError(
            safe_endpoint,
            "transport or request configuration failure",
        ) from None


def _validate_credentials(
    client_id: str,
    client_secret: str,
    safe_endpoint: str,
) -> None:
    """Validate that OAuth credentials are non-empty strings.

    Args:
        client_id: OAuth client identifier.
        client_secret: OAuth client secret.
        safe_endpoint: Sanitized endpoint used in error messages.

    Raises:
        OAuthTokenError: If either credential is missing or invalid.
    """
    if not isinstance(client_id, str) or not client_id.strip():
        raise OAuthTokenError(
            safe_endpoint,
            "client_id must be a non-empty string",
        )

    if not isinstance(client_secret, str) or not client_secret:
        raise OAuthTokenError(
            safe_endpoint,
            "client_secret must be a non-empty string",
        )


def _validate_token_url(
    token_url: str,
    safe_endpoint: str,
) -> None:
    """Validate that the token endpoint is a safe HTTPS URL.

    The endpoint must use HTTPS, contain a hostname, and must not contain
    embedded username, password, or fragment values.

    Args:
        token_url: OAuth token endpoint to validate.
        safe_endpoint: Sanitized endpoint used in error messages.

    Raises:
        OAuthTokenError: If the endpoint is invalid or insecure.
    """
    if not isinstance(token_url, str) or not token_url.strip():
        raise OAuthTokenError(
            safe_endpoint,
            "token_url must be a non-empty HTTPS URL",
        )

    try:
        parsed = urlsplit(token_url)
        parsed.port
    except (TypeError, ValueError):
        raise OAuthTokenError(
            safe_endpoint,
            "token_url is not a valid URL",
        ) from None

    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        raise OAuthTokenError(
            safe_endpoint,
            "token_url must be an HTTPS URL without embedded credentials",
        )


def _build_timeout(
    timeout: Timeout,
    safe_endpoint: str,
) -> urllib3.Timeout:
    """Create a urllib3 timeout configuration.

    Args:
        timeout: Either a positive total timeout in seconds or a
            ``(connect, read)`` timeout tuple.
        safe_endpoint: Sanitized endpoint used in error messages.

    Returns:
        A configured ``urllib3.Timeout`` instance.

    Raises:
        OAuthTokenError: If the timeout is invalid or non-positive.
    """
    if isinstance(timeout, bool):
        raise OAuthTokenError(safe_endpoint, "timeout must be positive")

    if isinstance(timeout, (int, float)):
        if timeout <= 0:
            raise OAuthTokenError(safe_endpoint, "timeout must be positive")
        return urllib3.Timeout(total=float(timeout))

    if (
        isinstance(timeout, tuple)
        and len(timeout) == 2
        and all(
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and value > 0
            for value in timeout
        )
    ):
        return urllib3.Timeout(
            connect=float(timeout[0]),
            read=float(timeout[1]),
        )

    raise OAuthTokenError(
        safe_endpoint,
        "timeout must be a positive number or (connect, read)",
    )


def _build_pool(
    *,
    verify_ssl: bool,
    ssl_ca_cert: Optional[str],
    ca_cert_data: Optional[Union[str, bytes]],
    proxy: Optional[str],
    proxy_headers: Optional[Mapping[str, str]],
) -> Any:
    """Create an urllib3 connection pool for the token request.

    The pool is configured with TLS certificate verification, an optional
    custom CA certificate, and an optional HTTP, HTTPS, or SOCKS proxy.

    Args:
        verify_ssl: Whether TLS certificates must be verified.
        ssl_ca_cert: Optional path to a CA certificate bundle.
        ca_cert_data: Optional CA certificate data.
        proxy: Optional proxy URL.
        proxy_headers: Optional headers sent to the proxy.

    Returns:
        An ``urllib3.PoolManager``, ``urllib3.ProxyManager``, or
        ``SOCKSProxyManager`` instance.
    """
    pool_args: Dict[str, Any] = {
        "cert_reqs": (ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE),
        "ca_certs": ssl_ca_cert,
        "ca_cert_data": ca_cert_data,
    }

    if proxy:
        proxy_scheme = proxy.split("://", 1)[0].lower()
        if proxy_scheme in _SUPPORTED_SOCKS_PROXIES:
            from urllib3.contrib.socks import SOCKSProxyManager

            pool_args["proxy_url"] = proxy
            pool_args["headers"] = dict(proxy_headers or {})
            return SOCKSProxyManager(**pool_args)

        return urllib3.ProxyManager(
            proxy_url=proxy,
            proxy_headers=dict(proxy_headers or {}),
            **pool_args,
        )

    return urllib3.PoolManager(**pool_args)


def _parse_response(
    response_data: bytes,
    safe_endpoint: str,
) -> OAuthTokenResponse:
    """Parse and validate that an OAuth response is valid JSON.

    This function verifies that the response body can be decoded as UTF-8,
    contains valid JSON, and represents a JSON object. It does not validate
    OAuth-specific fields such as ``access_token`` or ``expires_in``;
    that is handled by ``_validate_token_response``.

    Args:
        response_data: Raw response body returned by the OAuth server.
        safe_endpoint: Sanitized endpoint used in error messages.

    Returns:
        The decoded JSON object.

    Raises:
        OAuthTokenError: If the response is not valid UTF-8, valid JSON,
            or a JSON object.
    """
    try:
        payload = json.loads(response_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OAuthTokenError(
            safe_endpoint,
            "OAuth response was not valid JSON",
        ) from None

    if not isinstance(payload, dict):
        raise OAuthTokenError(
            safe_endpoint,
            "OAuth response must be a JSON object",
        )

    return payload


def _validate_token_response(
    payload: OAuthTokenResponse,
    safe_endpoint: str,
) -> None:
    """Validate required fields in an OAuth bearer-token response.

    Args:
        payload: Parsed OAuth response object.
        safe_endpoint: Sanitized endpoint used in error messages.

    Raises:
        OAuthTokenError: If the response does not contain a valid bearer
            access token or contains an invalid expiration value.
    """
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthTokenError(
            safe_endpoint,
            "OAuth response did not contain a valid access_token",
        )

    token_type = payload.get("token_type")
    if not isinstance(token_type, str) or token_type.lower() != "bearer":
        raise OAuthTokenError(
            safe_endpoint,
            "OAuth response did not contain bearer token_type",
        )

    expires_in = payload.get("expires_in")
    if expires_in is not None and (
        isinstance(expires_in, bool)
        or not isinstance(expires_in, int)
        or expires_in <= 0
    ):
        raise OAuthTokenError(
            safe_endpoint,
            "OAuth response contained an invalid expires_in value",
        )


def _safe_endpoint(token_url: str) -> str:
    """Create a safe endpoint description for diagnostics.

    Query strings, fragments, usernames, and passwords are excluded so the
    returned value cannot accidentally expose credentials or sensitive URL
    parameters. This function intentionally does not raise an exception:
    it is used while validating input and while building error messages.

    Args:
        token_url: Candidate OAuth endpoint URL.

    Returns:
        A sanitized endpoint string, or ``"<invalid-token-endpoint>"`` if
        the URL cannot be parsed safely.
    """
    if not isinstance(token_url, str):
        return "<invalid-token-endpoint>"

    try:
        parsed = urlsplit(token_url)
        hostname = parsed.hostname

        if not hostname:
            return "<invalid-token-endpoint>"

        try:
            port = parsed.port
        except ValueError:
            return "<invalid-token-endpoint>"
    except (TypeError, ValueError):
        return "<invalid-token-endpoint>"

    host = hostname
    if ":" in host:
        host = f"[{host}]"

    authority = host
    if port is not None:
        authority = f"{authority}:{port}"

    return f"{parsed.scheme}://{authority}{parsed.path or '/'}"
