"""Bounded, indexed and shared public traffic repository contracts."""

from dataclasses import asdict, replace
from unittest.mock import patch

import pytest

from app.domain.contracts import HistoricalContractSnapshot
from app.domain.errors import PersistenceError
from app.domain.game import PlayerState
from app.domain.journeys import unmetered_journey
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameStateRepository
from app.repositories.preferences import SqlitePreferenceStore
from app.repositories.relational_traffic import (
    TRAFFIC_FROM_SQL,
    SqliteTrafficReader,
)
from app.repositories.runtime_views import SqliteRuntimeReader


def seed_public_transports(relational, synthetic_game) -> None:
    """Persist two active trips with deterministic departure ordering."""
    vehicle = synthetic_game.state_repository.list_vehicles()[0]
    vehicle.start_trip()
    offer = synthetic_game.state_repository.list_offers()[0]
    route = RouteSnapshot(((1, 1), (2, 2)), 3, 10, "fixture")
    trip = ActiveTransport(
        "shared",
        vehicle.id,
        HistoricalContractSnapshot.from_offer(offer),
        offer.origin,
        offer.destination,
        route,
        10,
        20,
        1234,
        100,
        journey=unmetered_journey(route.distance_km, 10),
    )
    alice = SqliteGameStateRepository(relational, "alice")
    bob = SqliteGameStateRepository(relational, "bob")
    for repository in (alice, bob):
        repository.save_player(PlayerState(5000, 5, 5))
        repository.save_vehicle(vehicle)
    alice.save_transport(trip)
    bob.save_transport(
        replace(
            trip,
            id="bob-live",
            departed_at=11,
            arrives_at=30,
            journey=unmetered_journey(3, 19),
        )
    )


def test_public_traffic_limits_latest_rows_and_preserves_privacy(
    relational,
    synthetic_game,
):
    seed_public_transports(relational, synthetic_game)
    reader = SqliteTrafficReader(relational, maximum_transports=1)

    rows = reader.list_active_transports(12)
    summaries = SqliteRuntimeReader(relational, reader).traffic(12)

    assert [row.id for row in rows] == ["bob-live"]
    assert [row.id for row in summaries] == ["bob-live"]
    assert rows[0].coordinates == ((1, 1), (2, 2))
    assert summaries[0].coordinates == ()
    assert {"contract", "password_hash", "cash", "payout_eur"}.isdisjoint(
        asdict(rows[0])
    )


def test_public_traffic_cache_coalesces_clients_and_expires(
    relational,
    synthetic_game,
):
    seed_public_transports(relational, synthetic_game)
    now = [100.0]
    reader = SqliteTrafficReader(
        relational,
        cache_seconds=10,
        cache_clock=lambda: now[0],
    )

    with patch.object(reader, "_query", wraps=reader._query) as query:
        first = reader.list_active_summaries(12)
        assert reader.list_active_summaries(12) is first
        assert query.call_count == 1
        now[0] += 10
        assert reader.list_active_summaries(12) == first
        assert query.call_count == 2


def test_public_traffic_query_uses_active_ordering_index(relational):
    with relational.connect() as connection:
        plan = connection.execute(
            "EXPLAIN QUERY PLAN SELECT t.user_id " + TRAFFIC_FROM_SQL,
            (0, 100),
        ).fetchall()
    details = tuple(row[3] for row in plan)

    assert any("public_active_traffic" in detail for detail in details)
    assert not any("TEMP B-TREE" in detail for detail in details)


def test_public_traffic_schema_initialization_is_explicit(tmp_path):
    database = SqliteGameDatabase(tmp_path / "traffic.db")
    database.initialize()
    store = SqlitePreferenceStore(database)
    with database.connect() as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='account_preferences'"
            ).fetchone()
            is None
        )
    with pytest.raises(PersistenceError):
        SqliteTrafficReader(database).list_active_summaries(0)

    SqlitePreferenceStore.initialize(database)
    SqliteTrafficReader.initialize(database)

    assert store.color("missing") is None
    assert SqliteTrafficReader(database).list_active_summaries(0) == ()


def test_public_traffic_rejects_invalid_limits_and_storage(tmp_path):
    database = SqliteGameDatabase(tmp_path / "missing" / "game.db")
    with pytest.raises(ValueError, match="limit"):
        SqliteTrafficReader(database, maximum_transports=0)
    with pytest.raises(ValueError, match="duration"):
        SqliteTrafficReader(database, cache_seconds=0)
    with pytest.raises(PersistenceError):
        SqliteTrafficReader(database).list_active_transports(1)
