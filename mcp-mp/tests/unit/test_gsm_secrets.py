"""Unit tests for GSMSecrets with mocked Secret Manager client."""
from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from secrets_provider.gsm import GSMSecrets
from secrets_provider.protocol import SecretNotFoundError


@pytest.fixture(autouse=True)
def reset_shared_client() -> Iterator[None]:
    GSMSecrets._shared_client = None
    yield
    GSMSecrets._shared_client = None


@pytest.fixture
def fake_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def secrets(
    monkeypatch: pytest.MonkeyPatch, fake_client: MagicMock
) -> tuple[GSMSecrets, MagicMock]:
    monkeypatch.setattr(
        "secrets_provider.gsm.secretmanager.SecretManagerServiceClient",
        lambda: fake_client,
    )
    return GSMSecrets("project-x", "acme"), fake_client


async def test_get_missing_returns_none(secrets: tuple[GSMSecrets, MagicMock]) -> None:
    s, client = secrets
    from google.api_core import exceptions
    client.access_secret_version.side_effect = exceptions.NotFound("missing")  # type: ignore[no-untyped-call]
    assert await s.get_secret("cookies") is None


async def test_get_returns_bytes(secrets: tuple[GSMSecrets, MagicMock]) -> None:
    s, client = secrets
    response = MagicMock()
    response.payload.data = b"sekret"
    client.access_secret_version.return_value = response
    assert await s.get_secret("cookies") == b"sekret"


async def test_set_secret_creates_and_adds_version(
    secrets: tuple[GSMSecrets, MagicMock],
) -> None:
    s, client = secrets
    await s.set_secret("cookies", b"abc")
    assert client.create_secret.called
    assert client.add_secret_version.called


async def test_set_secret_handles_existing_container(
    secrets: tuple[GSMSecrets, MagicMock],
) -> None:
    s, client = secrets
    from google.api_core import exceptions
    client.create_secret.side_effect = exceptions.AlreadyExists("already")  # type: ignore[no-untyped-call]
    await s.set_secret("cookies", b"abc")
    assert client.add_secret_version.called


async def test_delete_not_found(secrets: tuple[GSMSecrets, MagicMock]) -> None:
    s, client = secrets
    from google.api_core import exceptions
    client.delete_secret.side_effect = exceptions.NotFound("missing")  # type: ignore[no-untyped-call]
    with pytest.raises(SecretNotFoundError):
        await s.delete_secret("cookies")


async def test_tenant_id_in_secret_name(secrets: tuple[GSMSecrets, MagicMock]) -> None:
    s, client = secrets
    await s.set_secret("cookies", b"x")
    create_call = client.create_secret.call_args
    assert "acme" in create_call.kwargs["request"]["secret_id"]
