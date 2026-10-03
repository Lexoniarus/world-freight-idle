"""Settings isolation shared by browser-test processes."""

from dataclasses import replace
from pathlib import Path

from app.config import Settings


def isolated_browser_settings(database_path: Path) -> Settings:
    """Build browser settings that cannot connect to live Supabase services."""
    return replace(
        Settings.from_env(),
        db_path=database_path,
        database_url=None,
        game_time_scale=900,
        supabase_url=None,
        supabase_publishable_key=None,
        supabase_jwks_url=None,
    )
