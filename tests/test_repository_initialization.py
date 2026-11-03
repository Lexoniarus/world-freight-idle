"""Explicit additive repository schema initialization contracts."""

from app.composition.runtime import initialize_runtime_schema
from app.repositories.accounts import AccountRepository
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import SqliteRoutingReadinessStore

ADDITIVE_TABLES = {
    "account_preferences",
    "auth_attempts",
    "geocode_cache",
    "market_coverage",
    "market_offer_templates",
    "market_preparations",
    "market_stock_cursors",
    "market_stock_pending",
    "market_template_uses",
    "market_templates",
    "offer_route_references",
    "route_cache",
    "routing_anchor_sources",
    "routing_anchors",
    "routing_attempts",
    "routing_connection_proofs",
    "routing_leases",
    "routing_provider_revisions",
    "routing_relations",
    "sessions",
}


def table_names(database: SqliteGameDatabase) -> set[str]:
    """Read user-defined table names without assuming an adapter schema."""
    with database.connect() as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }


def test_repository_constructors_do_not_mutate_schema(tmp_path):
    database = SqliteGameDatabase(tmp_path / "constructors.db")
    database.initialize()
    before = table_names(database)

    AccountRepository(database)
    SqliteProviderCache(database)
    SqliteRoutingAnchorRepository(database)
    SqliteRoutingReadinessStore(database)
    SqlitePreparationStore(database)

    assert table_names(database) == before
    assert ADDITIVE_TABLES.isdisjoint(before)


def test_runtime_repository_schema_initialization_is_explicit_and_idempotent(
    tmp_path,
):
    database = SqliteGameDatabase(tmp_path / "runtime.db")
    database.initialize()

    initialize_runtime_schema(database)
    first = table_names(database)
    initialize_runtime_schema(database)

    assert table_names(database) == first
    assert ADDITIVE_TABLES <= first
