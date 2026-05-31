from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class Storage(Protocol):
    """Tenant-scoped object storage abstraction.

    Implementations are constructed with a tenant_id and resolve all keys
    under the tenant's own namespace - callers pass logical keys without
    tenant prefixes (e.g. 'ofertas/1234/cotizacion.xlsx').
    """

    async def read_bytes(self, key: str) -> bytes: ...
    async def write_bytes(self, key: str, data: bytes) -> None: ...
    async def read_text(self, key: str, encoding: str = "utf-8") -> str: ...
    async def write_text(self, key: str, data: str, encoding: str = "utf-8") -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def list(self, prefix: str) -> list[str]: ...
    async def delete(self, key: str) -> None: ...
    async def signed_url(self, key: str, ttl_seconds: int = 3600) -> str: ...


class StorageError(Exception):
    """Base exception for storage backends."""


class StorageNotFoundError(StorageError):
    """Raised when read/delete is called on a key that does not exist."""


class StorageKeyError(StorageError):
    """Raised when a key is malformed (path traversal, absolute, empty)."""
