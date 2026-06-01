"""Google Cloud Storage backend for the Storage protocol.

All keys are stored under `tenants/<tenant_id>/<key>` so a single bucket can
host many tenants. The GCS client is reused across calls (thread-safe per the
google-cloud-storage docs); blocking GCS operations are offloaded to a
thread executor via asyncio.

This backend is used in production (Cloud Run). For dev/local, see
LocalFSStorage.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from google.cloud import storage as gcs_lib  # type: ignore[attr-defined]

from .protocol import StorageKeyError, StorageNotFoundError


T = TypeVar("T")


def _validate_key(key: str) -> None:
    if not key or key.startswith("/") or key.startswith("\\"):
        raise StorageKeyError(f"Key must be relative and non-empty: {key!r}")
    if ".." in key.split("/"):
        raise StorageKeyError(f"Key cannot traverse: {key!r}")


class GCSStorage:
    """GCS-backed Storage implementation for one tenant.

    The same `Client` instance can serve multiple tenants - we segregate them
    by object prefix, not by client. The shared client is created lazily and
    cached at module level so reused across requests.
    """

    _shared_client: gcs_lib.Client | None = None

    def __init__(self, bucket_name: str, tenant_id: str, kms_key: str | None = None) -> None:
        self._bucket_name = bucket_name
        self._tenant_id = tenant_id
        self._kms_key = kms_key
        self._prefix = f"tenants/{tenant_id}/"

    @classmethod
    def _client(cls) -> gcs_lib.Client:
        if cls._shared_client is None:
            cls._shared_client = gcs_lib.Client()
        return cls._shared_client

    def _bucket(self) -> Any:
        return self._client().bucket(self._bucket_name)

    def _blob(self, key: str) -> Any:
        _validate_key(key)
        blob = self._bucket().blob(self._prefix + key)
        if self._kms_key:
            blob.kms_key_name = self._kms_key
        return blob

    @staticmethod
    async def _run(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    async def read_bytes(self, key: str) -> bytes:
        blob = self._blob(key)
        try:
            data = await self._run(blob.download_as_bytes)
            return bytes(data)
        except Exception as exc:
            if "404" in str(exc) or "NotFound" in type(exc).__name__:
                raise StorageNotFoundError(key) from exc
            raise

    async def write_bytes(self, key: str, data: bytes) -> None:
        blob = self._blob(key)
        await self._run(blob.upload_from_string, data, content_type="application/octet-stream")

    async def read_text(self, key: str, encoding: str = "utf-8") -> str:
        return (await self.read_bytes(key)).decode(encoding)

    async def write_text(self, key: str, data: str, encoding: str = "utf-8") -> None:
        await self.write_bytes(key, data.encode(encoding))

    async def exists(self, key: str) -> bool:
        return bool(await self._run(self._blob(key).exists))

    async def list(self, prefix: str) -> list[str]:
        if prefix:
            _validate_key(prefix)
        full_prefix = self._prefix + prefix
        bucket = self._bucket()
        blobs = await self._run(
            lambda: list(self._client().list_blobs(bucket, prefix=full_prefix))
        )
        return sorted(str(b.name)[len(self._prefix):] for b in blobs)

    async def delete(self, key: str) -> None:
        try:
            await self._run(self._blob(key).delete)
        except Exception as exc:
            if "404" in str(exc) or "NotFound" in type(exc).__name__:
                raise StorageNotFoundError(key) from exc
            raise

    async def signed_url(self, key: str, ttl_seconds: int = 3600) -> str:
        blob = self._blob(key)
        url = await self._run(
            blob.generate_signed_url,
            version="v4",
            expiration=timedelta(seconds=ttl_seconds),
            method="GET",
        )
        return str(url)
