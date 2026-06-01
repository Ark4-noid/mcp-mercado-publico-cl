"""Unit tests for GCSProfileStore - backed by GCSStorage internally."""
from __future__ import annotations

import json
from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from profile_store.gcs import GCSProfileStore
from storage.protocol import StorageNotFoundError


@pytest.fixture
def fake_storage() -> MagicMock:
    s = MagicMock()
    s.read_bytes = AsyncMock()
    s.write_bytes = AsyncMock()
    s.delete = AsyncMock()
    return s


@pytest.fixture
def store(fake_storage: MagicMock) -> Iterator[tuple[GCSProfileStore, MagicMock]]:
    with patch("profile_store.gcs.GCSStorage", return_value=fake_storage):
        yield GCSProfileStore("bucket", "acme"), fake_storage


async def test_get_missing_returns_none(
    store: tuple[GCSProfileStore, MagicMock],
) -> None:
    s, fake = store
    fake.read_bytes.side_effect = StorageNotFoundError("profile.json")
    assert await s.get() is None


async def test_get_returns_dict(store: tuple[GCSProfileStore, MagicMock]) -> None:
    s, fake = store
    fake.read_bytes.return_value = b'{"empresa":"ACME"}'
    assert await s.get() == {"empresa": "ACME"}


async def test_save_writes_json(store: tuple[GCSProfileStore, MagicMock]) -> None:
    s, fake = store
    await s.save({"empresa": "ACME", "n": "ok"})
    fake.write_bytes.assert_awaited_once()
    args = fake.write_bytes.await_args.args
    assert args[0] == "profile.json"
    assert json.loads(args[1].decode("utf-8")) == {"empresa": "ACME", "n": "ok"}


async def test_delete_idempotent(store: tuple[GCSProfileStore, MagicMock]) -> None:
    s, fake = store
    fake.delete.side_effect = StorageNotFoundError("profile.json")
    await s.delete()  # should not raise
