from __future__ import annotations
import re
from typing import Protocol, runtime_checkable


SECRET_NAME_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


class SecretsError(Exception):
    pass


class SecretNotFoundError(SecretsError):
    pass


class SecretNameError(SecretsError):
    pass


def validate_secret_name(name: str) -> None:
    if not isinstance(name, str) or not SECRET_NAME_RE.fullmatch(name):
        raise SecretNameError(f"Invalid secret name: {name!r}. Must match {SECRET_NAME_RE.pattern}")


@runtime_checkable
class SecretsProvider(Protocol):
    """Tenant-scoped secrets store.

    Sprint 1: plain JSON on local disk. Sprint 3: Google Secret Manager.
    Values are arbitrary bytes (cookies as JSON-encoded blobs, ChileCompra
    ticket as utf-8 bytes, etc.). Implementations are responsible for
    isolating per-tenant access at construction time.
    """

    async def get_secret(self, name: str) -> bytes | None: ...
    async def set_secret(self, name: str, value: bytes) -> None: ...
    async def delete_secret(self, name: str) -> None: ...
