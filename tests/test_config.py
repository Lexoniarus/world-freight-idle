from pathlib import Path
from unittest.mock import patch

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


def test_settings_load_browser_safe_supabase_values_from_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        "HOST=127.0.0.1\n"
        "PORT=8123\n"
        "SUPABASE_URL=https://project.supabase.co\n"
        "SUPABASE_PUBLISHABLE_KEY=sb_publishable_test\n"
        "SUPABASE_JWKS_URL=https://project.supabase.co/auth/v1/jwks\n",
        encoding="utf-8",
    )
    with patch.dict("os.environ", {}, clear=True):
        settings = Settings.from_env(tmp_path)
    assert settings.supabase_url == "https://project.supabase.co"
    assert settings.host == "127.0.0.1"
    assert settings.port == 8123
    assert settings.supabase_publishable_key == "sb_publishable_test"
    assert settings.supabase_jwks_url is not None
    assert settings.supabase_jwks_url.endswith("/auth/v1/jwks")
