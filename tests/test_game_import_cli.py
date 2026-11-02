"""Offline import CLI path, backup and incomplete-output safety."""

import sqlite3
from unittest.mock import patch

import pytest

from app.bootstrap import (
    build_game_importer,
)
from app.config import Settings
from app.domain.errors import PersistenceError
from app.repositories.database_backup import backup_database
from app.repositories.legacy_game_import import (
    LegacyGameImporter,
)
from tests.support.catalogues import BERLIN_UID


def test_import_cli_requires_backup_and_separate_paths(
    legacy_source, tmp_path, monkeypatch, capsys
):
    from scripts import import_legacy_game as cli

    path, importer, _, now, _ = legacy_source
    monkeypatch.setattr(
        cli,
        "build_game_importer",
        lambda source, settings, exclude_global_demo=False: importer,
    )
    monkeypatch.setattr(cli.time, "time", lambda: now)
    monkeypatch.setattr(
        "sys.argv", ["import", "--source", str(path), "--check"]
    )
    cli.main()
    assert '"accounts": 3' in capsys.readouterr().out
    backup = tmp_path / "backup.db"
    output = tmp_path / "output.db"
    monkeypatch.setattr(
        "sys.argv",
        [
            "import",
            "--source",
            str(path),
            "--backup",
            str(backup),
            "--output",
            str(output),
        ],
    )
    with patch.object(cli, "backup_database", side_effect=OSError("disk")):
        with pytest.raises(OSError):
            cli.main()
    assert not output.exists()
    cli.main()
    assert backup.exists() and output.exists()
    with pytest.raises(SystemExit):
        cli.main()
    for extra in (
        [],
        ["--backup", str(path), "--output", str(tmp_path / "other.db")],
        ["--check", "--backup", str(backup)],
    ):
        monkeypatch.setattr(
            "sys.argv", ["import", "--source", str(path), *extra]
        )
        with pytest.raises(SystemExit):
            cli.main()
    settings = Settings.from_env()
    built = build_game_importer(path, settings)
    assert isinstance(built, LegacyGameImporter)
    assert built.reader.world.facility(BERLIN_UID).facility_uid == BERLIN_UID
    with pytest.raises(PersistenceError):
        build_game_importer(tmp_path / "missing.db", settings).inspect(now)


def test_backup_failure_removes_only_its_own_incomplete_output(tmp_path):
    from unittest.mock import MagicMock

    source = tmp_path / "source.db"
    target = tmp_path / "incomplete.db"
    source.write_bytes(b"source untouched")
    with patch("app.repositories.database_backup.sqlite3.connect") as connect:
        origin = MagicMock()
        destination = MagicMock()
        connect.side_effect = [origin, destination]
        origin.backup.side_effect = sqlite3.OperationalError("disk full")
        with pytest.raises(sqlite3.OperationalError):
            backup_database(source, target)
        assert not target.exists()
        origin.close.assert_called_once()
        destination.close.assert_called_once()
    assert source.read_bytes() == b"source untouched"
