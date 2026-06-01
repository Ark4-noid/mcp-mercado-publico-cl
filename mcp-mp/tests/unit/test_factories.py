from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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


def test_make_storage_gcs_with_bucket(
    tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MP_STORAGE_BACKEND", "gcs")
    monkeypatch.setenv("MP_GCS_BUCKET", "my-bucket")
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    # Prevent real GCS client construction.
    monkeypatch.setattr("storage.gcs.gcs_lib.Client", lambda: MagicMock())
    GCSStorage._shared_client = None
    s = Settings()
    backend = make_storage(s, "acme")
    assert isinstance(backend, GCSStorage)
    GCSStorage._shared_client = None


def test_make_secrets_localfs(settings: Settings) -> None:
    s = make_secrets(settings, "acme")
    assert isinstance(s, LocalFSSecrets)


def test_make_secrets_gsm_without_project_raises(
    tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MP_SECRETS_BACKEND", "gsm")
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    monkeypatch.delenv("MP_GCP_PROJECT", raising=False)
    s = Settings()
    with pytest.raises(ValueError, match="MP_GCP_PROJECT"):
        make_secrets(s, "acme")


def test_make_secrets_gsm_with_project(
    tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MP_SECRETS_BACKEND", "gsm")
    monkeypatch.setenv("MP_GCP_PROJECT", "test-project")
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    monkeypatch.setattr(
        "secrets_provider.gsm.secretmanager.SecretManagerServiceClient",
        lambda: MagicMock(),
    )
    from secrets_provider.gsm import GSMSecrets
    GSMSecrets._shared_client = None
    s = Settings()
    backend = make_secrets(s, "acme")
    assert isinstance(backend, GSMSecrets)
    GSMSecrets._shared_client = None


def test_make_profile_store_localfs(settings: Settings) -> None:
    p = make_profile_store(settings, "acme")
    assert isinstance(p, LocalFSProfileStore)


def test_make_profile_store_gcs_without_bucket_raises(
    tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MP_PROFILE_BACKEND", "gcs")
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    monkeypatch.delenv("MP_GCS_BUCKET", raising=False)
    s = Settings()
    with pytest.raises(ValueError, match="MP_GCS_BUCKET"):
        make_profile_store(s, "acme")


def test_make_profile_store_gcs_with_bucket(
    tmp_local_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MP_PROFILE_BACKEND", "gcs")
    monkeypatch.setenv("MP_GCS_BUCKET", "my-bucket")
    monkeypatch.setenv("MP_LOCAL_ROOT", str(tmp_local_root))
    monkeypatch.setattr("storage.gcs.gcs_lib.Client", lambda: MagicMock())
    GCSStorage._shared_client = None
    from profile_store.gcs import GCSProfileStore
    s = Settings()
    backend = make_profile_store(s, "acme")
    assert isinstance(backend, GCSProfileStore)
    GCSStorage._shared_client = None
