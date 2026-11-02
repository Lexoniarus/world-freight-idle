"""Account isolation, security, persistence and concurrent economy tests."""

import runpy
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.support.application_settings import (
    build_synthetic_application_settings,
)

PASSWORD = "test-only-password-42"


def test_launchers_run_main_without_changing_working_directory():
    root = Path(__file__).resolve().parents[1]
    with (
        patch("app.launcher.run", return_value=0) as run,
        patch("sys.argv", ["main.py"]),
        pytest.raises(SystemExit) as exited,
    ):
        runpy.run_path(str(root / "main.py"), run_name="__main__")
    assert exited.value.code == 0
    run.assert_called_once_with()


async def test_initialization_does_not_implicitly_import_legacy_trips(
    tmp_path,
):
    import httpx

    from app.bootstrap import build_game_runtime
    from app.domain.errors import UnsupportedGameSchema

    settings = build_synthetic_application_settings(tmp_path)
    import sqlite3

    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(settings.db_path)) as connection, connection:
        connection.execute(
            "CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.execute(
            "INSERT INTO kv VALUES (?, ?)",
            ("active_trip", '{"id":"old","arrives_at":42}'),
        )
    original = settings.db_path.read_bytes()
    async with httpx.AsyncClient() as routing_client:
        with pytest.raises(UnsupportedGameSchema):
            build_game_runtime(settings, routing_client)
    assert settings.db_path.read_bytes() == original
