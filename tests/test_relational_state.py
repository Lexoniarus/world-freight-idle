"""Relational isolation, historical snapshots and transactional failures."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace

import pytest

from app.domain.contracts import HistoricalContractSnapshot
from app.domain.errors import PersistenceError, UnsupportedGameSchema
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import (
    SqliteGameStateRepository,
    SqliteGameUnitOfWork,
    load_offer_record,
    load_transport_record,
    load_vehicle_record,
)
from app.repositories.state_snapshots import decode_snapshot, encode_snapshot


@pytest.fixture
def relational(tmp_path):
    database = SqliteGameDatabase(tmp_path / "fresh.db")
    database.initialize()
    with database.connect() as connection:
        connection.executemany(
            "INSERT INTO users VALUES (?, ?, ?, ?)",
            [
                ("alice", "Alice", "test-only", 0),
                ("bob", "Bob", "test-only", 1),
            ],
        )
    return database


def test_database_schema_rejects_old_and_unknown_files(tmp_path):
    path = tmp_path / "database.db"
    database = SqliteGameDatabase(path)
    database.initialize()
    database.initialize()
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        connection.execute("UPDATE game_schema SET version='99'")
    with pytest.raises(UnsupportedGameSchema):
        database.initialize()
    with database.connect() as connection:
        connection.execute("DROP TABLE game_schema")
    with pytest.raises(UnsupportedGameSchema):
        database.initialize()
    path.rename(tmp_path / "closed.db")
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE kv(key TEXT, value TEXT)")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(UnsupportedGameSchema):
        database.initialize()
    assert path.read_bytes() == before
    path.write_bytes(b"not SQLite")
    with pytest.raises(PersistenceError):
        database.initialize()
    missing_parent = SqliteGameDatabase(tmp_path / "missing" / "file.db")
    with pytest.raises(PersistenceError):
        with missing_parent.connect():
            pytest.fail("Connection must fail before yielding")


def test_unit_of_work_rolls_back_nested_writes_and_closes(relational):
    unit = SqliteGameUnitOfWork(relational, "alice")
    assert unit.repository.get_player() is None
    with unit.transaction():
        unit.repository.save_player(PlayerState(100, 0, 0))
        with unit.transaction():
            unit.repository.save_player(PlayerState(90, 1, 1))
    assert unit.repository.get_player() == PlayerState(90, 1, 1)
    with pytest.raises(RuntimeError):
        with unit.transaction():
            unit.repository.save_player(PlayerState(1, 5, 5))
            with unit.transaction():
                raise RuntimeError("abort use case")
    assert unit.repository.get_player() == PlayerState(90, 1, 1)
    with pytest.raises(PersistenceError):
        SqliteGameStateRepository(relational, "unknown").save_player(
            PlayerState(1, 0, 0)
        )
    with pytest.raises(ValueError):
        SqliteGameUnitOfWork(relational, "")
    with pytest.raises(PersistenceError):
        with relational.transaction(), relational.connect() as connection:
            connection.execute("SELECT * FROM absent")
    relational.path.rename(relational.path.with_suffix(".closed"))


def test_schema_structure_rejects_missing_columns_and_guards(relational):
    relational.initialize()
    with relational.connect() as connection:
        connection.execute("ALTER TABLE player_states ADD COLUMN stray TEXT")
    with pytest.raises(UnsupportedGameSchema, match="tabellen"):
        relational.initialize()
    with relational.connect() as connection:
        connection.execute("ALTER TABLE player_states DROP COLUMN stray")
        connection.execute("DROP INDEX one_active_transport_per_vehicle")
    with pytest.raises(UnsupportedGameSchema, match="schutz"):
        relational.initialize()


def test_relational_entities_roundtrip_isolate_and_protect_history(
    relational, game
):
    alice = SqliteGameStateRepository(relational, "alice")
    bob = SqliteGameStateRepository(relational, "bob")
    vehicle = game.state_repository.list_vehicles()[0]
    offer = game.state_repository.list_offers()[0]
    route = RouteSnapshot(((13, 52), (9, 53)), 400, 100, "fixture")
    trip = ActiveTransport(
        "trip",
        vehicle.id,
        HistoricalContractSnapshot.from_offer(offer),
        offer.origin,
        offer.destination,
        route,
        10,
        110,
        500,
        100,
    )
    for repository in (alice, bob):
        repository.save_player(PlayerState(1000, 0, 0))
        repository.save_vehicle(vehicle)
        repository.replace_offers((offer,))
        repository.save_transport(trip)
        assert repository.list_vehicles() == (vehicle,)
        assert repository.list_offers() == (offer,)
        assert repository.list_transports() == (trip,)
    with pytest.raises(PersistenceError):
        alice.save_transport(replace(trip, id="duplicate-active"))
    with pytest.raises(PersistenceError):
        alice.save_transport(replace(trip, vehicle_id="foreign"))
    with pytest.raises(PersistenceError):
        alice.replace_offers((offer, offer))
    assert alice.list_offers() == (offer,)
    with pytest.raises(PersistenceError):
        alice.save_transport(trip)
    with pytest.raises(PersistenceError):
        alice.save_transport(replace(trip.settle(110), payout_eur=999))
    vehicle.start_trip()
    alice.save_vehicle(vehicle)
    vehicle.arrive(offer.destination)
    alice.save_vehicle(vehicle)
    settled = trip.settle(110)
    alice.save_transport(settled)
    assert alice.list_transports() == (settled,)
    assert bob.list_transports() == (trip,)
    with pytest.raises(PersistenceError):
        alice.save_transport(trip)
    with pytest.raises(PersistenceError):
        alice.save_transport(settled)
    with pytest.raises(PersistenceError):
        with relational.connect() as connection:
            connection.execute(
                "UPDATE transports SET status='active', settled_at=NULL "
                "WHERE user_id='alice'"
            )
    alice.remove_offer("missing")
    alice.remove_offer(offer.id)
    assert alice.list_offers() == ()
    assert bob.list_offers() == (offer,)
    alice.save_vehicle(
        OwnedVehicle(
            "legacy", "Old", "truck", 12, offer.origin.facility_uid, "idle"
        )
    )
    assert alice.list_vehicles()[-1].location is None
    with pytest.raises(RuntimeError):
        with relational.transaction():
            alice.reset()
            raise RuntimeError("rollback reset")
    assert len(alice.list_vehicles()) == 2
    alice.reset()
    assert alice.get_player() is None
    assert alice.list_vehicles() == alice.list_offers() == ()
    assert alice.list_transports() == ()
    assert bob.get_player() == PlayerState(1000, 0, 0)


def test_snapshot_envelopes_and_corrupt_records_fail_explicitly(
    relational, game
):
    assert decode_snapshot("sample", encode_snapshot("sample", {"x": 1})) == {
        "x": 1
    }
    for data in ({"x": float("nan")}, {"x": object()}):
        with pytest.raises(PersistenceError):
            encode_snapshot("sample", data)
    for encoded in (
        "not json",
        "[]",
        '{"version":2}',
        '{"version":true,"kind":"sample","data":{}}',
        '{"version":1,"kind":"other","data":{}}',
        '{"version":1,"kind":"sample","data":[]}',
    ):
        with pytest.raises(PersistenceError):
            decode_snapshot("sample", encoded)
    repository = SqliteGameStateRepository(relational, "alice")
    repository.save_player(PlayerState(1, 0, 0))
    vehicle = game.state_repository.list_vehicles()[0]
    offer = game.state_repository.list_offers()[0]
    repository.save_vehicle(vehicle)
    repository.replace_offers((offer,))
    trip = ActiveTransport(
        "t",
        vehicle.id,
        HistoricalContractSnapshot.from_offer(offer),
        offer.origin,
        offer.destination,
        RouteSnapshot(((1, 1), (2, 2)), 1, 1, "fake"),
        1,
        2,
        5,
        1,
    )
    repository.save_transport(trip)
    with relational.connect() as connection:
        for table, loader, column in (
            ("owned_vehicles", load_vehicle_record, "capacity_tons"),
            ("contract_offers", load_offer_record, "market_model"),
            ("transports", load_transport_record, "payout_eur"),
        ):
            row = dict(connection.execute(f"SELECT * FROM {table}").fetchone())
            with pytest.raises(PersistenceError):
                loader({**row, column: -1})
            with pytest.raises(PersistenceError):
                loader({})
        connection.execute(
            "UPDATE contract_offers SET offer_snapshot=?",
            (json.dumps({"version": 1, "kind": "offer", "data": {}}),),
        )
    with pytest.raises(PersistenceError):
        repository.list_offers()


def test_concurrent_units_serialize_player_debits(relational):
    unit = SqliteGameUnitOfWork(relational, "alice")
    unit.repository.save_player(PlayerState(100, 0, 0))

    def debit_once():
        other = SqliteGameUnitOfWork(relational, "alice")
        with other.transaction():
            player = other.repository.get_player()
            assert player is not None
            if player.cash < 80:
                return False
            player.debit(80)
            other.repository.save_player(player)
            return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: debit_once(), range(2))) == [
            False,
            True,
        ]
    assert unit.repository.get_player() == PlayerState(20, 0, 0)


def test_corrupt_player_values_are_normalized_at_repository_boundary(
    relational,
):
    repository = SqliteGameStateRepository(relational, "alice")
    repository.save_player(PlayerState(100, 0, 0))
    with relational.connect() as connection:
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(
            "UPDATE player_states SET cash=-1 WHERE user_id='alice'"
        )
    with pytest.raises(PersistenceError, match="Spielerwerte"):
        repository.get_player()
