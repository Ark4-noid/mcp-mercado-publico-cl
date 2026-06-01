"""Integration tests for TenantContextMiddleware in google auth mode."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from core.auth import AuthError, TokenClaims
from core.middleware import TenantContextMiddleware
from core.settings import Settings, reset_settings_cache
from core.tenant_context import current_tenant


@pytest.fixture
def google_settings(
    tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch
) -> Settings:
    for key in list(os.environ):
        if key.startswith("MP_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    monkeypatch.setenv("MP_AUTH_PROVIDER", "google")
    monkeypatch.setenv("MP_OAUTH_AUDIENCE", "https://mcp-test.run.app")
    reset_settings_cache()
    s = Settings()
    s.validate_runtime()
    return s


@pytest.fixture
def asgi_app(google_settings: Settings) -> FastAPI:
    app = FastAPI()

    @app.get("/whoami")
    async def whoami() -> JSONResponse:
        return JSONResponse({"tenant_id": current_tenant().tenant_id})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.add_middleware(TenantContextMiddleware, settings=google_settings)
    return app


@pytest.fixture
async def client(asgi_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_missing_authorization_returns_401(client: AsyncClient) -> None:
    r = await client.get("/whoami")
    assert r.status_code == 401
    headers_lower = {k.lower() for k in r.headers}
    assert "www-authenticate" in headers_lower


@pytest.mark.asyncio
async def test_malformed_authorization_returns_401(
    client: AsyncClient,
) -> None:
    r = await client.get("/whoami", headers={"Authorization": "Basic xxx"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient) -> None:
    async def fail(token: str, audience: str) -> TokenClaims:
        raise AuthError("expired")

    with patch("core.middleware.verify_google_id_token", side_effect=fail):
        r = await client.get(
            "/whoami", headers={"Authorization": "Bearer bad.jwt.here"}
        )
    assert r.status_code == 401
    assert "expired" in r.json()["error"]


@pytest.mark.asyncio
async def test_valid_token_sets_context(client: AsyncClient) -> None:
    async def ok(token: str, audience: str) -> TokenClaims:
        return TokenClaims(
            sub="108451823765400000000", email="u@x.cl", audience=audience
        )

    with patch("core.middleware.verify_google_id_token", side_effect=ok):
        r = await client.get(
            "/whoami", headers={"Authorization": "Bearer good.jwt.here"}
        )
    assert r.status_code == 200
    assert r.json() == {"tenant_id": "108451823765400000000"}


@pytest.mark.asyncio
async def test_health_bypasses_auth(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_sequential_requests_isolated(client: AsyncClient) -> None:
    async def ok_a(token: str, audience: str) -> TokenClaims:
        return TokenClaims(
            sub="100000000000000000001", email=None, audience=audience
        )

    async def ok_b(token: str, audience: str) -> TokenClaims:
        return TokenClaims(
            sub="100000000000000000002", email=None, audience=audience
        )

    with patch("core.middleware.verify_google_id_token", side_effect=ok_a):
        a = await client.get(
            "/whoami", headers={"Authorization": "Bearer t-a"}
        )
    with patch("core.middleware.verify_google_id_token", side_effect=ok_b):
        b = await client.get(
            "/whoami", headers={"Authorization": "Bearer t-b"}
        )
    assert a.json()["tenant_id"] == "100000000000000000001"
    assert b.json()["tenant_id"] == "100000000000000000002"


@pytest.mark.asyncio
async def test_settings_validate_runtime_requires_audience(
    tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in list(os.environ):
        if key.startswith("MP_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    monkeypatch.setenv("MP_AUTH_PROVIDER", "google")
    reset_settings_cache()
    s = Settings()
    with pytest.raises(ValueError, match="MP_OAUTH_AUDIENCE"):
        s.validate_runtime()
