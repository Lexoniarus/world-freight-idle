"""Global routing storage must not alter the strict player-state schema."""

from dataclasses import replace

import pytest

from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingAttempt,
    RoutingRelation,
    relation_identity,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_readiness import (
    SqliteOfferRouteStore,
    SqliteRoutingReadinessStore,
)


def routing_store(tmp_path):
    database = SqliteGameDatabase(tmp_path / "game.db")
    database.initialize()
    SqliteProviderCache(database)
    return database, SqliteRoutingReadinessStore(database)


def ready_relation():
    return RoutingRelation(
        RouteReference(relation_identity("A", "B"), "revision"),
        "A",
        "B",
        "fingerprint",
        "ready",
        "routing:v2:test",
        None,
        None,
        10,
    )


def test_readiness_domain_rejects_incoherent_records():
    assert relation_identity("A", "B") != relation_identity("B", "A")
    with pytest.raises(ValueError):
        relation_identity("", "B")
    with pytest.raises(ValueError):
        RouteReference("relation", "")
    payload = RoutePayload(((1, 2), (3, 4)), 5, 6, "provider")
    assert payload.to_snapshot().duration_seconds == 6
    with pytest.raises(ValueError):
        replace(payload, road_distance_km=0)
    relation = ready_relation()
    for change in (
        {"status": "unknown"},
        {"origin_uid": "other"},
        {"cache_key": None},
        {"failure_category": "no_path"},
        {"retry_at": 20},
        {"status": "stale"},
        {"checked_at": float("nan")},
    ):
        with pytest.raises(ValueError):
            replace(relation, **change)
    assert (
        replace(
            relation, status="transient_failure", cache_key=None, retry_at=20
        ).retry_at
        == 20
    )
    with pytest.raises(ValueError):
        RoutingAttempt("A", "locate", "ready", 1, "trace", 1, None)
    with pytest.raises(ValueError):
        RoutingAttempt("", "locate", "ready", 1, "trace")


def test_global_lease_fences_expired_and_competing_writers(tmp_path):
    database, store = routing_store(tmp_path)
    other = SqliteRoutingReadinessStore(database)
    relation = ready_relation()
    key = relation.reference.relation_id
    payload = RoutePayload(((1, 2), (3, 4)), 5, 6, "provider")
    assert store.get(key) is None
    assert store.payload(relation.reference) is None
    with pytest.raises(ValueError):
        store.acquire(key, "a", 10, 10)
    with pytest.raises(ValueError):
        store.renew(key, "a", 10, 9)
    assert store.acquire(key, "a", 10, 20)
    assert not other.acquire(key, "b", 11, 21)
    assert not other.renew(key, "b", 11, 30)
    assert store.renew(key, "a", 11, 30)
    other.release(key, "b")
    assert not other.publish(relation, payload, "b", 12)
    with pytest.raises(ValueError):
        store.publish(relation, None, "a", 12)
    assert store.publish(relation, payload, "a", 12)
    assert other.get(key) == relation
    assert other.payload(relation.reference) == payload
    assert other.acquire(key, "b", 31, 40)
    assert not store.publish(relation, payload, "a", 32)
    assert not store.renew(key, "a", 32, 50)
    failure = replace(
        relation,
        status="deterministic_failure",
        cache_key=None,
        failure_category="no_path",
    )
    assert other.publish(failure, None, "b", 33)
    assert store.payload(relation.reference) is None
    other.release(key, "b")
    assert store.acquire(key, "c", 34, 50)
    assert store.publish(relation, payload, "c", 35)
    with database.connect() as conn:
        conn.execute("UPDATE route_cache SET payload='{}'")
    assert store.payload(relation.reference) is None
    database.initialize()


def test_attempt_history_and_offer_reference_atomicity(tmp_path):
    database, store = routing_store(tmp_path)
    for outcome in ("no_truck_edge", "snap_too_far", "validated"):
        store.append_attempt(RoutingAttempt("A", "locate", outcome, 1, "t"))
    with database.connect() as conn:
        assert [
            r[0]
            for r in conn.execute(
                "SELECT outcome FROM routing_attempts ORDER BY attempt_id"
            )
        ] == ["no_truck_edge", "snap_too_far", "validated"]
        conn.execute("INSERT INTO users VALUES ('u','u','hash',0)")
        conn.execute("INSERT INTO player_states VALUES ('u',0,0,0)")
        conn.execute(
            "INSERT INTO contract_offers VALUES "
            "('u','offer','A','B',0,100,'nhm_v2','{}')"
        )
    refs = SqliteOfferRouteStore(database, "u")
    foreign = SqliteOfferRouteStore(database, "other")
    assert refs.get("missing") is None
    reference = ready_relation().reference
    with database.transaction():
        refs.replace((("offer", reference),))
    assert refs.get("offer") == reference
    assert foreign.get("offer") is None
    with pytest.raises(RuntimeError), database.transaction():
        refs.replace(())
        raise RuntimeError("rollback")
    assert refs.get("offer") == reference
    with database.connect() as conn:
        conn.execute("DELETE FROM contract_offers WHERE contract_id='offer'")
    assert refs.get("offer") is None


def test_anchor_publication_rejects_expired_owner(tmp_path):
    from app.domain.geography import Coordinates
    from app.domain.routing_anchors import RoutingAnchor
    from app.repositories.routing_anchors import SqliteRoutingAnchorRepository

    database, store = routing_store(tmp_path)
    anchors = SqliteRoutingAnchorRepository(database)
    anchor = RoutingAnchor(
        "A",
        "truck",
        Coordinates(50, 10),
        "facility_coordinate",
        Coordinates(50, 10),
        0,
        "validated",
        "test",
        None,
        1,
    )
    assert not anchors.put_leased(anchor, "owner", 1)
    assert store.acquire("anchor:A:truck", "owner", 1, 3)
    assert anchors.put_leased(anchor, "owner", 2)
    assert not anchors.put_leased(anchor, "owner", 3)
    assert anchors.get("A", "truck") == anchor
