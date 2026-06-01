from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from core.middleware import TenantContextMiddleware
from core.tenant_context import current_tenant


@pytest.fixture
def asgi_app(settings):
    app = FastAPI()

    @app.get("/whoami")
    async def whoami():
        ctx = current_tenant()
        return JSONResponse({"tenant_id": ctx.tenant_id})

    app.add_middleware(TenantContextMiddleware, settings=settings)
    return app


@pytest.fixture
async def client(asgi_app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_valid_tenant_sets_context(client: AsyncClient) -> None:
    r = await client.get("/whoami", headers={"X-Tenant-Id": "acme"})
    assert r.status_code == 200
    assert r.json() == {"tenant_id": "acme"}


@pytest.mark.asyncio
async def test_missing_header_returns_400(client: AsyncClient) -> None:
    r = await client.get("/whoami")
    assert r.status_code == 400
    assert "Missing X-Tenant-Id" in r.json()["error"]


@pytest.mark.asyncio
async def test_invalid_tenant_returns_400(client: AsyncClient) -> None:
    r = await client.get("/whoami", headers={"X-Tenant-Id": "BAD_NAME"})
    assert r.status_code == 400
    assert "Invalid X-Tenant-Id" in r.json()["error"]


@pytest.mark.asyncio
async def test_case_normalization(client: AsyncClient) -> None:
    r = await client.get("/whoami", headers={"X-Tenant-Id": "  Acme  "})
    assert r.status_code == 200
    assert r.json() == {"tenant_id": "acme"}


@pytest.mark.asyncio
async def test_isolation_between_concurrent_requests(client: AsyncClient) -> None:
    a, b = await asyncio.gather(
        client.get("/whoami", headers={"X-Tenant-Id": "tenant-a"}),
        client.get("/whoami", headers={"X-Tenant-Id": "tenant-b"}),
    )
    assert a.json()["tenant_id"] == "tenant-a"
    assert b.json()["tenant_id"] == "tenant-b"


@pytest.mark.asyncio
async def test_context_reset_after_request(client: AsyncClient) -> None:
    r1 = await client.get("/whoami", headers={"X-Tenant-Id": "first"})
    r2 = await client.get("/whoami", headers={"X-Tenant-Id": "second"})
    assert r1.json()["tenant_id"] == "first"
    assert r2.json()["tenant_id"] == "second"
