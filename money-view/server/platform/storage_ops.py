"""Local SQLite backup and restore-to-new-file operations.

Run from money-view: python -m server.platform.storage_ops backup SOURCE DESTINATION
Restore: python -m server.platform.storage_ops restore BACKUP NEW_DATABASE
The adjacent .manifest.json file must accompany a backup when restoring it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from ..store import BUSY_TIMEOUT_MS


def _checked_path(path: str | Path, *, existing: bool) -> Path:
    candidate = Path(path).absolute()
    if any(part.is_symlink() for part in (candidate, *candidate.parents)):
        raise ValueError("Symlink paths are not supported")
    candidate = candidate.resolve(strict=existing)
    if existing and not candidate.is_file():
        raise ValueError("Source must be a regular database file")
    if not existing and candidate.exists():
        raise FileExistsError(candidate)
    return candidate


def _reserve(path: Path) -> None:
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    os.close(descriptor)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as content:
        for block in iter(lambda: content.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_connection(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        f"{path.as_uri()}?mode=ro", uri=True, timeout=BUSY_TIMEOUT_MS / 1000
    )


def _inspect(connection: sqlite3.Connection) -> dict[str, int]:
    if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("Database integrity check failed")
    if connection.execute("PRAGMA foreign_key_check").fetchall():
        raise ValueError("Database foreign key check failed")
    tables = connection.execute(
        "SELECT name FROM sqlite_schema WHERE type='table' ORDER BY name"
    ).fetchall()
    return {
        name: connection.execute(
            'SELECT count(*) FROM "' + name.replace('"', '""') + '"'
        ).fetchone()[0]
        for (name,) in tables
    }


def _copy(source: Path, destination: Path) -> dict[str, int]:
    with closing(_read_connection(source)) as origin:
        with closing(sqlite3.connect(destination)) as target:
            origin.backup(target)
            target.execute("PRAGMA journal_mode=DELETE")
            counts = _inspect(target)
    with destination.open("rb") as content:
        os.fsync(content.fileno())
    return counts


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def backup_database(source: str | Path, destination: str | Path) -> dict:
    source_path = _checked_path(source, existing=True)
    destination_path = _checked_path(destination, existing=False)
    manifest_path = _checked_path(
        str(destination_path) + ".manifest.json", existing=False
    )
    published: list[Path] = []
    try:
        with TemporaryDirectory(
            prefix=".clara-backup-", dir=destination_path.parent
        ) as folder:
            staged = Path(folder) / "database.sqlite3"
            staged_manifest = Path(folder) / "manifest.json"
            _reserve(staged)
            _reserve(staged_manifest)
            counts = _copy(source_path, staged)
            manifest = {
                "format_version": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "sha256": _digest(staged),
                "size_bytes": staged.stat().st_size,
                "integrity_check": "ok",
                "foreign_key_check": "ok",
                "row_counts": counts,
            }
            with staged_manifest.open("w") as content:
                json.dump(manifest, content, indent=2, sort_keys=True)
                content.write("\n")
                content.flush()
                os.fsync(content.fileno())
            # Publish complete files atomically without replacing an existing name.
            # The manifest is the completion marker and is published last.
            for temporary, final in (
                (staged, destination_path),
                (staged_manifest, manifest_path),
            ):
                os.link(temporary, final)
                published.append(final)
            _sync_directory(destination_path.parent)
        return manifest
    except BaseException:
        for path in reversed(published):
            path.unlink(missing_ok=True)
        raise


def restore_database(source: str | Path, destination: str | Path) -> dict:
    source_path = _checked_path(source, existing=True)
    destination_path = _checked_path(destination, existing=False)
    manifest_path = _checked_path(str(source_path) + ".manifest.json", existing=True)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("format_version") != 1 or manifest.get("sha256") != _digest(
        source_path
    ):
        raise ValueError("Backup manifest or SHA-256 mismatch")
    with TemporaryDirectory(
        prefix=".clara-restore-", dir=destination_path.parent
    ) as folder:
        staged = Path(folder) / "database.sqlite3"
        _reserve(staged)
        counts = _copy(source_path, staged)
        if counts != manifest.get("row_counts"):
            raise ValueError("Restored row counts differ from backup manifest")
        os.link(staged, destination_path)
        _sync_directory(destination_path.parent)
    return {"integrity_check": "ok", "foreign_key_check": "ok", "row_counts": counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("backup", "restore"))
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    operation = backup_database if args.operation == "backup" else restore_database
    print(json.dumps(operation(args.source, args.destination), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
