"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
    routing_anchor_max_snap_m: float = 250.0
    cookie_secure: bool = False
    vehicle_catalogue_path: Path | None = None
    world_catalogue_path: Path | None = None

    @classmethod
    def from_env(cls, base_dir: Path | None = None) -> "Settings":
        """Build settings from the current process environment."""
        resolved_base = base_dir or Path(__file__).resolve().parent.parent
        data_dir = Path(os.getenv("DATA_DIR", resolved_base / "data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            base_dir=resolved_base,
            data_dir=data_dir,
            db_path=Path(os.getenv("DB_PATH", data_dir / "game.db")),
            world_catalogue_path=Path(
                os.getenv(
                    "WORLD_CATALOGUE_PATH",
                    resolved_base
                    / "data"
                    / "world_freight_company_facility_mvp.sqlite3",
                )
            ),
            vehicle_catalogue_path=Path(
                os.getenv(
                    "VEHICLE_CATALOGUE_PATH",
                    resolved_base
                    / "data"
                    / "world_freight_vehicle_catalog.sqlite3",
                )
            ),
            nominatim_url=os.getenv(
                "NOMINATIM_URL",
                "https://nominatim.openstreetmap.org",
            ).rstrip("/"),
            valhalla_url=os.getenv(
                "VALHALLA_URL",
                "https://valhalla1.openstreetmap.de",
            ).rstrip("/"),
            http_user_agent=os.getenv(
                "HTTP_USER_AGENT",
                "WorldFreightIdleMVP/0.4 (local-development)",
            ),
            valhalla_client_id=os.getenv(
                "VALHALLA_CLIENT_ID",
                "world-freight-idle-local",
            ),
            request_timeout_seconds=float(
                os.getenv("REQUEST_TIMEOUT_SECONDS", "20")
            ),
            game_time_scale=max(
                0.001,
                float(os.getenv("GAME_TIME_SCALE", "1")),
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            routing_anchor_max_snap_m=max(
                1.0,
                float(os.getenv("ROUTING_ANCHOR_MAX_SNAP_M", "250")),
            ),
            cookie_secure=os.getenv("COOKIE_SECURE", "false").lower()
            == "true",
        )
