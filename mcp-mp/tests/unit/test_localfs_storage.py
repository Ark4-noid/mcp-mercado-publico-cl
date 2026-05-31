from __future__ import annotations

from pathlib import Path

import pytest

from core.settings import Settings
from storage.factory import make_storage
from storage.localfs import LocalFSStorage
from storage.protocol import StorageKeyError, StorageNotFoundError


@pytest.mark.asyncio
async def test_roundtrip_bytes(local_storage: LocalFSStorage) -> None:
    await local_storage.write_bytes("ofertas/1234/cot.xlsx", b"\x00\x01binary")
    assert await local_storage.read_bytes("ofertas/1234/cot.xlsx") == b"\x00\x01binary"


@pytest.mark.asyncio
async def test_roundtrip_text(local_storage: LocalFSStorage) -> None:
    await local_storage.write_text("notes/hola.txt", "ñandú áéíóú")
    assert await local_storage.read_text("notes/hola.txt") == "ñandú áéíóú"


@pytest.mark.asyncio
async def test_exists(local_storage: LocalFSStorage) -> None:
    assert await local_storage.exists("nope.txt") is False
    await local_storage.write_bytes("yes.txt", b"x")
    assert await local_storage.exists("yes.txt") is True


@pytest.mark.asyncio
async def test_delete_existing(local_storage: LocalFSStorage) -> None:
    await local_storage.write_bytes("gone.txt", b"x")
    await local_storage.delete("gone.txt")
    assert await local_storage.exists("gone.txt") is False


@pytest.mark.asyncio
async def test_delete_missing_raises(local_storage: LocalFSStorage) -> None:
    with pytest.raises(StorageNotFoundError):
        await local_storage.delete("missing.txt")


@pytest.mark.asyncio
async def test_read_missing_raises(local_storage: LocalFSStorage) -> None:
    with pytest.raises(StorageNotFoundError):
        await local_storage.read_bytes("missing.txt")


@pytest.mark.asyncio
async def test_list_empty_prefix_lists_all(local_storage: LocalFSStorage) -> None:
    await local_storage.write_bytes("a/x.txt", b"a")
    await local_storage.write_bytes("b/y.txt", b"b")
    items = await local_storage.list("")
    assert "a/x.txt" in items
    assert "b/y.txt" in items


@pytest.mark.asyncio
async def test_list_subprefix(local_storage: LocalFSStorage) -> None:
    await local_storage.write_bytes("a/x.txt", b"a")
    await local_storage.write_bytes("b/y.txt", b"b")
    items = await local_storage.list("a")
    assert items == ["a/x.txt"]


@pytest.mark.asyncio
async def test_list_nonexistent_prefix(local_storage: LocalFSStorage) -> None:
    assert await local_storage.list("nope") == []


@pytest.mark.asyncio
async def test_list_on_file_returns_file(local_storage: LocalFSStorage) -> None:
    await local_storage.write_bytes("single.txt", b"x")
    items = await local_storage.list("single.txt")
    assert items == ["single.txt"]


@pytest.mark.asyncio
async def test_path_traversal_rejected(local_storage: LocalFSStorage) -> None:
    with pytest.raises(StorageKeyError):
        await local_storage.write_bytes("../escape.txt", b"x")


@pytest.mark.asyncio
async def test_empty_key_rejected(local_storage: LocalFSStorage) -> None:
    with pytest.raises(StorageKeyError):
        await local_storage.write_bytes("", b"x")


@pytest.mark.asyncio
async def test_absolute_unix_key_rejected(local_storage: LocalFSStorage) -> None:
    with pytest.raises(StorageKeyError):
        await local_storage.write_bytes("/abs", b"x")


@pytest.mark.asyncio
async def test_absolute_windows_key_rejected(local_storage: LocalFSStorage) -> None:
    with pytest.raises(StorageKeyError):
        await local_storage.write_bytes("\\abs", b"x")


@pytest.mark.asyncio
async def test_signed_url_returns_file_uri(local_storage: LocalFSStorage) -> None:
    await local_storage.write_bytes("doc.txt", b"x")
    url = await local_storage.signed_url("doc.txt")
    assert url.startswith("file:")


@pytest.mark.asyncio
async def test_tenant_isolation(settings: Settings, tmp_local_root: Path) -> None:
    a = make_storage(settings, "tenant-a")
    b = make_storage(settings, "tenant-b")
    await a.write_bytes("shared.txt", b"only-a")
    assert await a.exists("shared.txt") is True
    assert await b.exists("shared.txt") is False
