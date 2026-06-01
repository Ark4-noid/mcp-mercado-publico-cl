"""Tests for the tenant-scoped repository factories."""
from __future__ import annotations

import httpx
import pytest

from core.settings import Settings
from core.tenant_context import TenantContext
from infrastructure.licitacion_repository import MercadoPublicoLicitacionRepository
from infrastructure.orden_compra_repository import MercadoPublicoOrdenCompraRepository
from repos.factory import (
    _resolve_ticket,
    make_licitacion_repo,
    make_oc_repo,
    make_scraper_repo,
)

pytestmark = pytest.mark.asyncio


async def test_resolve_ticket_from_profile(tenant_ctx: TenantContext) -> None:
    await tenant_ctx.profile_store.save({"ticket": "ABC"})
    assert await _resolve_ticket(tenant_ctx) == "ABC"


async def test_resolve_ticket_missing_raises(tenant_ctx: TenantContext) -> None:
    with pytest.raises(ValueError, match="acme"):
        await _resolve_ticket(tenant_ctx)


async def test_resolve_ticket_empty_string_raises(
    tenant_ctx: TenantContext,
) -> None:
    await tenant_ctx.profile_store.save({"ticket": ""})
    with pytest.raises(ValueError, match="no ChileCompra ticket"):
        await _resolve_ticket(tenant_ctx)


async def test_make_licitacion_repo_returns_correct_type(
    tenant_ctx: TenantContext, settings: Settings
) -> None:
    await tenant_ctx.profile_store.save({"ticket": "T1"})
    async with httpx.AsyncClient() as http:
        repo = await make_licitacion_repo(tenant_ctx, http, settings)
    assert isinstance(repo, MercadoPublicoLicitacionRepository)


async def test_make_oc_repo_returns_correct_type(
    tenant_ctx: TenantContext, settings: Settings
) -> None:
    await tenant_ctx.profile_store.save({"ticket": "T1"})
    async with httpx.AsyncClient() as http:
        repo = await make_oc_repo(tenant_ctx, http, settings)
    assert isinstance(repo, MercadoPublicoOrdenCompraRepository)


async def test_make_scraper_repo_returns_tenant_scoped_instance(
    tenant_ctx: TenantContext, settings: Settings
) -> None:
    """Chunk 3: factory returns a ScraperRepo bound to the tenant context."""
    from repos.factory import ScraperRepo

    repo = make_scraper_repo(tenant_ctx, None)
    assert isinstance(repo, ScraperRepo)
    # verificar_sesion does not need cookies and should report empty.
    res = await repo.verificar_sesion()
    assert res["tenant_id"] == "acme"
    assert res["tiene_cookies"] is False
    assert res["cantidad_cookies"] == 0
