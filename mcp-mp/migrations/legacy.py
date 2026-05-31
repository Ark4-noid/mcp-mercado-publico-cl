"""One-shot idempotent migration from legacy single-user layout to multi-tenant.

Legacy layout:
    <root>/provider.json
    <root>/cookies.json
    <root>/ofertas/<licitacion-id>/...

Multi-tenant layout (tenant_id defaults to "local"):
    <root>/<tenant_id>/profile.json
    <root>/<tenant_id>/secrets/cookies
    <root>/<tenant_id>/ofertas/<licitacion-id>/...

The migration copies, never deletes the source - safe rollback.
"""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger("mp.migrations.legacy")

MARKER_FILENAME = ".migration_v1_done"

try:
    import portalocker  # type: ignore[import-not-found]

    HAS_PORTALOCKER = True
except ImportError:  # pragma: no cover - portalocker is optional
    HAS_PORTALOCKER = False
    # TODO: file lock - Sprint 2. Single-process desktop is OK without lock.


def _copy_file_idempotent(src: Path, dst: Path, summary: dict[str, list[str]]) -> None:
    """Copy src -> dst only if dst does not already exist."""
    if not src.is_file():
        return
    if dst.exists():
        summary["skipped"].append(str(dst))
        logger.info("migration: skip existing %s", dst)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    summary["moved"].append(str(dst))
    logger.info("migration: copied %s -> %s", src, dst)


def _copy_tree_idempotent(src: Path, dst: Path, summary: dict[str, list[str]]) -> None:
    """Copy directory tree if dst does not exist (dirs_exist_ok=False)."""
    if not src.is_dir():
        return
    if dst.exists():
        summary["skipped"].append(str(dst))
        logger.info("migration: skip existing tree %s", dst)
        return
    shutil.copytree(src, dst, dirs_exist_ok=False)
    summary["moved"].append(str(dst))
    logger.info("migration: copied tree %s -> %s", src, dst)


def migrate_legacy_layout(
    local_root: Path,
    legacy_ticket_env_value: str | None = None,
    tenant_id: str = "local",
) -> dict[str, Any]:
    """Migrate ~/.mp-mcp/* to ~/.mp-mcp/<tenant_id>/*.

    Returns a summary dict {moved: [...], skipped: [...], migrated_ticket: bool,
    marker_created: bool}. Idempotent: safe to call on every startup.
    """
    summary: dict[str, Any] = {
        "moved": [],
        "skipped": [],
        "migrated_ticket": False,
        "marker_created": False,
    }

    local_root = Path(local_root)
    if not local_root.exists():
        local_root.mkdir(parents=True, exist_ok=True)
        logger.info("migration: created fresh local_root %s", local_root)

    marker = local_root / MARKER_FILENAME
    if marker.is_file():
        logger.debug("migration: marker present, skipping all work")
        return summary

    tenant_root = local_root / tenant_id
    tenant_root.mkdir(parents=True, exist_ok=True)

    # 1. provider.json -> <tenant>/profile.json
    legacy_profile = local_root / "provider.json"
    target_profile = tenant_root / "profile.json"
    _copy_file_idempotent(legacy_profile, target_profile, summary)

    # 2. cookies.json -> <tenant>/secrets/cookies
    legacy_cookies = local_root / "cookies.json"
    target_cookies = tenant_root / "secrets" / "cookies"
    _copy_file_idempotent(legacy_cookies, target_cookies, summary)

    # 3. ofertas/ -> <tenant>/ofertas/
    legacy_ofertas = local_root / "ofertas"
    target_ofertas = tenant_root / "ofertas"
    _copy_tree_idempotent(legacy_ofertas, target_ofertas, summary)

    # 4. Inject ticket from env if profile lacks one
    if legacy_ticket_env_value and target_profile.is_file():
        try:
            profile_data: dict[str, Any] = json.loads(
                target_profile.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("migration: cannot parse %s: %s", target_profile, exc)
            profile_data = {}

        existing_ticket = profile_data.get("ticket")
        if isinstance(existing_ticket, str) and existing_ticket:
            logger.info(
                "migration: profile already has ticket, env value ignored"
            )
        else:
            profile_data["ticket"] = legacy_ticket_env_value
            target_profile.write_text(
                json.dumps(profile_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            summary["migrated_ticket"] = True
            logger.info(
                "migration: injected ticket from env into %s", target_profile
            )

    # 5. Drop marker for fast-path on subsequent boots
    try:
        marker.write_text("v1\n", encoding="utf-8")
        summary["marker_created"] = True
    except OSError as exc:  # pragma: no cover - very unlikely on tmpdir
        logger.warning("migration: cannot write marker: %s", exc)

    return summary
