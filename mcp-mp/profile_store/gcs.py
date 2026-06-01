"""GCS-backed ProfileStore.

The profile is a JSON object stored at `tenants/<tenant_id>/profile.json`.
Uses the same bucket as Storage so we only need one GCS resource per
project. The internal layer reuses GCSStorage to avoid duplicate client
plumbing.
"""
from __future__ import annotations

import json
from typing import Any

from storage.gcs import GCSStorage
from storage.protocol import StorageNotFoundError


class GCSProfileStore:
    def __init__(self, bucket_name: str, tenant_id: str, kms_key: str | None = None) -> None:
        self._storage = GCSStorage(bucket_name, tenant_id, kms_key)
        self._key = "profile.json"

    async def get(self) -> dict[str, Any] | None:
        try:
            data = await self._storage.read_bytes(self._key)
        except StorageNotFoundError:
            return None
        result: dict[str, Any] = json.loads(data.decode("utf-8"))
        return result

    async def save(self, profile: dict[str, Any]) -> None:
        payload = json.dumps(profile, ensure_ascii=False, indent=2).encode("utf-8")
        await self._storage.write_bytes(self._key, payload)

    async def delete(self) -> None:
        try:
            await self._storage.delete(self._key)
        except StorageNotFoundError:
            return
