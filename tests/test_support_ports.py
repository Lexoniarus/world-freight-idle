"""Relational public reads and provider cache boundaries."""

from dataclasses import asdict, replace

import pytest

from app.domain.contracts import HistoricalContractSnapshot
from app.domain.errors import DuplicateAccountError, PersistenceError
from app.domain.game import PlayerState
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.repositories.accounts import AccountRepository
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameStateRepository
from app.repositories.leaderboard import SqliteLeaderboardReader
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.relational_traffic import SqliteTrafficReader
from tests.test_relational_state import relational as relational


def test_relational_public_reads_preserve_privacy_and_offline_progress(
    relational, game
):
    ranking = SqliteLeaderboardReader(relational)
    traffic = SqliteTrafficReader(relational)
    assert traffic.list_active_transports(12) == ()
    assert len(ranking.list_ranking(12)) == 2
    vehicle = game.state_repository.list_vehicles()[0]
    vehicle.start_trip()
    offer = game.state_repository.list_offers()[0]
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
    )
    alice = SqliteGameStateRepository(relational, "alice")
    bob = SqliteGameStateRepository(relational, "bob")
    for repository in (alice, bob):
        repository.save_player(PlayerState(5000, 5, 5))
        repository.save_vehicle(vehicle)
    alice.save_transport(trip)
    bob.save_transport(replace(trip, id="bob-live", arrives_at=30))
    rows = traffic.list_active_transports(12)
    assert len(rows) == 2
    assert {row.user_id for row in rows} == {"alice", "bob"}
    for row in rows:
        assert {"contract", "password_hash", "cash", "payout_eur"}.isdisjoint(
            asdict(row)
        )
        assert row.vehicle_id == vehicle.id
        assert row.coordinates == ((1, 1), (2, 2))
    assert ranking.list_ranking(21)[0] == {"username": "Alice", "completed": 6}
    assert len(traffic.list_active_transports(21)) == 1
    with relational.transaction():
        alice.save_transport(trip.settle(21))
        player = alice.get_player()
        assert player is not None
        player.complete_delivery(trip.payout_eur)
        alice.save_player(player)
    assert ranking.list_ranking(21)[0]["completed"] == 6
    assert ranking.list_ranking(31)[1]["completed"] == 6
    with relational.connect() as connection:
        connection.execute(
            "UPDATE transports SET transport_snapshot='{}' WHERE user_id='bob'"
        )
    with pytest.raises(PersistenceError):
        traffic.list_active_transports(12)
    assert traffic.list_active_transports(31) == ()


def test_relational_account_adapter_exposes_domain_uniqueness(relational):
    accounts = AccountRepository(relational)
    user = accounts.create_user("Carol", "unchanged-test-hash")
    assert set(user) == {"id", "username"}
    saved = accounts.find_user("carol")
    assert saved is not None
    assert saved["password_hash"] == "unchanged-test-hash"
    with pytest.raises(DuplicateAccountError):
        accounts.create_user("CAROL", "different")
    assert accounts.find_user("Carol") == saved
    accounts.save_session("test-token", user["id"], 30)
    assert accounts.session_user("test-token") == user
    accounts.revoke_session("test-token")
    assert accounts.session_user("test-token") is None


def test_provider_cache_roundtrip_replaces_invalid_documents(
    relational, tmp_path, caplog
):
    caplog.set_level("WARNING", logger="app.repositories.provider_cache")
    cache = SqliteProviderCache(relational)
    assert cache.get_route("absent") is None
    assert cache.get_geocode("absent") is None
    cache.put_route("route", {"distance_km": 1})
    cache.put_route("route", {"distance_km": 2})
    assert cache.get_route("route") == {"distance_km": 2}
    with pytest.raises(PersistenceError):
        cache.put_route("route", {"distance_km": float("nan")})
    assert cache.get_route("route") == {"distance_km": 2}
    with relational.connect() as connection:
        connection.execute("UPDATE route_cache SET payload='not json'")
    assert cache.get_route("route") is None
    assert any(
        getattr(record, "event", None) == "cache.invalid_route"
        for record in caplog.records
    )
    cache.put_route("route", {"distance_km": 3})
    assert cache.get_route("route") == {"distance_km": 3}
    cache.put_geocode("address", 52, 13, "First")
    cache.put_geocode("address", 53, 14, "Second")
    found = cache.get_geocode("address")
    assert found is not None and found["display_name"] == "Second"
    assert (found["lat"], found["lon"]) == (53, 14)
    bad = SqliteGameDatabase(tmp_path / "missing" / "file.db")
    with pytest.raises(PersistenceError):
        SqliteProviderCache(bad)
    with pytest.raises(PersistenceError):
        SqliteLeaderboardReader(bad).list_ranking(1)
    with pytest.raises(PersistenceError):
        SqliteTrafficReader(bad).list_active_transports(1)
