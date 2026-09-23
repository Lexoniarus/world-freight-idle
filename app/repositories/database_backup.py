"""Consistent SQLite backups for explicit local maintenance."""

import sqlite3
from contextlib import closing
from pathlib import Path


def backup_database(db_path: Path, backup_path: Path) -> None:
    """Copy committed state including WAL, without overwriting a backup."""
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(
        sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    ) as source:
        with backup_path.open("xb"):
            pass
        try:
            with closing(sqlite3.connect(backup_path)) as target:
                source.backup(target)
        except BaseException:
            backup_path.unlink(missing_ok=True)
            raise
