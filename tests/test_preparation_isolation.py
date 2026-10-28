"""Runtime demand, short transactions and publication fences under races."""

from unittest.mock import Mock, patch

import pytest

from app.domain.errors import PersistenceError
from app.domain.market import VehicleCoverageDiagnostic
from app.domain.routing_readiness import RoutePayload
from app.repositories.market_preparation import SqlitePreparationStore
from app.repositories.routing_readiness import decode_route_payload
from tests.test_market_preparation import (
    bind_preparation,
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
    jobs = preparation.demand.jobs
    assert isinstance(jobs, SqlitePreparationStore)
    notify = Mock()
    jobs.set_notifier(notify)
    assert jobs.diagnostics("test-owner") == ()
    preparation.demand.request()
    notify.assert_called_once_with()
    first = jobs.status("test-owner")
    assert first is not None
    preparation.demand.request()
    assert notify.call_count == 1
    assert jobs.status("test-owner") == first
    diagnostic = VehicleCoverageDiagnostic("v", "city", 1, (1, 0, 0), (), ())
    jobs.publish_diagnostics("test-owner", first.generation, (diagnostic,))
    assert jobs.diagnostics("test-owner") == (diagnostic,)
    preparation.demand.request(changed=True)
    assert notify.call_count == 2
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
    assert require_value(jobs.status("test-owner")).status == "ready"
    assert jobs.next_player(20) is None
    jobs.finish("test-owner", second.generation, "partial", 30, 20)
    jobs.ensure("test-owner", 21)
    assert jobs.next_player(21) is None
    assert jobs.next_player(30) == "test-owner"


def test_runtime_never_builds_candidates_and_worker_plans_outside_writer(
    game, database
):
    bind_preparation(game, database)
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


@pytest.mark.asyncio
async def test_readiness_read_view_reuses_facts_but_never_crosses_publication(
    game, database
):
    preparation = bind_preparation(game, database)
    readiness = preparation.routes.readiness
    assert readiness.store.get_many(()) == {}
    assert readiness.anchor_store.get_many((), "truck") == {}
    offer = game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    with (
        patch.object(readiness.store, "get", wraps=readiness.store.get) as get,
        patch.object(
            readiness.store,
            "get_many",
            wraps=readiness.store.get_many,
        ) as get_many,
    ):
        with readiness.reading((pair,)), readiness.reading((pair,)):
            assert readiness.current(*pair) is None
            assert readiness.current(*pair) is None
            get.assert_not_called()
            get_many.assert_called_once()
            assert readiness.fingerprint(*pair) == readiness.fingerprint(*pair)
        assert readiness.current(*pair) is None
        get.assert_called_once()
    assert require_value(await readiness.prepare(*pair)).status == "ready"
    with (
        patch.object(
            readiness.store,
            "connected",
            wraps=readiness.store.connected,
        ) as connected,
        patch.object(
            readiness.store,
            "connected_many",
            wraps=readiness.store.connected_many,
        ) as connected_many,
    ):
        with readiness.reading((pair,)):
            assert require_value(readiness.current(*pair)).status == "ready"
            assert require_value(readiness.current(*pair)).status == "ready"
        connected.assert_not_called()
        connected_many.assert_called_once()
    readiness.provider_identity = "changed"
    assert require_value(readiness.current(*pair)).status == "stale"


def test_payload_validation_cache_detects_changes(
    tmp_path,
):
    database, store = routing_store(tmp_path)
    relation = ready_relation()
    payload = RoutePayload(((1, 2), (3, 4)), 5, 6, "provider")
    assert not store.payload_available(relation.reference)
    assert store.acquire(relation.reference.relation_id, "pair", 10, 30)
    assert store.publish(relation, payload, "pair", 11)
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
