from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.settings import Settings
from core.tenant_context import (
    TenantContext,
    TenantIdError,
    reset_current_tenant,
    set_current_tenant,
    validate_tenant_id,
)
from profile_store.factory import make_profile_store
from secrets_provider.factory import make_secrets
from storage.factory import make_storage

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


logger = logging.getLogger("mp.middleware")

TENANT_HEADER = b"x-tenant-id"

# Paths that bypass tenant resolution (health probes, etc.).
EXEMPT_PATHS: frozenset[str] = frozenset({"/health"})


class TenantContextMiddleware:
    """ASGI middleware that resolves and installs the per-request TenantContext.

    The middleware:
      1. Reads the X-Tenant-Id header (case-insensitive).
      2. Validates the tenant_id format with the shared regex.
      3. Builds Storage/Secrets/ProfileStore for that tenant via factories.
      4. Sets the ContextVar before delegating to the downstream app.
      5. Resets the ContextVar on the way out.

    On HTTP, a missing or invalid X-Tenant-Id returns 400. On other ASGI
    types (lifespan, websocket) the middleware is a pass-through.
    """

    def __init__(self, app: "ASGIApp", *, settings: Settings) -> None:
        self._app = app
        self._settings = settings

    async def __call__(self, scope: "Scope", receive: "Receive", send: "Send") -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if scope.get("path") in EXEMPT_PATHS:
            await self._app(scope, receive, send)
            return

        headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
        raw = next((v for k, v in headers if k.lower() == TENANT_HEADER), None)

        if raw is None:
            await self._reject(send, 400, "Missing X-Tenant-Id header")
            return

        try:
            tenant_id = raw.decode("ascii").strip().lower()
            validate_tenant_id(tenant_id)
        except (UnicodeDecodeError, TenantIdError) as exc:
            await self._reject(send, 400, f"Invalid X-Tenant-Id: {exc}")
            return

        ctx = TenantContext(
            tenant_id=tenant_id,
            storage=make_storage(self._settings, tenant_id),
            secrets=make_secrets(self._settings, tenant_id),
            profile_store=make_profile_store(self._settings, tenant_id),
        )

        token = set_current_tenant(ctx)
        try:
            await self._app(scope, receive, send)
        finally:
            reset_current_tenant(token)

    @staticmethod
    async def _reject(send: "Send", status: int, message: str) -> None:
        body = f'{{"error":"{message}"}}'.encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        })
        await send({"type": "http.response.body", "body": body})
