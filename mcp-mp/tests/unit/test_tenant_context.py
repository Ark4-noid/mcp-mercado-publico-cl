from __future__ import annotations

import asyncio
import contextvars
from unittest.mock import MagicMock

import pytest

from core.tenant_context import (
    TenantContext,
    TenantIdError,
    current_tenant,
    reset_current_tenant,
    set_current_tenant,
    validate_tenant_id,
)


def _make_ctx(tenant_id: str = "acme") -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        storage=MagicMock(),
        secrets=MagicMock(),
        profile_store=MagicMock(),
    )


@pytest.mark.parametrize(
    "tid",
    ["acme", "abc-123", "t1a", "tenant-acme-prod-east-2025"],
)
def test_validate_tenant_id_valid(tid: str) -> None:
    validate_tenant_id(tid)


@pytest.mark.parametrize(
    "tid",
    [
        "",
        "ACME",
        "with_underscore",
        "-leading-hyphen",
        "trailing-hyphen-",
        "a" * 65,
        "ab",
    ],
)
def test_validate_tenant_id_invalid(tid: str) -> None:
    with pytest.raises(TenantIdError):
        validate_tenant_id(tid)


def test_current_tenant_unset_raises() -> None:
    def _inner() -> None:
        with pytest.raises(LookupError, match="No TenantContext"):
            current_tenant()

    ctx = contextvars.copy_context()
    ctx.run(_inner)


def test_set_get_reset_roundtrip() -> None:
    ctx = _make_ctx("acme")
    token = set_current_tenant(ctx)
    try:
        got = current_tenant()
        assert got is ctx
        assert got.tenant_id == "acme"
    finally:
        reset_current_tenant(token)
    with pytest.raises(LookupError):
        current_tenant()


def test_tenant_context_validates_on_init() -> None:
    with pytest.raises(TenantIdError):
        TenantContext(
            tenant_id="INVALID",
            storage=MagicMock(),
            secrets=MagicMock(),
            profile_store=MagicMock(),
        )


def test_contextvar_isolation_between_tasks() -> None:
    """Each asyncio task gets its own ContextVar copy when spawned with create_task."""
    outer_ctx = _make_ctx("outer-tenant")
    seen: dict[str, str | None] = {}

    async def child_reads() -> None:
        try:
            seen["child"] = current_tenant().tenant_id
        except LookupError:
            seen["child"] = None

    async def child_overrides() -> None:
        inner = _make_ctx("inner-tenant")
        tok = set_current_tenant(inner)
        try:
            seen["override"] = current_tenant().tenant_id
        finally:
            reset_current_tenant(tok)

    async def main() -> None:
        token = set_current_tenant(outer_ctx)
        try:
            # Task inherits a COPY of the current context at creation time.
            await asyncio.create_task(child_reads())
            await asyncio.create_task(child_overrides())
            # Override in child task must not leak into parent.
            seen["parent_after"] = current_tenant().tenant_id
        finally:
            reset_current_tenant(token)

    asyncio.run(main())

    assert seen["child"] == "outer-tenant"
    assert seen["override"] == "inner-tenant"
    assert seen["parent_after"] == "outer-tenant"
