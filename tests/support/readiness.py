"""Shared relational routing-readiness factories for tests."""

from pathlib import Path

from app.domain.routing_readiness import (
    RouteReference,
    RoutingRelation,
    relation_identity,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_readiness import SqliteRoutingReadinessStore


def routing_store(
    directory: Path,
) -> tuple[SqliteGameDatabase, SqliteRoutingReadinessStore]:
    """Create an isolated routing-readiness store."""
    database = SqliteGameDatabase(directory / "game.db")
    database.initialize()
    SqliteProviderCache(database)
    return database, SqliteRoutingReadinessStore(database)


def ready_relation() -> RoutingRelation:
    """Build one coherent ready relation."""
    return RoutingRelation(
        RouteReference(relation_identity("A", "B"), "revision"),
        "A",
        "B",
        "fingerprint",
        "ready",
        None,
        None,
        10,
    )
