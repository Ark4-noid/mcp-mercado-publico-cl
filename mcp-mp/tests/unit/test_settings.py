from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.settings import Settings, get_settings, reset_settings_cache


@pytest.fixture(autouse=True)
def _clear_mp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip any MP_* env vars before each test for isolation."""
    for key in list(os.environ):
        if key.startswith("MP_"):
            monkeypatch.delenv(key, raising=False)
    reset_settings_cache()


def test_defaults_load() -> None:
    s = Settings()
    assert s.storage_backend == "localfs"
    assert s.secrets_backend == "localfs"
    assert s.profile_backend == "localfs"
    assert s.tenant_mode == "legacy"
    assert s.max_browsers == 2
    assert s.local_root == Path.home() / ".mp-mcp"
    assert s.gcs_bucket is None
    assert s.legacy_ticket_env == "MERCADO_PUBLICO_TICKET"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("MP_GCS_BUCKET", "mybucket")
    s = Settings()
    s.validate_runtime()
    assert s.storage_backend == "gcs"
    assert s.gcs_bucket == "mybucket"


def test_gcs_without_bucket_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_STORAGE_BACKEND", "gcs")
    s = Settings()
    with pytest.raises(ValueError, match="MP_GCS_BUCKET"):
        s.validate_runtime()


def test_max_browsers_lower_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_MAX_BROWSERS", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_max_browsers_upper_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_MAX_BROWSERS", "11")
    with pytest.raises(ValidationError):
        Settings()


def test_get_settings_cached() -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_reset_settings_cache() -> None:
    s1 = get_settings()
    reset_settings_cache()
    s2 = get_settings()
    assert s1 is not s2
