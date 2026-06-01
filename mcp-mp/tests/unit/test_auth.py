"""Unit tests for core.auth - bearer parsing, sub mapping, JWT verification."""
from __future__ import annotations

from typing import Any

import pytest

from core import auth as auth_module
from core.auth import (
    AuthError,
    TokenClaims,
    extract_bearer_token,
    sub_to_tenant_id,
    verify_google_id_token,
)


# ---------- extract_bearer_token ----------


def test_extract_bearer_token_valid() -> None:
    assert extract_bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"


def test_extract_bearer_token_case_insensitive() -> None:
    assert extract_bearer_token("bearer abc.def.ghi") == "abc.def.ghi"


def test_extract_bearer_token_invalid_scheme() -> None:
    with pytest.raises(AuthError, match="Malformed"):
        extract_bearer_token("Basic xxx")


def test_extract_bearer_token_missing() -> None:
    with pytest.raises(AuthError, match="Missing"):
        extract_bearer_token(None)


def test_extract_bearer_token_empty() -> None:
    with pytest.raises(AuthError, match="Missing"):
        extract_bearer_token("")


# ---------- sub_to_tenant_id ----------


def test_sub_to_tenant_id_numeric() -> None:
    assert sub_to_tenant_id("108451823765400000000") == "108451823765400000000"


def test_sub_to_tenant_id_invalid_chars() -> None:
    with pytest.raises(AuthError, match="cannot be used"):
        sub_to_tenant_id("ABC@something")


def test_sub_to_tenant_id_too_short() -> None:
    with pytest.raises(AuthError):
        sub_to_tenant_id("ab")


# ---------- verify_google_id_token ----------


@pytest.mark.asyncio
async def test_verify_google_id_token_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_verify(
        token: str, request: Any, audience: str
    ) -> dict[str, Any]:
        return {"sub": "123456789012", "aud": "https://test", "email": "u@x.cl"}

    monkeypatch.setattr(
        auth_module.id_token, "verify_oauth2_token", fake_verify
    )
    claims = await verify_google_id_token("tkn", "https://test")
    assert claims == TokenClaims(
        sub="123456789012", email="u@x.cl", audience="https://test"
    )


@pytest.mark.asyncio
async def test_verify_audience_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_verify(
        token: str, request: Any, audience: str
    ) -> dict[str, Any]:
        return {"sub": "123", "aud": "other"}

    monkeypatch.setattr(
        auth_module.id_token, "verify_oauth2_token", fake_verify
    )
    with pytest.raises(AuthError, match="audience"):
        await verify_google_id_token("tkn", "https://test")


@pytest.mark.asyncio
async def test_verify_aud_list_match(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_verify(
        token: str, request: Any, audience: str
    ) -> dict[str, Any]:
        return {"sub": "123456789012", "aud": ["other", "https://test"]}

    monkeypatch.setattr(
        auth_module.id_token, "verify_oauth2_token", fake_verify
    )
    claims = await verify_google_id_token("tkn", "https://test")
    assert claims.sub == "123456789012"


@pytest.mark.asyncio
async def test_verify_aud_list_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_verify(
        token: str, request: Any, audience: str
    ) -> dict[str, Any]:
        return {"sub": "123", "aud": ["a", "b"]}

    monkeypatch.setattr(
        auth_module.id_token, "verify_oauth2_token", fake_verify
    )
    with pytest.raises(AuthError, match="audience"):
        await verify_google_id_token("tkn", "https://test")


@pytest.mark.asyncio
async def test_verify_no_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_verify(
        token: str, request: Any, audience: str
    ) -> dict[str, Any]:
        return {"aud": "https://test"}

    monkeypatch.setattr(
        auth_module.id_token, "verify_oauth2_token", fake_verify
    )
    with pytest.raises(AuthError, match="sub"):
        await verify_google_id_token("tkn", "https://test")


@pytest.mark.asyncio
async def test_verify_underlying_value_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_verify(
        token: str, request: Any, audience: str
    ) -> dict[str, Any]:
        raise ValueError("expired token")

    monkeypatch.setattr(
        auth_module.id_token, "verify_oauth2_token", fake_verify
    )
    with pytest.raises(AuthError, match="expired"):
        await verify_google_id_token("tkn", "https://test")
