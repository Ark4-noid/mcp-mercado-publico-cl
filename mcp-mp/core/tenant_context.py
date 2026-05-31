from __future__ import annotations

import re
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from profile_store.protocol import ProfileStore
    from secrets_provider.protocol import SecretsProvider
    from storage.protocol import Storage


TENANT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


class TenantIdError(ValueError):
    """Raised when a tenant_id does not match the allowed format."""


def validate_tenant_id(tenant_id: str) -> None:
    """Raise TenantIdError if tenant_id is invalid.

    Format: DNS-safe lowercase, 3-64 chars, no leading/trailing hyphen.
    """
    if not isinstance(tenant_id, str) or not TENANT_ID_RE.fullmatch(tenant_id):
        raise TenantIdError(
            f"Invalid tenant_id: {tenant_id!r}. Must match {TENANT_ID_RE.pattern}"
        )


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Per-request context carrying tenant-scoped resources.

    Created by the ASGI middleware (HTTP) or by run_stdio.py (stdio).
    Accessed via current_tenant() inside tool handlers.
    """

    tenant_id: str
    storage: Storage
    secrets: SecretsProvider
    profile_store: ProfileStore

    def __post_init__(self) -> None:
        validate_tenant_id(self.tenant_id)


_current_tenant: ContextVar[TenantContext] = ContextVar("_current_tenant")


def current_tenant() -> TenantContext:
    """Return the TenantContext for the current request.

    Raises LookupError if no context has been set - usually a bug in the
    middleware (HTTP) or bootstrap (stdio).
    """
    try:
        return _current_tenant.get()
    except LookupError as exc:
        raise LookupError(
            "No TenantContext is set. The middleware (HTTP) or "
            "run_stdio.py bootstrap must set one before tool calls."
        ) from exc


def set_current_tenant(ctx: TenantContext) -> Token[TenantContext]:
    """Set the current TenantContext, returning a Token for reset."""
    return _current_tenant.set(ctx)


def reset_current_tenant(token: Token[TenantContext]) -> None:
    """Restore the previous TenantContext (used by middleware on exit)."""
    _current_tenant.reset(token)
