"""End-to-end multi-tenant isolation tests.

These tests exercise the full FastAPI stack (TenantContextMiddleware +
tenant-scoped factories) end-to-end at the ASGI level, and also verify
that tool handlers — when invoked with `set_current_tenant(...)` — produce
properly isolated state per tenant.

Why two layers:
  - The HTTP layer tests verify that the middleware correctly rejects
    invalid/missing tenant headers (REQ-2 / REQ-3 of the spec).
  - The handler-level tests verify REQ-10: no cross-tenant data leakage
    between profile_store / secrets / storage. Going through the full
    MCP streamable_http transport would require negotiating session IDs
    and SSE framing, which is out of scope for an isolation test.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from httpx import ASGITransport

from core.settings import Settings
from core.tenant_context import (
    TenantContext,
    reset_current_tenant,
    set_current_tenant,
)
from interfaces.mcp.server import create_app
from profile_store.factory import make_profile_store
from secrets_provider.factory import make_secrets
from storage.factory import make_storage


pytestmark = pytest.mark.asyncio


def _build_ctx(settings: Settings, tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        storage=make_storage(settings, tenant_id),
        secrets=make_secrets(settings, tenant_id),
        profile_store=make_profile_store(settings, tenant_id),
    )


# ─── HTTP layer (middleware) ─────────────────────────────────────────────────


async def test_missing_tenant_header_returns_400(settings: Settings) -> None:
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        # POST /mcp/ goes through the middleware; missing X-Tenant-Id => 400.
        r = await client.post("/mcp/", json=body)
        assert r.status_code == 400
        assert "X-Tenant-Id" in r.text


async def test_invalid_tenant_format_returns_400(settings: Settings) -> None:
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        headers = {"X-Tenant-Id": "INVALID_UPPERCASE"}
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        r = await client.post("/mcp/", headers=headers, json=body)
        assert r.status_code == 400


async def test_health_endpoint_does_not_require_tenant(
    settings: Settings,
) -> None:
    app = create_app(settings)
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


# ─── Tenant isolation (handler-level) ────────────────────────────────────────


async def test_profile_isolation_between_tenants(settings: Settings) -> None:
    """REQ-10: profile data does not leak between tenants."""
    from interfaces.mcp import tools as tools_module

    ctx_a = _build_ctx(settings, "tenant-a")
    ctx_b = _build_ctx(settings, "tenant-b")

    # Tenant A saves a profile.
    tok = set_current_tenant(ctx_a)
    try:
        res = await tools_module.guardar_perfil_proveedor(
            {
                "empresa": "ACME SA",
                "rut": "11.111.111-1",
                "representante_legal": "Juan Pérez",
                "direccion": "Av. Siempre Viva 742",
                "telefono": "+56912345678",
                "email": "ventas@acme.cl",
            }
        )
        assert res.get("success") is True
    finally:
        reset_current_tenant(tok)

    # Tenant B reads its (empty) profile.
    tok = set_current_tenant(ctx_b)
    try:
        res_b = await tools_module.obtener_perfil_proveedor()
        assert res_b.get("perfil") is None, (
            f"Tenant B saw tenant A's profile! Got: {res_b}"
        )
    finally:
        reset_current_tenant(tok)

    # Tenant A reads its own profile back.
    tok = set_current_tenant(ctx_a)
    try:
        res_a = await tools_module.obtener_perfil_proveedor()
        assert res_a.get("perfil") is not None
        assert res_a["perfil"]["empresa"] == "ACME SA"
        assert res_a.get("tenant_id") == "tenant-a"
    finally:
        reset_current_tenant(tok)


async def test_cookies_isolation_between_tenants(settings: Settings) -> None:
    """REQ-10: scraper cookies do not leak between tenants."""
    from interfaces.mcp import scraper_tools

    ctx_alpha = _build_ctx(settings, "alpha")
    ctx_beta = _build_ctx(settings, "beta")

    cookies = json.dumps(
        [
            {
                "name": "ASP.NET_SessionId",
                "value": "secret-a",
                "domain": "mercadopublico.cl",
                "path": "/",
            }
        ]
    )

    # Alpha uploads cookies.
    tok = set_current_tenant(ctx_alpha)
    try:
        res = await scraper_tools.subir_cookies_scraper(cookies)
        assert res.get("ok") is True
        assert res.get("cantidad") == 1
    finally:
        reset_current_tenant(tok)

    # Alpha sees its cookies.
    tok = set_current_tenant(ctx_alpha)
    try:
        res_alpha = await scraper_tools.verificar_sesion_scraper()
        assert res_alpha.get("tiene_cookies") is True
        assert res_alpha.get("cantidad_cookies") == 1
        assert res_alpha.get("tenant_id") == "alpha"
    finally:
        reset_current_tenant(tok)

    # Beta sees NOTHING.
    tok = set_current_tenant(ctx_beta)
    try:
        res_beta = await scraper_tools.verificar_sesion_scraper()
        assert res_beta.get("tiene_cookies") is False, (
            f"Tenant beta leaked alpha's cookies! Got: {res_beta}"
        )
        assert res_beta.get("cantidad_cookies") == 0
        assert res_beta.get("tenant_id") == "beta"
    finally:
        reset_current_tenant(tok)


async def test_storage_isolation_between_tenants(settings: Settings) -> None:
    """REQ-10: storage data does not leak between tenants."""
    ctx_one = _build_ctx(settings, "one")
    ctx_two = _build_ctx(settings, "two")

    await ctx_one.storage.write_bytes("ofertas/X/file.txt", b"hello from one")

    assert await ctx_one.storage.exists("ofertas/X/file.txt") is True
    assert await ctx_two.storage.exists("ofertas/X/file.txt") is False

    data = await ctx_one.storage.read_bytes("ofertas/X/file.txt")
    assert data == b"hello from one"
