"""FastAPI host for the MCP server, with multi-tenant lifespan."""
from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from browser_pool.pool import BrowserPool
from core.middleware import TenantContextMiddleware
from core.settings import Settings, get_settings
from migrations.legacy import migrate_legacy_layout


logger = logging.getLogger("mp.server")


mcp = FastMCP(
    "mercado-publico",
    instructions=(
        "Servidor MCP para consultar licitaciones y órdenes de compra de la "
        "API de Mercado Público de ChileCompra."
    ),
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI host for HTTP-mode MCP."""
    settings = settings or get_settings()

    # Import-time side effect: register all MCP tools on `mcp`.
    from interfaces.mcp import tools  # noqa: F401

    # Extend the DNS-rebinding allowlist with any host the server is exposed
    # under (Cloud Run URL, custom domain, etc.). Without this, FastMCP rejects
    # the proxied Host header with 421 Misdirected Request.
    extra_hosts = [h.strip() for h in settings.allowed_hosts.split(",") if h.strip()]
    if extra_hosts:
        mcp.settings.transport_security.allowed_hosts = (
            list(mcp.settings.transport_security.allowed_hosts) + extra_hosts
        )
        mcp.settings.transport_security.allowed_origins = (
            list(mcp.settings.transport_security.allowed_origins)
            + [f"https://{h}" for h in extra_hosts]
        )

    mcp_app = mcp.streamable_http_app()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Migrate legacy layout (idempotent, never deletes source).
        env_ticket = os.environ.get(settings.legacy_ticket_env)
        summary = migrate_legacy_layout(
            settings.local_root, legacy_ticket_env_value=env_ticket, tenant_id="local"
        )
        if summary.get("moved"):
            logger.info("legacy migration moved: %s", summary["moved"])
        if summary.get("migrated_ticket"):
            logger.info("legacy ticket migrated into local profile")

        # Pools shared across requests.
        http = httpx.AsyncClient(timeout=30.0)
        browser_pool = BrowserPool(max_browsers=settings.max_browsers)
        try:
            await browser_pool.start()
        except RuntimeError as exc:
            # Playwright not installed (scraper extra missing). Server can still
            # serve API-only tools; scraper tools will error at call time.
            logger.warning("BrowserPool disabled: %s", exc)

        app.state.settings = settings
        app.state.http = http
        app.state.browser_pool = browser_pool

        # Make these reachable from runtime helpers (stdio path also sets them).
        import interfaces.mcp.server as srv
        srv.app_http = http  # type: ignore[attr-defined]
        srv.app_browser_pool = browser_pool  # type: ignore[attr-defined]

        try:
            async with mcp_app.router.lifespan_context(mcp_app):
                yield
        finally:
            await http.aclose()
            await browser_pool.stop()

    app = FastAPI(title="MCP Mercado Público", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Order matters: middleware wraps mcp_app, then mount at /.
    app.add_middleware(TenantContextMiddleware, settings=settings)
    app.mount("/", mcp_app)

    return app
