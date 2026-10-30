"""Canonical local catalogue paths and stable test identities."""

from pathlib import Path

from app.domain.world_scopes import WorldScope
from app.repositories.world_catalogue import SqliteWorldCatalogue

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORLD_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "world_freight_company_facility_mvp.sqlite3"
)
BERLIN_UID = (
    WorldScope(SqliteWorldCatalogue(WORLD_PATH).read())
    .facility("berlin_westhafen")
    .facility_uid
)
