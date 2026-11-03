"""Read-only routing and economy audit dependency assembly."""

import random
from pathlib import Path

from app.composition.runtime import GameRuntime
from app.repositories.routing_audit import SqliteRoutingAudit
from app.repositories.vehicle_catalogue import SqliteVehicleCatalogue
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.services.economy_audit import EconomyAuditService


def build_routing_audit(runtime: GameRuntime) -> SqliteRoutingAudit:
    """Compose local routing diagnostics without provider operations."""
    return SqliteRoutingAudit(runtime.database)


def build_economy_audit(root: Path, seed: int) -> EconomyAuditService:
    """Compose reproducible audits from read-only reference catalogues."""
    return EconomyAuditService(
        SqliteVehicleCatalogue(
            root / "data/world_freight_vehicle_catalog.sqlite3"
        ),
        SqliteWorldCatalogue(
            root / "data/world_freight_company_facility_mvp.sqlite3"
        ),
        random.Random(seed),
    )
