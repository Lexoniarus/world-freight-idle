"""Isolated settings for synthetic and reference acceptance tests."""

from __future__ import annotations

from pathlib import Path

from app.config import Settings
from tests.support.catalogue_databases import (
    create_small_vehicle_catalogue,
    create_small_world_catalogue,
)


def build_synthetic_application_settings(tmp_path: Path) -> Settings:
    """Build application settings backed by compact readable SQL fixtures."""
    vehicle_path = tmp_path / "vehicles.sqlite3"
    world_path = tmp_path / "world.sqlite3"
    if not vehicle_path.exists():
        create_small_vehicle_catalogue(vehicle_path)
    if not world_path.exists():
        create_small_world_catalogue(world_path)
    return _settings(tmp_path, vehicle_path, world_path)


def _settings(
    tmp_path: Path,
    vehicle_path: Path,
    world_path: Path,
) -> Settings:
    """Return isolated settings without choosing catalogue provenance."""
    return Settings(
        world_catalogue_path=world_path,
        vehicle_catalogue_path=vehicle_path,
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "game.db",
        nominatim_url="https://n.test",
        valhalla_url="https://v.test",
        http_user_agent="agent",
        valhalla_client_id="client",
        request_timeout_seconds=1,
        game_time_scale=1,
        log_level="CRITICAL",
    )
