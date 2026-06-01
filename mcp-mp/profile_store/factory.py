from __future__ import annotations
from core.settings import Settings
from .localfs import LocalFSProfileStore
from .protocol import ProfileStore


def make_profile_store(settings: Settings, tenant_id: str) -> ProfileStore:
    if settings.profile_backend == "localfs":
        return LocalFSProfileStore(settings.local_root, tenant_id)
    if settings.profile_backend == "gcs":
        if not settings.gcs_bucket:
            raise ValueError("MP_GCS_BUCKET required when profile_backend=gcs")
        from .gcs import GCSProfileStore
        return GCSProfileStore(settings.gcs_bucket, tenant_id, settings.gcs_kms_key)
    raise ValueError(f"Unknown profile_backend: {settings.profile_backend}")
