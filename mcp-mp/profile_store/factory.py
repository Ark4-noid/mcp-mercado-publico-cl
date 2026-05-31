from __future__ import annotations
from core.settings import Settings
from .localfs import LocalFSProfileStore
from .protocol import ProfileStore


def make_profile_store(settings: Settings, tenant_id: str) -> ProfileStore:
    if settings.profile_backend == "localfs":
        return LocalFSProfileStore(settings.local_root, tenant_id)
    raise ValueError(f"Unknown profile_backend: {settings.profile_backend}")
