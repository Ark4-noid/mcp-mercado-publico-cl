"""Factories for tenant-scoped repositories.

Each factory takes a `TenantContext` and returns a repository wired to that
tenant's ChileCompra ticket. The ticket is resolved from the tenant's profile;
no environment fallback to avoid cross-tenant leakage.
"""
from __future__ import annotations

from typing import Any

import httpx

from core.settings import Settings
from core.tenant_context import TenantContext


async def _resolve_ticket(ctx: TenantContext) -> str:
    """Resolve the ChileCompra ticket from the tenant profile.

    Resolution order:
      1. profile['ticket'] (canonical, multi-tenant)
      2. raise ValueError if missing or empty - the caller (middleware) can
         turn this into an HTTP 400.
    """
    profile = await ctx.profile_store.get()
    if profile is not None:
        ticket = profile.get("ticket")
        if isinstance(ticket, str) and ticket:
            return ticket
    raise ValueError(
        f"Tenant {ctx.tenant_id!r} has no ChileCompra ticket configured. "
        "Set profile['ticket'] via guardar_perfil_proveedor."
    )


async def make_licitacion_repo(
    ctx: TenantContext,
    http: httpx.AsyncClient,
    settings: Settings,
) -> Any:
    """Build a `MercadoPublicoLicitacionRepository` scoped to one tenant."""
    from infrastructure.licitacion_repository import (
        MercadoPublicoLicitacionRepository,
    )
    from infrastructure.mercado_publico_client import MercadoPublicoClient

    ticket = await _resolve_ticket(ctx)
    client = MercadoPublicoClient(
        base_url=str(settings.chilecompra_base_url),
        ticket=ticket,
        http=http,
    )
    return MercadoPublicoLicitacionRepository(client)


async def make_oc_repo(
    ctx: TenantContext,
    http: httpx.AsyncClient,
    settings: Settings,
) -> Any:
    """Build a `MercadoPublicoOrdenCompraRepository` scoped to one tenant."""
    from infrastructure.mercado_publico_client import MercadoPublicoClient
    from infrastructure.orden_compra_repository import (
        MercadoPublicoOrdenCompraRepository,
    )

    ticket = await _resolve_ticket(ctx)
    client = MercadoPublicoClient(
        base_url=str(settings.chilecompra_base_url),
        ticket=ticket,
        http=http,
    )
    return MercadoPublicoOrdenCompraRepository(client)


async def make_scraper_repo(
    ctx: TenantContext,
    http: httpx.AsyncClient,
    settings: Settings,
) -> Any:
    """Build a scraper-backed repo for the tenant.

    The legacy scraper module (`scraper.src.scraper`) exposes `MPBrowser` and
    auth helpers but no formal repository abstraction. Wiring a tenant-aware
    scraper repo requires the BrowserPool integration and cookie-secret
    plumbing scheduled for Chunk 4.
    """
    raise NotImplementedError(
        "Scraper repository factory lands in Chunk 4 "
        "(needs BrowserPool + per-tenant cookie injection)."
    )
