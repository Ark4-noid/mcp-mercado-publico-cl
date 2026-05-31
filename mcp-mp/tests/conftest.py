"""Shared fixtures for the multi-tenant test suite.

These fixtures are intentionally minimal in Chunk 1 - backend fixtures
(local_storage, local_secrets, local_profile, tenant_ctx) land in Chunk 2
once their implementations exist.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from core.settings import Settings, reset_settings_cache
from core.tenant_context import (
    TenantContext,
    reset_current_tenant,
    set_current_tenant,
)
from profile_store.factory import make_profile_store
from secrets_provider.factory import make_secrets
from storage.factory import make_storage


@pytest.fixture
def tmp_local_root(tmp_path: Path) -> Path:
    """An isolated ~/.mp-mcp replacement for the test."""
    root = tmp_path / "mp-mcp"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def settings(tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    """A Settings instance with local_root pointing at the per-test tmp dir.

    Any MP_* env var set by the test runner is cleared to avoid leaking
    real config into unit tests.
    """
    for key in list(os.environ):
        if key.startswith("MP_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    reset_settings_cache()
    s = Settings()
    s.validate_runtime()
    yield s
    reset_settings_cache()


@pytest.fixture
def local_storage(settings: Settings, tmp_local_root: Path) -> object:
    return make_storage(settings, tenant_id="acme")


@pytest.fixture
def local_secrets(settings: Settings, tmp_local_root: Path) -> object:
    return make_secrets(settings, tenant_id="acme")


@pytest.fixture
def local_profile(settings: Settings, tmp_local_root: Path) -> object:
    return make_profile_store(settings, tenant_id="acme")


@pytest.fixture
def tenant_ctx(settings: Settings, tmp_local_root: Path) -> Iterator[TenantContext]:
    """A TenantContext with tenant_id='acme' wired to local backends.

    Yields the context and automatically resets the ContextVar on teardown.
    """
    ctx = TenantContext(
        tenant_id="acme",
        storage=make_storage(settings, "acme"),
        secrets=make_secrets(settings, "acme"),
        profile_store=make_profile_store(settings, "acme"),
    )
    token = set_current_tenant(ctx)
    try:
        yield ctx
    finally:
        reset_current_tenant(token)
