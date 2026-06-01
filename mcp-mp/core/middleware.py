from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from core.auth import (
    AuthError,
    extract_bearer_token,
    sub_to_tenant_id,
    verify_google_id_token,
)
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
AUTHORIZATION_HEADER = b"authorization"

# Paths that bypass tenant resolution (health probes, etc.).
EXEMPT_PATHS: frozenset[str] = frozenset({"/health"})


class _Reject(Exception):
    """Internal sentinel to short-circuit auth resolution with an HTTP error."""

    def __init__(
        self,
        status: int,
        message: str,
        headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        self.status = status
        self.message = message
        self.headers = headers
        super().__init__(message)


class TenantContextMiddleware:
    """ASGI middleware that resolves and installs the per-request TenantContext.

    Resolves tenant_id according to settings.auth_provider:
      - "header": from X-Tenant-Id (dev/local).
      - "google": from Authorization Bearer <Google ID token>, validating
                  audience against settings.oauth_audience and using the
                  `sub` claim as tenant_id.

    On the http scope, missing/invalid credentials return 401 (google) or
    400 (header). /health bypasses auth for Cloud Run probes.
    """

    def __init__(self, app: "ASGIApp", *, settings: Settings) -> None:
        self._app = app
        self._settings = settings

    async def __call__(
        self, scope: "Scope", receive: "Receive", send: "Send"
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        if scope.get("path") in EXEMPT_PATHS:
            await self._app(scope, receive, send)
            return

        headers: list[tuple[bytes, bytes]] = scope.get("headers", [])

        try:
            if self._settings.auth_provider == "google":
                tenant_id = await self._resolve_google(headers)
            else:
                tenant_id = self._resolve_header(headers)
        except _Reject as r:
            await self._respond(send, r.status, r.message, r.headers)
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

    def _resolve_header(self, headers: list[tuple[bytes, bytes]]) -> str:
        raw = next((v for k, v in headers if k.lower() == TENANT_HEADER), None)
        if raw is None:
            raise _Reject(400, "Missing X-Tenant-Id header")
        try:
            tenant_id = raw.decode("ascii").strip().lower()
            validate_tenant_id(tenant_id)
        except (UnicodeDecodeError, TenantIdError) as exc:
            raise _Reject(400, f"Invalid X-Tenant-Id: {exc}") from exc
        return tenant_id

    async def _resolve_google(self, headers: list[tuple[bytes, bytes]]) -> str:
        raw = next(
            (v for k, v in headers if k.lower() == AUTHORIZATION_HEADER), None
        )
        try:
            token = extract_bearer_token(raw.decode("ascii") if raw else None)
            audience = self._settings.oauth_audience
            assert audience, "oauth_audience required (validate_runtime should catch this)"
            claims = await verify_google_id_token(token, audience)
            return sub_to_tenant_id(claims.sub)
        except (UnicodeDecodeError, AuthError) as exc:
            # Per RFC 6750.
            challenge = (
                f'Bearer realm="mcp", error="invalid_token", '
                f'error_description="{exc}"'
            )
            raise _Reject(
                401,
                f"invalid_token: {exc}",
                headers=[(b"www-authenticate", challenge.encode("utf-8"))],
            ) from exc

    @staticmethod
    async def _respond(
        send: "Send",
        status: int,
        message: str,
        extra_headers: list[tuple[bytes, bytes]] | None = None,
    ) -> None:
        body = f'{{"error":"{message}"}}'.encode("utf-8")
        h: list[tuple[bytes, bytes]] = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode("ascii")),
        ]
        if extra_headers:
            h.extend(extra_headers)
        await send(
            {"type": "http.response.start", "status": status, "headers": h}
        )
        await send({"type": "http.response.body", "body": body})
