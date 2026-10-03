"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    base_dir: Path
    data_dir: Path
    db_path: Path
    nominatim_url: str
    valhalla_url: str
    http_user_agent: str
    valhalla_client_id: str
    request_timeout_seconds: float
    game_time_scale: float
    log_level: str
    routing_anchor_max_snap_m: float = 1000.0
    valhalla_concurrency: int = 1
    valhalla_minimum_interval: float = 1.0
    cookie_secure: bool = False
    vehicle_catalogue_path: Path | None = None
    world_catalogue_path: Path | None = None
    database_url: str | None = None
    game_database_schema: str = "game"
    world_database_schema: str = "world_catalogue"
    vehicle_database_schema: str = "vehicle_catalogue"
    database_pool_size: int = 5
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_jwks_url: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> "Settings":
        """Build settings from the current process environment."""
        resolved_base = base_dir or Path(__file__).resolve().parent.parent
        environment = {
            key: value
            for key, value in dotenv_values(resolved_base / ".env").items()
            if value is not None
        }
        environment.update(os.environ)
        data_dir = Path(
            environment.get("DATA_DIR", str(resolved_base / "data"))
        )
        data_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            base_dir=resolved_base,
            data_dir=data_dir,
            db_path=Path(
                environment.get("DB_PATH", str(data_dir / "game.db"))
            ),
            world_catalogue_path=Path(
                environment.get(
                    "WORLD_CATALOGUE_PATH",
                    str(
                        resolved_base
                        / "data"
                        / "world_freight_company_facility_mvp.sqlite3"
                    ),
                )
            ),
            vehicle_catalogue_path=Path(
                environment.get(
                    "VEHICLE_CATALOGUE_PATH",
                    str(
                        resolved_base
                        / "data"
                        / "world_freight_vehicle_catalog.sqlite3"
                    ),
                )
            ),
            nominatim_url=environment.get(
                "NOMINATIM_URL",
                "https://nominatim.openstreetmap.org",
            ).rstrip("/"),
            valhalla_url=environment.get(
                "VALHALLA_URL",
                "https://valhalla1.openstreetmap.de",
            ).rstrip("/"),
            http_user_agent=environment.get(
                "HTTP_USER_AGENT",
                "WorldFreightIdleMVP/0.4 (local-development)",
            ),
            valhalla_client_id=environment.get(
                "VALHALLA_CLIENT_ID",
                "world-freight-idle-local",
            ),
            request_timeout_seconds=float(
                environment.get("REQUEST_TIMEOUT_SECONDS", "20")
            ),
            game_time_scale=max(
                0.001,
                float(environment.get("GAME_TIME_SCALE", "1")),
            ),
            log_level=environment.get("LOG_LEVEL", "INFO").upper(),
            routing_anchor_max_snap_m=max(
                1.0,
                float(environment.get("ROUTING_ANCHOR_MAX_SNAP_M", "1000")),
            ),
            valhalla_concurrency=int(
                environment.get("VALHALLA_CONCURRENCY", "1")
            ),
            valhalla_minimum_interval=float(
                environment.get("VALHALLA_MINIMUM_INTERVAL", "1")
            ),
            cookie_secure=environment.get("COOKIE_SECURE", "false").lower()
            == "true",
            database_url=environment.get("DATABASE_URL") or None,
            game_database_schema=environment.get(
                "GAME_DATABASE_SCHEMA", "game"
            ),
            world_database_schema=environment.get(
                "WORLD_DATABASE_SCHEMA", "world_catalogue"
            ),
            vehicle_database_schema=environment.get(
                "VEHICLE_DATABASE_SCHEMA", "vehicle_catalogue"
            ),
            database_pool_size=max(
                1, int(environment.get("DATABASE_POOL_SIZE", "5"))
            ),
            supabase_url=environment.get("SUPABASE_URL") or None,
            supabase_publishable_key=(
                environment.get("SUPABASE_PUBLISHABLE_KEY") or None
            ),
            supabase_jwks_url=environment.get("SUPABASE_JWKS_URL") or None,
            host=environment.get("HOST", "0.0.0.0"),
            port=int(environment.get("PORT", "8000")),
        )
