from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the MCP server.

    All values can be overridden via env vars prefixed with MP_.
    """

    storage_backend: Literal["localfs", "gcs"] = "localfs"
    secrets_backend: Literal["localfs"] = "localfs"
    profile_backend: Literal["localfs"] = "localfs"
    local_root: Path = Field(default_factory=lambda: Path.home() / ".mp-mcp")
    chilecompra_base_url: AnyHttpUrl = "https://api.mercadopublico.cl/servicios/v1/publico"  # type: ignore[assignment]
    max_browsers: int = Field(default=2, ge=1, le=10)
    tenant_mode: Literal["legacy", "tenant-aware"] = "legacy"
    gcs_bucket: str | None = None
    gcs_kms_key: str | None = None
    legacy_ticket_env: str = "MERCADO_PUBLICO_TICKET"

    model_config = SettingsConfigDict(
        env_prefix="MP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def validate_runtime(self) -> None:
        """Cross-field validation that runs at app startup. Fail-fast."""
        if self.storage_backend == "gcs" and not self.gcs_bucket:
            raise ValueError(
                "MP_GCS_BUCKET is required when MP_STORAGE_BACKEND=gcs"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.validate_runtime()
    return s


def reset_settings_cache() -> None:
    """Clear the lru_cache. Tests only."""
    get_settings.cache_clear()
