"""SSRF-safe page fetching.

URLs come from search results, i.e. from the open web, so they must be
treated as hostile: a result can point at ``http://169.254.169.254`` (cloud
metadata), at a host that resolves to a private address, or redirect there.

Defences:
- only http(s), no credentials in the URL;
- every address a host resolves to must be globally routable;
- the check is repeated at connection time by a custom network backend, so a
  DNS answer that changes between check and connect (rebinding) is caught;
- redirects are followed manually and each hop is validated again;
- response size and content types are capped.
"""

import asyncio
import ipaddress
import logging
import re
import socket
import urllib.request
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

import httpcore
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

Resolver = Callable[[str, int], Awaitable[list[str]]]

MAX_REDIRECTS = 5
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "text/markdown")
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_META_CHARSET_RE = re.compile(rb"""<meta[^>]+charset=["']?([A-Za-z0-9_\-]+)""", re.IGNORECASE)


class FetchError(Exception):
    """The page could not be retrieved."""


class BlockedURLError(FetchError):
    """The URL targets a disallowed scheme or a non-public address."""


@dataclass
class FetchedPage:
    url: str
    final_url: str
    content_type: str
    text: str


def is_public_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    if ip.version == 6:
        if ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        elif ip.sixtofour:
            ip = ip.sixtofour
        elif ip in _NAT64:
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return ip.is_global and not ip.is_multicast


async def system_resolver(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0] for info in infos))


async def resolve_public(host: str, port: int, resolver: Resolver, allow_private: bool = False) -> list[str]:
    """Resolve ``host`` and return its addresses, refusing non-public ones."""
    host = host.strip("[]")
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
        addresses = [host]
    except ValueError:
        try:
            addresses = await resolver(host, port)
        except OSError as exc:
            raise FetchError(f"DNS resolution failed for {host}") from exc
    if not addresses:
        raise FetchError(f"No address for {host}")
    if not allow_private and not all(is_public_ip(a) for a in addresses):
        raise BlockedURLError(f"{host} resolves to a non-public address")
    return addresses


def validate_url_syntax(url: str) -> httpx.URL:
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, TypeError, ValueError) as exc:
        raise BlockedURLError(f"Invalid URL: {url!r}") from exc
    if parsed.scheme not in ("http", "https"):
        raise BlockedURLError(f"Scheme not allowed: {parsed.scheme or '(none)'}")
    if not parsed.host:
        raise BlockedURLError("URL has no host")
    if parsed.userinfo:
        raise BlockedURLError("Credentials in URLs are not allowed")
    return parsed


def is_safe_url(url: str) -> bool:
    """Synchronous syntax + literal-IP check (no DNS). Kept for quick filtering."""
    try:
        parsed = validate_url_syntax(url)
    except BlockedURLError:
        return False
    host = parsed.host.strip("[]")
    if host.lower() in ("localhost", "localhost.localdomain") or host.lower().endswith((".localhost", ".local", ".internal")):
        return False
    try:
        ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return True
    return is_public_ip(host)


class _GuardedNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolves and validates hosts at connect time, then connects to the IP.

    TLS still uses the original hostname (SNI and certificate checks happen
    in httpcore's ``start_tls`` with ``server_hostname=<host>``).
    """

    def __init__(self, resolver: Resolver, allow_private: bool):
        self._inner = httpcore.AnyIOBackend()
        self._resolver = resolver
        self._allow_private = allow_private

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        addresses = await resolve_public(host, port, self._resolver, self._allow_private)
        last_exc: Optional[Exception] = None
        for address in addresses:
            try:
                return await self._inner.connect_tcp(
                    address, port, timeout=timeout, local_address=local_address, socket_options=socket_options
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_exc = exc
        raise httpcore.ConnectError(f"Could not connect to {host}") from last_exc

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise httpcore.ConnectError("Unix sockets are not allowed")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class _GuardedTransport(httpx.AsyncHTTPTransport):
    def __init__(self, resolver: Resolver, allow_private: bool):
        super().__init__(trust_env=False)
        # Same pool httpx would build, plus the validating network backend.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(),
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=5.0,
            network_backend=_GuardedNetworkBackend(resolver, allow_private),
        )


def _env_proxy_configured() -> bool:
    proxies = urllib.request.getproxies()
    return any(proxies.get(key) for key in ("http", "https", "all"))


def _decode(body: bytes, charset: Optional[str]) -> str:
    if not charset:
        match = _META_CHARSET_RE.search(body[:4096])
        charset = match.group(1).decode("ascii", "ignore") if match else "utf-8"
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


class SafeFetcher:
    """Async context manager holding one HTTP client for a batch of fetches."""

    def __init__(
        self,
        *,
        timeout: float = settings.FETCH_TIMEOUT_SECONDS,
        max_bytes: int = settings.FETCH_MAX_BYTES,
        user_agent: str = settings.FETCH_USER_AGENT,
        allow_private: bool = settings.FETCH_ALLOW_PRIVATE_NETWORKS,
        resolver: Resolver = system_resolver,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.user_agent = user_agent
        self.allow_private = allow_private
        self.resolver = resolver
        self._transport = transport
        self._client: Optional[httpx.AsyncClient] = None

    def _build_client(self) -> httpx.AsyncClient:
        common = {
            "timeout": httpx.Timeout(self.timeout, connect=min(self.timeout, 8.0)),
            "follow_redirects": False,
            "headers": {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.5",
                "Accept-Language": "en,fr;q=0.8,*;q=0.5",
            },
        }
        if self._transport is not None:
            return httpx.AsyncClient(transport=self._transport, **common)
        if _env_proxy_configured():
            # Traffic has to go through an outbound proxy, which resolves hosts
            # itself: rely on the pre-request validation of every hop.
            return httpx.AsyncClient(trust_env=True, **common)
        return httpx.AsyncClient(transport=_GuardedTransport(self.resolver, self.allow_private), trust_env=False, **common)

    async def __aenter__(self) -> "SafeFetcher":
        self._client = self._build_client()
        return self

    async def __aexit__(self, *exc_info) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _validate(self, url: str) -> None:
        parsed = validate_url_syntax(url)
        await resolve_public(
            parsed.host, parsed.port or (443 if parsed.scheme == "https" else 80), self.resolver, self.allow_private
        )

    async def fetch(self, url: str) -> FetchedPage:
        if self._client is None:
            raise RuntimeError("SafeFetcher must be used as an async context manager")
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            await self._validate(current)
            try:
                async with self._client.stream("GET", current) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError(f"Redirect without location from {current}")
                        current = urljoin(str(response.url), location)
                        continue
                    if response.status_code >= 400:
                        raise FetchError(f"HTTP {response.status_code}")
                    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if content_type and not content_type.startswith(ALLOWED_CONTENT_TYPES):
                        raise FetchError(f"Unsupported content type {content_type}")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) >= self.max_bytes:
                            del body[self.max_bytes :]
                            break
                    return FetchedPage(
                        url=url,
                        final_url=str(response.url),
                        content_type=content_type or "text/html",
                        text=_decode(bytes(body), response.charset_encoding),
                    )
            except httpx.HTTPError as exc:
                raise FetchError(f"{type(exc).__name__}: {exc}") from exc
        raise FetchError("Too many redirects")
