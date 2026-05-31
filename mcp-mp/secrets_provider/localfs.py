from __future__ import annotations
from pathlib import Path

from .protocol import SecretNotFoundError, validate_secret_name


class LocalFSSecrets:
    """Plain-file secrets backend rooted at <root>/<tenant_id>/secrets/.

    No encryption in Sprint 1 - Secret Manager lands in Sprint 3. Files
    are stored as raw bytes named after the secret. Use only for local
    development.
    """

    def __init__(self, root: Path, tenant_id: str) -> None:
        self._dir = (root / tenant_id / "secrets").resolve()
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        validate_secret_name(name)
        return self._dir / name

    async def get_secret(self, name: str) -> bytes | None:
        p = self._path(name)
        if not p.is_file():
            return None
        return p.read_bytes()

    async def set_secret(self, name: str, value: bytes) -> None:
        p = self._path(name)
        p.write_bytes(value)

    async def delete_secret(self, name: str) -> None:
        p = self._path(name)
        if not p.is_file():
            raise SecretNotFoundError(name)
        p.unlink()
