from __future__ import annotations


class GCSStorage:
    """Stub for Google Cloud Storage backend.

    The functional implementation lands in Sprint 3 (Cloud Run cutover).
    Importing this module must never crash; calling any method raises
    NotImplementedError with a clear pointer.
    """

    def __init__(self, bucket: str, tenant_id: str, kms_key: str | None = None) -> None:
        self._bucket = bucket
        self._tenant_id = tenant_id
        self._kms_key = kms_key

    def _not_yet(self) -> NotImplementedError:
        return NotImplementedError(
            "GCS backend lands in Sprint 3. Set MP_STORAGE_BACKEND=localfs for now."
        )

    async def read_bytes(self, key: str) -> bytes:
        raise self._not_yet()

    async def write_bytes(self, key: str, data: bytes) -> None:
        raise self._not_yet()

    async def read_text(self, key: str, encoding: str = "utf-8") -> str:
        raise self._not_yet()

    async def write_text(self, key: str, data: str, encoding: str = "utf-8") -> None:
        raise self._not_yet()

    async def exists(self, key: str) -> bool:
        raise self._not_yet()

    async def list(self, prefix: str) -> list[str]:
        raise self._not_yet()

    async def delete(self, key: str) -> None:
        raise self._not_yet()

    async def signed_url(self, key: str, ttl_seconds: int = 3600) -> str:
        raise self._not_yet()
