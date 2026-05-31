from __future__ import annotations

from pathlib import Path

import pytest

from core.settings import Settings
from profile_store.factory import make_profile_store
from profile_store.localfs import LocalFSProfileStore
from secrets_provider.factory import make_secrets
from secrets_provider.localfs import LocalFSSecrets
from storage.factory import make_storage
from storage.gcs import GCSStorage
from storage.localfs import LocalFSStorage


def test_make_storage_localfs(settings: Settings) -> None:
    s = make_storage(settings, "acme")
    assert isinstance(s, LocalFSStorage)


def test_make_storage_gcs_without_bucket_raises(tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    monkeypatch.delenv("MP_GCS_BUCKET", raising=False)
    s = Settings()
    with pytest.raises(ValueError, match="MP_GCS_BUCKET"):
        make_storage(s, "acme")


def test_make_storage_gcs_with_bucket(tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("MP_GCS_BUCKET", "my-bucket")
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    s = Settings()
    backend = make_storage(s, "acme")
    assert isinstance(backend, GCSStorage)


@pytest.mark.asyncio
async def test_gcs_stub_raises_not_implemented(tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MP_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("MP_GCS_BUCKET", "my-bucket")
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    s = Settings()
    backend = make_storage(s, "acme")
    with pytest.raises(NotImplementedError, match="Sprint 3"):
        await backend.read_bytes("k")
    with pytest.raises(NotImplementedError):
        await backend.write_bytes("k", b"x")
    with pytest.raises(NotImplementedError):
        await backend.read_text("k")
    with pytest.raises(NotImplementedError):
        await backend.write_text("k", "x")
    with pytest.raises(NotImplementedError):
        await backend.exists("k")
    with pytest.raises(NotImplementedError):
        await backend.list("")
    with pytest.raises(NotImplementedError):
        await backend.delete("k")
    with pytest.raises(NotImplementedError):
        await backend.signed_url("k")


def test_make_secrets_localfs(settings: Settings) -> None:
    s = make_secrets(settings, "acme")
    assert isinstance(s, LocalFSSecrets)


def test_make_profile_store_localfs(settings: Settings) -> None:
    p = make_profile_store(settings, "acme")
    assert isinstance(p, LocalFSProfileStore)
