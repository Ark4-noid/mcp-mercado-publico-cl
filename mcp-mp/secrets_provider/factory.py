from __future__ import annotations
from core.settings import Settings
from .localfs import LocalFSSecrets
from .protocol import SecretsProvider


def make_secrets(settings: Settings, tenant_id: str) -> SecretsProvider:
    if settings.secrets_backend == "localfs":
        return LocalFSSecrets(settings.local_root, tenant_id)
    raise ValueError(f"Unknown secrets_backend: {settings.secrets_backend}")
