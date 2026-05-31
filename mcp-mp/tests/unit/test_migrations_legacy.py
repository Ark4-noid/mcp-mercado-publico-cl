"""Tests for the one-shot legacy layout migration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from migrations.legacy import MARKER_FILENAME, migrate_legacy_layout


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_clean_install(tmp_path: Path) -> None:
    root = tmp_path / "fresh"
    summary = migrate_legacy_layout(root)
    assert summary["moved"] == []
    assert summary["skipped"] == []
    assert summary["migrated_ticket"] is False
    assert (root / MARKER_FILENAME).is_file()


def test_migrates_profile(tmp_path: Path) -> None:
    root = tmp_path / "mp"
    root.mkdir()
    _write(root / "provider.json", json.dumps({"empresa": "ACME"}))

    summary = migrate_legacy_layout(root)

    target = root / "local" / "profile.json"
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == {"empresa": "ACME"}
    assert str(target) in summary["moved"]


def test_migrates_cookies(tmp_path: Path) -> None:
    root = tmp_path / "mp"
    root.mkdir()
    _write(root / "cookies.json", '[{"name":"sid","value":"abc"}]')

    migrate_legacy_layout(root)

    target = root / "local" / "secrets" / "cookies"
    assert target.is_file()
    assert "sid" in target.read_text(encoding="utf-8")


def test_migrates_ofertas(tmp_path: Path) -> None:
    root = tmp_path / "mp"
    root.mkdir()
    _write(root / "ofertas" / "1234-5" / "some.pdf", "%PDF-1.4 fake")

    migrate_legacy_layout(root)

    moved = root / "local" / "ofertas" / "1234-5" / "some.pdf"
    assert moved.is_file()
    assert moved.read_text(encoding="utf-8").startswith("%PDF")


def test_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "mp"
    root.mkdir()
    _write(root / "provider.json", json.dumps({"empresa": "ACME"}))

    first = migrate_legacy_layout(root)
    second = migrate_legacy_layout(root)

    # Second call hits the marker fast-path - returns an empty summary.
    assert second["moved"] == []
    assert second["skipped"] == []
    assert first["marker_created"] is True


def test_env_ticket_added_when_missing(tmp_path: Path) -> None:
    root = tmp_path / "mp"
    root.mkdir()
    _write(root / "provider.json", json.dumps({"empresa": "ACME"}))

    summary = migrate_legacy_layout(root, legacy_ticket_env_value="ABC")

    target = root / "local" / "profile.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["ticket"] == "ABC"
    assert summary["migrated_ticket"] is True


def test_env_ticket_ignored_when_present(tmp_path: Path) -> None:
    root = tmp_path / "mp"
    root.mkdir()
    _write(
        root / "provider.json",
        json.dumps({"empresa": "ACME", "ticket": "EXISTING"}),
    )

    summary = migrate_legacy_layout(root, legacy_ticket_env_value="NEW")

    target = root / "local" / "profile.json"
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["ticket"] == "EXISTING"
    assert summary["migrated_ticket"] is False


def test_marker_file_created(tmp_path: Path) -> None:
    root = tmp_path / "mp"
    root.mkdir()
    migrate_legacy_layout(root)
    assert (root / MARKER_FILENAME).is_file()


def test_source_files_not_deleted(tmp_path: Path) -> None:
    root = tmp_path / "mp"
    root.mkdir()
    src = root / "provider.json"
    _write(src, json.dumps({"empresa": "ACME"}))

    migrate_legacy_layout(root)

    assert src.is_file(), "legacy source must survive the migration"
