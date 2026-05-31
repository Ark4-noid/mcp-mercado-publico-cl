"""Pool of Playwright Chromium browsers reused across requests.

Multi-tenant safety: each `acquire_context` yields a fresh `BrowserContext`
that is closed on exit, so cookies and storage state never leak between
tenants. Browser instances themselves are reused for performance.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Playwright,
        async_playwright,
    )

    HAS_PLAYWRIGHT = True
except ImportError:  # pragma: no cover - scraper extra not installed
    HAS_PLAYWRIGHT = False
    async_playwright = None  # type: ignore[assignment]
    Browser = BrowserContext = Playwright = object  # type: ignore[misc,assignment]


_PLAYWRIGHT_MISSING_MSG = (
    "Playwright not installed. Install with: uv sync --extra scraper"
)


class BrowserPool:
    """Pool of Playwright Chromium browsers reused across requests.

    Lifecycle:
      - start(): launches `max_browsers` chromium instances at app startup.
      - acquire_context(cookies): yields a fresh BrowserContext with cookies
        injected; the context is closed on `__aexit__` so no scraper state
        leaks between requests (multi-tenant safety).
      - stop(): closes all browsers and stops Playwright. Idempotent.

    Concurrency model: a single asyncio.Semaphore guards browser checkouts.
    Cloud Run is configured with concurrency=1, so contention should be rare.
    """

    def __init__(self, max_browsers: int = 2) -> None:
        if max_browsers < 1:
            raise ValueError("max_browsers must be >= 1")
        self._max_browsers = max_browsers
        self._playwright: Playwright | None = None
        self._browsers: list[Browser] = []
        self._semaphore = asyncio.Semaphore(max_browsers)
        self._rr_index = 0
        self._rr_lock = asyncio.Lock()
        self._started = False

    async def start(self) -> None:
        if not HAS_PLAYWRIGHT:
            raise RuntimeError(_PLAYWRIGHT_MISSING_MSG)
        if self._started:
            return
        assert async_playwright is not None
        self._playwright = await async_playwright().start()
        for _ in range(self._max_browsers):
            browser = await self._playwright.chromium.launch(headless=True)
            self._browsers.append(browser)
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            return
        for browser in self._browsers:
            try:
                await browser.close()
            except Exception:  # noqa: BLE001 - best-effort teardown
                pass
        self._browsers.clear()
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:  # noqa: BLE001
                pass
            self._playwright = None
        self._started = False

    async def _next_browser(self) -> Browser:
        async with self._rr_lock:
            browser = self._browsers[self._rr_index % len(self._browsers)]
            self._rr_index += 1
            return browser

    @asynccontextmanager
    async def acquire_context(
        self, cookies: list[dict[str, Any]] | None = None
    ) -> AsyncIterator[BrowserContext]:
        if not self._started:
            raise RuntimeError(
                "BrowserPool not started. Call await pool.start() first."
            )
        async with self._semaphore:
            browser = await self._next_browser()
            context = await browser.new_context()
            try:
                if cookies:
                    await context.add_cookies(cookies)  # type: ignore[arg-type]
                yield context
            finally:
                try:
                    await context.close()
                except Exception:  # noqa: BLE001
                    pass
