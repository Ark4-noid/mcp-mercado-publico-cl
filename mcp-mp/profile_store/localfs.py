from __future__ import annotations
import json
from pathlib import Path
from typing import Any


class LocalFSProfileStore:
    """JSON-on-disk profile, one per tenant at <root>/<tenant_id>/profile.json."""

    def __init__(self, root: Path, tenant_id: str) -> None:
        self._dir = (root / tenant_id).resolve()
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / "profile.json"

    async def get(self) -> dict[str, Any] | None:
        if not self._path.is_file():
            return None
        loaded: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))
        return loaded

    async def save(self, profile: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    async def delete(self) -> None:
        if self._path.is_file():
            self._path.unlink()
