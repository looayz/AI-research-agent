import httpx
import pytest

from app.services.fetcher import (
    BlockedURLError,
    FetchError,
    SafeFetcher,
    _GuardedNetworkBackend,
    is_public_ip,
    is_safe_url,
    resolve_public,
    validate_url_syntax,
)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "::1",
        "fd00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
        "2002:7f00:1::",
        "64:ff9b::7f00:1",
        "224.0.0.1",
    ],
)
def test_non_public_addresses_are_rejected(address):
    assert not is_public_ip(address)


@pytest.mark.parametrize("address", ["8.8.8.8", "172.217.16.142", "208.80.154.224", "2620:0:861:ed1a::1"])
def test_public_addresses_are_allowed(address):
    # 172.217.x.x is public: the first version blocked every "172." prefix.
    assert is_public_ip(address)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://example.com",
        "http://user:pass@example.com/",
        "http://",
        "not a url",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://metadata.google.internal/",
    ],
)
def test_unsafe_urls(url):
    assert not is_safe_url(url)


def test_safe_url():
    assert is_safe_url("https://en.wikipedia.org/wiki/Python")


def test_credentials_in_url_are_rejected():
    with pytest.raises(BlockedURLError):
        validate_url_syntax("https://user:secret@example.com/")


def _resolver_to(*addresses):
    async def resolve(host, port):
        return list(addresses)

    return resolve


async def test_hostname_resolving_to_private_ip_is_blocked():
    resolver = _resolver_to("93.184.216.34", "10.0.0.5")
    with pytest.raises(BlockedURLError):
        await resolve_public("rebind.example.com", 443, resolver)


async def test_decimal_ip_forms_are_resolved_then_blocked():
    # "2130706433" is 127.0.0.1 once resolved by the system resolver.
    resolver = _resolver_to("127.0.0.1")
    with pytest.raises(BlockedURLError):
        await resolve_public("2130706433", 80, resolver)


async def test_allow_private_networks_opt_in():
    resolver = _resolver_to("10.0.0.5")
    assert await resolve_public("intranet.local", 80, resolver, allow_private=True) == ["10.0.0.5"]


async def test_guarded_backend_checks_at_connect_time():
    # Anti DNS-rebinding: the address is validated when the socket is opened.
    backend = _GuardedNetworkBackend(_resolver_to("127.0.0.1"), allow_private=False)
    with pytest.raises(BlockedURLError):
        await backend.connect_tcp("innocent.example.com", 80)


def _fetcher(handler, resolver) -> SafeFetcher:
    return SafeFetcher(transport=httpx.MockTransport(handler), resolver=resolver, max_bytes=1000)


async def test_redirect_to_private_address_is_blocked():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

    async with _fetcher(handler, _resolver_to("93.184.216.34")) as fetcher:
        with pytest.raises(BlockedURLError):
            await fetcher.fetch("https://example.com/start")


async def test_redirects_are_followed_and_validated():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(301, headers={"location": "/final"})
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="<p>hello</p>")

    async with _fetcher(handler, _resolver_to("93.184.216.34")) as fetcher:
        page = await fetcher.fetch("https://example.com/start")
    assert page.final_url == "https://example.com/final"
    assert "hello" in page.text


async def test_too_many_redirects():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": f"/r{len(request.url.path)}"})

    async with _fetcher(handler, _resolver_to("93.184.216.34")) as fetcher:
        with pytest.raises(FetchError, match="Too many redirects"):
            await fetcher.fetch("https://example.com/")


async def test_unsupported_content_type_and_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
        return httpx.Response(403, text="forbidden")

    async with _fetcher(handler, _resolver_to("93.184.216.34")) as fetcher:
        with pytest.raises(FetchError, match="Unsupported content type"):
            await fetcher.fetch("https://example.com/pdf")
        with pytest.raises(FetchError, match="HTTP 403"):
            await fetcher.fetch("https://example.com/blocked")


async def test_response_size_is_capped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/plain"}, content=b"a" * 50_000)

    async with _fetcher(handler, _resolver_to("93.184.216.34")) as fetcher:
        page = await fetcher.fetch("https://example.com/big")
    assert len(page.text) == 1000
