from pathlib import Path

from app.config import Settings


def test_settings_from_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GAME_TIME_SCALE", "120")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("VALHALLA_URL", "https://example.test/")
    settings = Settings.from_env(tmp_path)
    assert settings.base_dir == tmp_path
    assert settings.data_dir.exists()
    assert settings.game_time_scale == 120
    assert settings.log_level == "DEBUG"
    assert settings.valhalla_url == "https://example.test"


def test_catalogue_path_is_independent_from_player_data(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "players"))
    monkeypatch.delenv("VEHICLE_CATALOGUE_PATH", raising=False)
    settings = Settings.from_env(tmp_path)
    assert (
        settings.vehicle_catalogue_path
        == tmp_path / "data" / "world_freight_vehicle_catalog.sqlite3"
    )
    monkeypatch.setenv("VEHICLE_CATALOGUE_PATH", str(tmp_path / "external.db"))
    assert (
        Settings.from_env(tmp_path).vehicle_catalogue_path
        == tmp_path / "external.db"
    )
