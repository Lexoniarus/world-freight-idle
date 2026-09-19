"""Atomic persistence boundary for the explicit world-state migration."""

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any


class WorldStateMigrationRepository:
    """Rewrite existing JSON state in one transaction without account edits."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def transform(
        self,
        convert: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> int:
        """Transform all records or preserve the original database."""
        with closing(
            sqlite3.connect(
                self.path.resolve().as_uri() + "?mode=rw",
                uri=True,
            )
        ) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                before = {
                    key: json.loads(value)
                    for key, value in connection.execute(
                        "SELECT key,value FROM kv"
                    )
                }
                after = convert(before)
                changed = 0
                for key, value in after.items():
                    if key not in before or value != before[key]:
                        connection.execute(
                            "INSERT INTO kv(key,value) VALUES(?,?) "
                            "ON CONFLICT(key) DO UPDATE "
                            "SET value=excluded.value",
                            (key, json.dumps(value)),
                        )
                        changed += 1
                return changed
