"""Regression tests for isolated browser-test configuration."""

from tests.browser_settings import isolated_browser_settings


def test_browser_settings_reject_live_supabase_configuration(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://production.invalid/example",
    )
    monkeypatch.setenv("SUPABASE_URL", "https://production.invalid")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "publishable-test-key")
    monkeypatch.setenv(
        "SUPABASE_JWKS_URL",
        "https://production.invalid/auth/v1/.well-known/jwks.json",
    )
    database_path = tmp_path / "browser.db"

    settings = isolated_browser_settings(database_path)

    assert settings.db_path == database_path
    assert settings.database_url is None
    assert settings.supabase_url is None
    assert settings.supabase_publishable_key is None
    assert settings.supabase_jwks_url is None
    assert settings.game_time_scale == 900
