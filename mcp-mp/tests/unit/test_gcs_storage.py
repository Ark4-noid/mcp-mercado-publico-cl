"""Unit tests for GCSStorage with mocked google-cloud-storage."""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest

from storage.gcs import GCSStorage
from storage.protocol import StorageKeyError, StorageNotFoundError


@pytest.fixture(autouse=True)
def reset_shared_client() -> Iterator[None]:
    GCSStorage._shared_client = None
    yield
    GCSStorage._shared_client = None


@pytest.fixture
def fake_blob() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fake_bucket(fake_blob: MagicMock) -> MagicMock:
    bucket = MagicMock()
    bucket.blob.return_value = fake_blob
    return bucket


@pytest.fixture
def fake_client(fake_bucket: MagicMock) -> MagicMock:
    client = MagicMock()
    client.bucket.return_value = fake_bucket
    return client


@pytest.fixture
def gcs(monkeypatch: pytest.MonkeyPatch, fake_client: MagicMock) -> GCSStorage:
    monkeypatch.setattr("storage.gcs.gcs_lib.Client", lambda: fake_client)
    return GCSStorage("test-bucket", "acme")


async def test_write_bytes_uploads(
    gcs: GCSStorage, fake_blob: MagicMock, fake_bucket: MagicMock
) -> None:
    await gcs.write_bytes("doc.pdf", b"hello")
    fake_bucket.blob.assert_called_with("tenants/acme/doc.pdf")
    fake_blob.upload_from_string.assert_called_once()


async def test_read_bytes_downloads(gcs: GCSStorage, fake_blob: MagicMock) -> None:
    fake_blob.download_as_bytes.return_value = b"hello"
    data = await gcs.read_bytes("doc.pdf")
    assert data == b"hello"


async def test_read_bytes_not_found(gcs: GCSStorage, fake_blob: MagicMock) -> None:
    from google.api_core import exceptions
    fake_blob.download_as_bytes.side_effect = exceptions.NotFound("missing")  # type: ignore[no-untyped-call]
    with pytest.raises(StorageNotFoundError):
        await gcs.read_bytes("missing.pdf")


async def test_exists(gcs: GCSStorage, fake_blob: MagicMock) -> None:
    fake_blob.exists.return_value = True
    assert await gcs.exists("doc.pdf") is True


async def test_path_traversal_rejected(gcs: GCSStorage) -> None:
    with pytest.raises(StorageKeyError):
        await gcs.write_bytes("../escape", b"x")


async def test_absolute_key_rejected(gcs: GCSStorage) -> None:
    with pytest.raises(StorageKeyError):
        await gcs.write_bytes("/abs", b"x")


async def test_list_strips_tenant_prefix(
    gcs: GCSStorage, fake_client: MagicMock, fake_bucket: MagicMock
) -> None:
    blob_a = MagicMock()
    blob_a.name = "tenants/acme/docs/a.pdf"
    blob_b = MagicMock()
    blob_b.name = "tenants/acme/docs/b.pdf"
    fake_client.list_blobs.return_value = [blob_a, blob_b]
    res = await gcs.list("docs/")
    assert res == ["docs/a.pdf", "docs/b.pdf"]


async def test_signed_url(gcs: GCSStorage, fake_blob: MagicMock) -> None:
    fake_blob.generate_signed_url.return_value = "https://signed.example/x"
    url = await gcs.signed_url("a.pdf", 60)
    assert url == "https://signed.example/x"
    fake_blob.generate_signed_url.assert_called_once()


async def test_delete_not_found(gcs: GCSStorage, fake_blob: MagicMock) -> None:
    from google.api_core import exceptions
    fake_blob.delete.side_effect = exceptions.NotFound("missing")  # type: ignore[no-untyped-call]
    with pytest.raises(StorageNotFoundError):
        await gcs.delete("missing.pdf")


async def test_tenant_isolation(
    monkeypatch: pytest.MonkeyPatch, fake_client: MagicMock, fake_bucket: MagicMock
) -> None:
    monkeypatch.setattr("storage.gcs.gcs_lib.Client", lambda: fake_client)
    a = GCSStorage("bucket", "acme")
    b = GCSStorage("bucket", "beta")
    await a.write_bytes("doc.pdf", b"a")
    await b.write_bytes("doc.pdf", b"b")
    calls: list[Any] = [c.args[0] for c in fake_bucket.blob.call_args_list]
    assert "tenants/acme/doc.pdf" in calls
    assert "tenants/beta/doc.pdf" in calls
