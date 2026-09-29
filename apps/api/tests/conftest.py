"""Hermetic test configuration.

Environment variables are set before the app is imported so a developer's
``.env`` can never leak into the tests. The suite runs on a throwaway SQLite
file by default, or on PostgreSQL when ``TEST_DATABASE_URL`` is set (CI).
Outbound network access is blocked: every provider is exercised through
mocks or ``httpx.MockTransport``.
"""

import ipaddress
import os
import socket
import tempfile

_TMP = tempfile.mkdtemp(prefix="ara-tests-")
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_TMP}/test.db"
os.environ.update(
    {
        "MOCK_MODE": "false",
        "LLM_PROVIDER": "mock",
        "SEARCH_PROVIDER": "mock",
        "REDIS_URL": "",
        "DEBUG": "false",
        "LOG_LEVEL": "WARNING",
        "MEMORY_RECALL_ENABLED": "true",
    }
)


import httpx  # noqa: E402
import pytest  # noqa: E402

_real_connect = socket.socket.connect
_real_getaddrinfo = socket.getaddrinfo
_LOCAL_NAMES = {"localhost", "test", None}


def _is_local(host) -> bool:
    if host in _LOCAL_NAMES:
        return True
    try:
        return ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return False


def _guarded_connect(self, address):
    if self.family == socket.AF_UNIX or (isinstance(address, tuple) and _is_local(address[0])):
        return _real_connect(self, address)
    raise RuntimeError(f"Network access is disabled in tests (tried to connect to {address!r})")


def _guarded_getaddrinfo(host, *args, **kwargs):
    if _is_local(host):
        return _real_getaddrinfo(host, *args, **kwargs)
    raise RuntimeError(f"DNS lookups are disabled in tests (tried to resolve {host!r})")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)


@pytest.fixture(autouse=True)
async def _database():
    from app.core.cache import close_cache
    from app.core.database import engine, init_db

    await init_db()
    yield
    from app.services.tasks import task_manager

    await task_manager.shutdown(timeout=2)
    await close_cache()
    # Pooled connections are bound to this test's event loop.
    await engine.dispose()


@pytest.fixture
async def client():
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
