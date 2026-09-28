"""Runtime demand, short transactions and publication fences under races."""

import sqlite3
from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.errors import PersistenceError
from app.domain.market import VehicleCoverageDiagnostic
from app.domain.routing_readiness import RoutePayload
from app.repositories.routing_readiness import decode_route_payload
from app.services.preparation_lease import WORKER_SUBJECT
from tests.test_market_preparation import (
    bind_preparation,
    make_batch,
    require_value,
)
from tests.test_routing_readiness_store import ready_relation, routing_store


def test_wal_read_snapshot_rejects_writes_and_resets_after_failure(database):
    with database.connect() as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 500
    with database.read_transaction(), database.read_transaction():
        with pytest.raises(PersistenceError), database.connect() as db:
            db.execute("UPDATE users SET created_at=1")
    with pytest.raises(RuntimeError), database.read_transaction():
        raise RuntimeError("read failed")
    with database.transaction(), database.read_transaction():
        with database.connect() as db:
            db.execute("UPDATE users SET created_at=2")
    with database.connect() as db:
        assert db.execute("SELECT created_at FROM users").fetchone()[0] == 2


def test_durable_demand_coalesces_and_fences_stale_diagnostics(game, database):
    preparation = bind_preparation(game, database)
    jobs = preparation.jobs
    assert jobs.diagnostics("test-owner") == ()
    preparation.request()
    first = jobs.status("test-owner")
    assert first is not None
    preparation.request()
    assert jobs.status("test-owner") == first
    diagnostic = VehicleCoverageDiagnostic("v", "city", 1, (1, 0, 0), (), ())
    jobs.publish_diagnostics("test-owner", first.generation, (diagnostic,))
    assert jobs.diagnostics("test-owner") == (diagnostic,)
    preparation.request(changed=True)
    second = jobs.status("test-owner")
    assert second is not None and second.generation != first.generation
    jobs.publish_diagnostics("test-owner", first.generation, ())
    jobs.finish("test-owner", first.generation, "ready", None, 5)
    assert jobs.status("test-owner") == second
    assert jobs.diagnostics("test-owner") == (diagnostic,)
    jobs.finish("test-owner", second.generation, "ready", 20, 10)
    jobs.ensure("test-owner", 19)
    assert jobs.next_player(19) is None
    jobs.ensure("test-owner", 20)
    assert require_value(jobs.status("test-owner")).status == "partial"
    assert jobs.next_player(20) == "test-owner"
    jobs.finish("test-owner", second.generation, "partial", 30, 20)
    jobs.ensure("test-owner", 21)
    assert jobs.next_player(21) is None
    assert jobs.next_player(30) == "test-owner"


def test_runtime_never_builds_candidates_and_worker_plans_outside_writer(
    game, database
):
    preparation = bind_preparation(game, database)
    with patch.object(
        type(game.market.candidates),
        "build",
        side_effect=AssertionError("Runtime planned"),
    ):
        assert game.list_contracts() == []
        assert game.refresh_contracts() == []
        assert game.market_lifecycle.vehicle_diagnostics() == ()
        game.ensure_initial_state()
        game.reconcile_arrival()
    with patch.object(
        database,
        "transaction",
        side_effect=AssertionError("Read acquired writer"),
    ):
        game.ensure_initial_state()
        game.reconcile_arrival()
        game.list_contracts()
    original = type(game.market.candidates).build

    def build(service, *args):
        # A separate connection can acquire the writer during candidate CPU work.
        with sqlite3.connect(database.path, timeout=0) as concurrent:
            concurrent.execute("BEGIN IMMEDIATE")
            concurrent.rollback()
        return original(service, *args)

    with patch.object(type(game.market.candidates), "build", build):
        make_batch(game, preparation).plan()
    generation = require_value(
        preparation.jobs.status("test-owner")
    ).generation
    with patch.object(
        type(game.market), "generate", wraps=game.market.generate
    ) as generate:
        game.market_lifecycle.publication_guard = lambda: False
        assert game.refresh_market() == []
        generate.assert_called_once()
    assert (
        require_value(preparation.jobs.status("test-owner")).generation
        == generation
    )


@pytest.mark.asyncio
async def test_readiness_read_view_reuses_facts_but_never_crosses_publication(
    game, database
):
    preparation = bind_preparation(game, database)
    readiness = preparation.readiness
    offer = game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    with patch.object(
        readiness.store, "get", wraps=readiness.store.get
    ) as get:
        with readiness.reading(), readiness.reading():
            assert readiness.current(*pair) is None
            assert readiness.current(*pair) is None
            get.assert_called_once()
            assert readiness.fingerprint(*pair) == readiness.fingerprint(*pair)
        assert readiness.current(*pair) is None
        assert get.call_count == 2
    readiness.worker_owner = "worker"
    # Losing global ownership prevents either direction from being published.
    assert await readiness.prepare(*pair) is None
    assert readiness.current(*pair) is None
    assert readiness.store.acquire(
        WORKER_SUBJECT, "worker", game.now(), game.now() + 180
    )
    assert require_value(await readiness.prepare(*pair)).status == "ready"
    with readiness.reading():
        assert require_value(readiness.current(*pair)).status == "ready"
    readiness.provider_identity = "changed"
    assert require_value(readiness.current(*pair)).status == "stale"


