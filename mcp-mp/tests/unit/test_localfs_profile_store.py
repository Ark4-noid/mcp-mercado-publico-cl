from __future__ import annotations

from pathlib import Path

import pytest

from core.settings import Settings
from profile_store.factory import make_profile_store
from profile_store.localfs import LocalFSProfileStore


@pytest.mark.asyncio
async def test_get_returns_none_when_unset(local_profile: LocalFSProfileStore) -> None:
    assert await local_profile.get() is None


@pytest.mark.asyncio
async def test_save_and_get_roundtrip_unicode(local_profile: LocalFSProfileStore) -> None:
    payload = {
        "empresa": "Ñandú S.A.",
        "rut": "76.123.456-7",
        "email": "ventas@ñandu.cl",
        "nested": {"giro": "consultoría"},
    }
    await local_profile.save(payload)
    assert await local_profile.get() == payload


@pytest.mark.asyncio
async def test_delete_existing(local_profile: LocalFSProfileStore) -> None:
    await local_profile.save({"x": 1})
    await local_profile.delete()
    assert await local_profile.get() is None


@pytest.mark.asyncio
async def test_delete_missing_is_idempotent(local_profile: LocalFSProfileStore) -> None:
    # Should not raise.
    await local_profile.delete()
    await local_profile.delete()


@pytest.mark.asyncio
async def test_tenant_isolation(settings: Settings, tmp_local_root: Path) -> None:
    a = make_profile_store(settings, "tenant-a")
    b = make_profile_store(settings, "tenant-b")
    await a.save({"rut": "11.111.111-1"})
    assert await a.get() == {"rut": "11.111.111-1"}
    assert await b.get() is None
