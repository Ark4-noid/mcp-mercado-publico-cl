from __future__ import annotations

from pathlib import Path

import pytest

from core.settings import Settings
from secrets_provider.factory import make_secrets
from secrets_provider.localfs import LocalFSSecrets
from secrets_provider.protocol import SecretNameError, SecretNotFoundError


@pytest.mark.asyncio
async def test_roundtrip(local_secrets: LocalFSSecrets) -> None:
    await local_secrets.set_secret("api-token", b"shhh-secret")
    assert await local_secrets.get_secret("api-token") == b"shhh-secret"


@pytest.mark.asyncio
async def test_get_missing_returns_none(local_secrets: LocalFSSecrets) -> None:
    assert await local_secrets.get_secret("does-not-exist") is None


@pytest.mark.asyncio
async def test_delete_missing_raises(local_secrets: LocalFSSecrets) -> None:
    with pytest.raises(SecretNotFoundError):
        await local_secrets.delete_secret("missing")


@pytest.mark.asyncio
async def test_delete_existing(local_secrets: LocalFSSecrets) -> None:
    await local_secrets.set_secret("burn", b"x")
    await local_secrets.delete_secret("burn")
    assert await local_secrets.get_secret("burn") is None


@pytest.mark.parametrize("bad", ["UPPER", "with space", "with/slash", "", "a" * 65])
@pytest.mark.asyncio
async def test_invalid_names_rejected(local_secrets: LocalFSSecrets, bad: str) -> None:
    with pytest.raises(SecretNameError):
        await local_secrets.set_secret(bad, b"x")


@pytest.mark.asyncio
async def test_tenant_isolation(settings: Settings, tmp_local_root: Path) -> None:
    a = make_secrets(settings, "tenant-a")
    b = make_secrets(settings, "tenant-b")
    await a.set_secret("token", b"a-only")
    assert await a.get_secret("token") == b"a-only"
    assert await b.get_secret("token") is None