def test_payload_validation_cache_detects_changes_and_worker_fences_failure(
    tmp_path,
):
    database, store = routing_store(tmp_path)
    relation = ready_relation()
    payload = RoutePayload(((1, 2), (3, 4)), 5, 6, "provider")
    assert not store.payload_available(relation.reference)
    assert store.acquire(relation.reference.relation_id, "pair", 10, 30)
    assert not store.publish(
        relation, payload, "pair", 11, worker_owner="worker"
    )
    assert store.acquire(WORKER_SUBJECT, "worker", 10, 30)
    assert store.publish(relation, payload, "pair", 11, worker_owner="worker")
    with patch(
        "app.repositories.routing_readiness.decode_route_payload",
        wraps=decode_route_payload,
    ) as decode:
        assert store.payload_available(relation.reference)
        assert store.payload_available(relation.reference)
        decode.assert_called_once()
    # Force the bounded memo through eviction without expensive geometry work.
    for index in range(2047):
        store._validated_payloads[str(index)] = True
    with database.connect() as db:
        db.execute("UPDATE route_cache SET payload='{}'")
    assert not store.payload_available(relation.reference)
    assert len(store._validated_payloads) == 2048
    assert decode_route_payload("[]") is None
    assert decode_route_payload("invalid") is None
    store.release(WORKER_SUBJECT, "worker")
    assert not store.publish(
        replace(relation, status="deterministic_failure"),
        None,
        "pair",
        12,
        worker_owner="worker",
    )


@pytest.mark.asyncio
async def test_publication_revision_change_and_concurrent_arrival_are_fenced(
    game, database, runtime
):
    from app.api.v1.runtime import project_runtime
    from app.bootstrap import build_runtime_reader
    from app.domain.runtime_views import RuntimeView

    offer = game.state_repository.list_offers()[0]
    preparation = bind_preparation(game, database)
    vehicle = game.state_repository.list_vehicles()[0]
    await preparation.readiness.prepare(
        offer.origin.facility_uid, offer.destination.facility_uid
    )
    if vehicle.facility_uid != offer.origin.facility_uid:
        await preparation.readiness.prepare(
            vehicle.facility_uid, offer.origin.facility_uid
        )
    offers = game.refresh_market()
    assert offers
    lifecycle = game.market_lifecycle
    current = lifecycle._publication_evidence
    calls = 0

    def evidence(*args):
        nonlocal calls
        calls += 1
        result = current(*args)
        return (
            result
            if calls == 1
            else tuple(
                replace(item, expected_fingerprint="changed")
                for item in result
            )
        )

    before = game.state_repository.list_offers()
    with (
        patch.object(
            type(lifecycle), "_publication_evidence", side_effect=evidence
        ),
        patch.object(
            type(lifecycle),
            "_store",
            side_effect=AssertionError("Stale publication"),
        ),
    ):
        assert game.refresh_market() == list(before)
    status = require_value(preparation.jobs.status("test-owner"))
    preparation.jobs.finish(
        "test-owner", status.generation, "ready", game.now() + 60, game.now()
    )
    assert game.refresh_contracts()
    assert (
        require_value(preparation.jobs.status("test-owner")).generation
        != status.generation
    )
    trip = await game.dispatch(offers[0].id, vehicle.id)
    reader = build_runtime_reader(runtime)
    view = project_runtime(
        RuntimeView(
            reader.read("test-owner"),
            trip.departed_at + 1,
            game.time_scale,
            game.preparation_status(),
        ),
        "test-owner",
        game.catalogue,
    )
    assert view["vehicles"][0]["energy_level"] <= vehicle.energy_level
    with patch.object(
        game.state_repository, "list_due_transports", side_effect=[(trip,), ()]
    ):
        assert not game.reconcile_arrival()
    game.now = lambda: trip.arrives_at + 1
    assert game.reconcile_arrival()
    assert not game.reconcile_arrival()
    fleet = game.market.candidates.resolve_fleet(
        game.state_repository.list_vehicles()
    )
    candidates = game.market.candidates.build(
        game.market_scope.resolve(game.state_repository.list_vehicles()), fleet
    )
    with patch.object(
        preparation.readiness,
        "current",
        return_value=replace(ready_relation(), status="deterministic_failure"),
    ):
        assert preparation.preparable_candidates(candidates) == ()


def test_two_process_roles_can_initialize_the_same_empty_file(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.repositories.game_database import SqliteGameDatabase

    ready = Barrier(2)
    path = tmp_path / "shared.db"

    def initialize():
        ready.wait(timeout=5)
        SqliteGameDatabase(path).initialize()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(initialize) for _ in range(2)]
        for future in futures:
            future.result(timeout=5)
    with SqliteGameDatabase(path).connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM game_schema").fetchone()[
                0
            ]
            == 1
        )
