from __future__ import annotations
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import pathname2url

from .protocol import StorageKeyError, StorageNotFoundError


class LocalFSStorage:
    """Filesystem-backed Storage rooted at <root>/<tenant_id>/.

    Used by stdio mode and by HTTP mode with MP_STORAGE_BACKEND=localfs
    (development). All keys are resolved relative to the tenant base
    path; path traversal is rejected.
    """

    def __init__(self, root: Path, tenant_id: str) -> None:
        self._base = (root / tenant_id).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        if not key or key.startswith("/") or key.startswith("\\"):
            raise StorageKeyError(f"Key must be relative and non-empty: {key!r}")
        candidate = (self._base / key).resolve()
        try:
            candidate.relative_to(self._base)
        except ValueError as exc:
            raise StorageKeyError(f"Key escapes tenant root: {key!r}") from exc
        return candidate

    async def read_bytes(self, key: str) -> bytes:
        p = self._resolve(key)
        if not p.is_file():
            raise StorageNotFoundError(key)
        return p.read_bytes()

    async def write_bytes(self, key: str, data: bytes) -> None:
        p = self._resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    async def read_text(self, key: str, encoding: str = "utf-8") -> str:
        return (await self.read_bytes(key)).decode(encoding)

    async def write_text(self, key: str, data: str, encoding: str = "utf-8") -> None:
        await self.write_bytes(key, data.encode(encoding))

    async def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    async def list(self, prefix: str) -> list[str]:
        # Empty prefix lists everything under tenant root.
        root = self._resolve(prefix) if prefix else self._base
        if not root.exists():
            return []
        if root.is_file():
            return [str(root.relative_to(self._base)).replace("\\", "/")]
        return sorted(
            str(p.relative_to(self._base)).replace("\\", "/")
            for p in root.rglob("*")
            if p.is_file()
        )

    async def delete(self, key: str) -> None:
        p = self._resolve(key)
        if not p.is_file():
            raise StorageNotFoundError(key)
        p.unlink()

    async def signed_url(self, key: str, ttl_seconds: int = 3600) -> str:
        # LocalFS has no signing - return a file:// URL for symmetry with GCS.
        p = self._resolve(key)
        return urljoin("file:", pathname2url(str(p)))
