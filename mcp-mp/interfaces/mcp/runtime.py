"""Runtime accessor that bridges stdio and HTTP transports.

Both transports populate the same module-level fields on
`interfaces.mcp.server`:
  - app_http: httpx.AsyncClient
  - app_browser_pool: BrowserPool

In HTTP mode, the lifespan handler in server.py sets these (via
app.state.http / app.state.browser_pool AND also assigns them to module
attributes). In stdio mode, run_stdio.py assigns them at bootstrap.

Tools resolve these accessors lazily - never at import time - so that
import order does not matter and tests can patch them.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.settings import Settings, get_settings

if TYPE_CHECKING:
    import httpx
    from browser_pool.pool import BrowserPool


class RuntimeNotReadyError(RuntimeError):
    """Raised when a tool runs before the transport bootstrapped the runtime."""


def get_http() -> "httpx.AsyncClient":
    import httpx

    import interfaces.mcp.server as srv

    http = getattr(srv, "app_http", None)
    if http is None:
        raise RuntimeNotReadyError(
            "HTTP client is not initialized. The transport (run_stdio.py or "
            "create_app) must set interfaces.mcp.server.app_http before tool calls."
        )
    assert isinstance(http, httpx.AsyncClient)
    return http


def get_browser_pool() -> "BrowserPool":
    from browser_pool.pool import BrowserPool

    import interfaces.mcp.server as srv

    pool = getattr(srv, "app_browser_pool", None)
    if pool is None:
        raise RuntimeNotReadyError(
            "BrowserPool is not initialized. The transport must set "
            "interfaces.mcp.server.app_browser_pool before tool calls."
        )
    assert isinstance(pool, BrowserPool)
    return pool


def get_runtime_settings() -> Settings:
    return get_settings()
