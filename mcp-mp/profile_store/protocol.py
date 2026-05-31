from __future__ import annotations
from typing import Any, Protocol, runtime_checkable


class ProfileStoreError(Exception):
    pass


@runtime_checkable
class ProfileStore(Protocol):
    """Tenant-scoped profile storage.

    The profile is an opaque dict: in Sprint 1 it holds empresa/rut/email/etc.
    The schema is validated at the application layer, not here.
    """

    async def get(self) -> dict[str, Any] | None: ...
    async def save(self, profile: dict[str, Any]) -> None: ...
    async def delete(self) -> None: ...
