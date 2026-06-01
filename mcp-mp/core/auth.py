"""Google Identity ID-token verification.

Wraps `google.auth.transport.requests` + `google.oauth2.id_token` to validate
ID tokens signed by Google. The verifier is async-friendly (the underlying
HTTP call is offloaded to a thread because google-auth is sync) and caches
JWKS automatically inside the library.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

__all__ = [
    "AuthError",
    "TokenClaims",
    "extract_bearer_token",
    "id_token",
    "sub_to_tenant_id",
    "verify_google_id_token",
]

logger = logging.getLogger("mp.auth")


class AuthError(Exception):
    """Raised when an ID token fails validation."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Subset of the verified JWT we care about."""

    sub: str
    email: str | None
    audience: str


_BEARER_RE = re.compile(r"^Bearer\s+(?P<token>[\w\-\.]+)$", re.IGNORECASE)
_SAFE_SUB_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")


def extract_bearer_token(authorization_header: str | None) -> str:
    """Parse `Authorization: Bearer <jwt>`. Raises AuthError if malformed."""
    if not authorization_header:
        raise AuthError("Missing Authorization header")
    m = _BEARER_RE.match(authorization_header.strip())
    if not m:
        raise AuthError("Malformed Authorization header (expected Bearer)")
    return m.group("token")


_request = google_requests.Request()


def _verify_sync(token: str, audience: str) -> dict[str, Any]:
    """Blocking JWT verification - call only via run_in_executor."""
    try:
        payload: dict[str, Any] = id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            token, _request, audience
        )
        return payload
    except ValueError as exc:
        # google-auth wraps everything in ValueError. Tag it for our middleware.
        raise AuthError(str(exc)) from exc


async def verify_google_id_token(token: str, audience: str) -> TokenClaims:
    """Verify a Google-signed JWT and return the claims we use."""
    loop = asyncio.get_running_loop()
    payload = await loop.run_in_executor(None, _verify_sync, token, audience)

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise AuthError("Token has no usable sub claim")

    aud = payload.get("aud")
    if isinstance(aud, list):
        if audience not in aud:
            raise AuthError("Token audience does not match")
    elif aud != audience:
        raise AuthError("Token audience does not match")

    email = payload.get("email")
    return TokenClaims(
        sub=sub,
        email=email if isinstance(email, str) else None,
        audience=audience,
    )


def sub_to_tenant_id(sub: str) -> str:
    """Map a Google sub (numeric string) to our tenant_id format.

    Google sub is always digits - that already matches our regex.
    For safety we still validate and lowercase.
    """
    candidate = sub.strip().lower()
    if not _SAFE_SUB_RE.fullmatch(candidate):
        raise AuthError(f"sub {sub!r} cannot be used as tenant_id")
    return candidate
