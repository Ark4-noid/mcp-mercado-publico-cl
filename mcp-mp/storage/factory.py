from __future__ import annotations
from core.settings import Settings
from .gcs import GCSStorage
from .localfs import LocalFSStorage
from .protocol import Storage


def make_storage(settings: Settings, tenant_id: str) -> Storage:
    """Construct the Storage backend for one tenant according to settings."""
    if settings.storage_backend == "localfs":
        return LocalFSStorage(settings.local_root, tenant_id)
    if settings.storage_backend == "gcs":
        if not settings.gcs_bucket:
            raise ValueError("MP_GCS_BUCKET required when storage_backend=gcs")
        return GCSStorage(settings.gcs_bucket, tenant_id, settings.gcs_kms_key)
    raise ValueError(f"Unknown storage_backend: {settings.storage_backend}")
