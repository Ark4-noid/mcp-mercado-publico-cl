"""Tests for the Playwright browser pool.

Playwright launches are slow, so most tests are marked `slow`. The default
`pytest -m "not slow"` run covers the lifecycle smoke test only.
"""
from __future__ import annotations

import asyncio

import pytest

from browser_pool.pool import HAS_PLAYWRIGHT, BrowserPool

pytestmark = pytest.mark.asyncio


@pytest.mark.skipif(HAS_PLAYWRIGHT, reason="playwright is installed")
async def test_start_raises_when_playwright_missing() -> None:
    pool = BrowserPool(max_browsers=1)
    with pytest.raises(RuntimeError, match="Playwright not installed"):
        await pool.start()


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
async def test_lifecycle() -> None:
    pool = BrowserPool(max_browsers=1)
    try:
        await pool.start()
        assert pool._started is True
        assert len(pool._browsers) == 1
    finally:
        await pool.stop()
    assert pool._started is False
    # Double stop is a no-op
    await pool.stop()


@pytest.mark.slow
@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
async def test_acquire_context_yields_fresh() -> None:
    pool = BrowserPool(max_browsers=1)
    await pool.start()
    try:
        async with pool.acquire_context() as ctx1:
            id1 = id(ctx1)
        async with pool.acquire_context() as ctx2:
            id2 = id(ctx2)
        assert id1 != id2
    finally:
        await pool.stop()


@pytest.mark.slow
@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
async def test_cookies_injected() -> None:
    pool = BrowserPool(max_browsers=1)
    await pool.start()
    try:
        cookies = [
            {
                "name": "x",
                "value": "y",
                "url": "https://example.com",
            }
        ]
        async with pool.acquire_context(cookies=cookies) as ctx:
            stored = await ctx.cookies("https://example.com")
            names = {c["name"] for c in stored}
            assert "x" in names
    finally:
        await pool.stop()


@pytest.mark.slow
@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
async def test_context_closed_on_exit() -> None:
    pool = BrowserPool(max_browsers=1)
    await pool.start()
    try:
        async with pool.acquire_context() as ctx:
            captured = ctx
        with pytest.raises(Exception):
            await captured.cookies()
    finally:
        await pool.stop()


@pytest.mark.slow
@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
async def test_semaphore_limits_concurrency() -> None:
    pool = BrowserPool(max_browsers=1)
    await pool.start()
    order: list[str] = []
    try:

        async def task(name: str, hold: float) -> None:
            async with pool.acquire_context():
                order.append(f"{name}-enter")
                await asyncio.sleep(hold)
                order.append(f"{name}-exit")

        await asyncio.gather(task("a", 0.2), task("b", 0.05))
        # Second task cannot enter until first exits.
        assert order.index("a-exit") < order.index("b-enter")
    finally:
        await pool.stop()


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
async def test_acquire_without_start_raises() -> None:
    pool = BrowserPool(max_browsers=1)
    with pytest.raises(RuntimeError, match="not started"):
        async with pool.acquire_context():
            pass
