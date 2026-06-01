"""Stdio entrypoint for the MCP server (Claude Desktop, local CLI)."""
from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

load_dotenv()

import httpx

from browser_pool.pool import BrowserPool
from core.settings import get_settings
from core.tenant_context import TenantContext, set_current_tenant
from interfaces.mcp import tools  # noqa: F401 — registers MCP tools
from interfaces.mcp.server import mcp
from migrations.legacy import migrate_legacy_layout
from profile_store.factory import make_profile_store
from secrets_provider.factory import make_secrets
from storage.factory import make_storage


logger = logging.getLogger("mp.stdio")


def _bootstrap() -> tuple[httpx.AsyncClient, BrowserPool]:
    settings = get_settings()

    env_ticket = os.environ.get(settings.legacy_ticket_env)
    summary = migrate_legacy_layout(
        settings.local_root, legacy_ticket_env_value=env_ticket, tenant_id="local"
    )
    if summary.get("moved"):
        logger.info("legacy migration moved: %s", summary["moved"])

    tenant_id = "local"
    ctx = TenantContext(
        tenant_id=tenant_id,
        storage=make_storage(settings, tenant_id),
        secrets=make_secrets(settings, tenant_id),
        profile_store=make_profile_store(settings, tenant_id),
    )
    set_current_tenant(ctx)

    http = httpx.AsyncClient(timeout=30.0)
    # Browser pool starts lazily on first scraper tool call (stdio uses its own loop).
    browser_pool = BrowserPool(max_browsers=settings.max_browsers)

    # Stash on the server module so tools can reach them.
    import interfaces.mcp.server as srv
    srv.app_http = http  # type: ignore[attr-defined]
    srv.app_browser_pool = browser_pool  # type: ignore[attr-defined]

    return http, browser_pool


def main() -> None:
    http, pool = _bootstrap()
    try:
        mcp.run(transport="stdio")
    finally:
        import asyncio

        async def _cleanup() -> None:
            await http.aclose()
            await pool.stop()

        try:
            asyncio.run(_cleanup())
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
