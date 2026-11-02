"""Real Wolfsburg regression and atomic bidirectional readiness invariants."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.errors import RoutingError
from app.domain.geography import Coordinates
from app.domain.routing_anchors import (
    POSITIVE_TTL,
)
from app.domain.routing_connections import (
    anchor_identity,
)
from app.domain.routing_readiness import relation_identity
from tests.support.catalogues import (
    BERLIN_UID,
)
from tests.support.routing import (
    FakeRouter,
)
from tests.support.routing_cases import build_routing_test_case

ORIGIN = BERLIN_UID
DESTINATION = "10000000-0000-4000-8000-000000000003"
REFERENCE_ORIGIN = "53e47547-aa34-4234-a41c-4fe81bb86290"
REFERENCE_DESTINATION = "18e6c54b-658c-4a10-ab92-d518bca060f7"


@pytest.fixture
def case(tmp_path, synthetic_world_catalogue):
    return build_routing_test_case(tmp_path, synthetic_world_catalogue)


@pytest.mark.asyncio
async def test_route_certificates_outlive_payloads_but_versions_invalidate(
    case,
):
    first = await case.service.prepare(ORIGIN, DESTINATION)
    assert first.status == "ready"
    for sql in (
        "UPDATE routing_connection_proofs SET validation_version='old'",
        "UPDATE routing_relations SET fingerprint='legacy-locate'",
    ):
        with case.db.connect() as conn:
            conn.execute(sql)
        assert case.service.current(ORIGIN, DESTINATION).status == "stale"
        assert (
            await case.service.prepare(ORIGIN, DESTINATION)
        ).status == "ready"
    with case.db.connect() as conn:
        conn.execute(
            "DELETE FROM route_cache WHERE cache_key IN "
            "(SELECT cache_key FROM routing_relations "
            "WHERE origin_uid=?)",
            (ORIGIN,),
        )
    assert case.service.current(ORIGIN, DESTINATION).status == "ready"
    with pytest.raises(ValueError, match="vorbereitet"):
        case.service.load(ORIGIN, DESTINATION)
    case.clock[0] += POSITIVE_TTL * 2
    assert case.service.current(ORIGIN, DESTINATION).status == "ready"
    with case.db.connect() as conn:
        conn.execute("DELETE FROM routing_connection_proofs")
        conn.execute("DELETE FROM routing_relations")
    error = RoutingError("no road")
    error.category = "no_path"
    case.service.router = SimpleNamespace(route=AsyncMock(side_effect=error))
    failure = await case.service.prepare(ORIGIN, DESTINATION)
    assert failure.retry_at == case.clock[0] + 3600
    assert await case.service.prepare(ORIGIN, DESTINATION) == failure
    case.clock[0] += 3600
    assert case.service.current(ORIGIN, DESTINATION).status == "stale"
    error.category = "provider_unavailable"
    transient = await case.service.prepare(ORIGIN, DESTINATION)
    assert transient.retry_at == case.clock[0] + 60
    assert await case.service.prepare(ORIGIN, DESTINATION) == transient
    case.clock[0] += 60
    case.service.router = FakeRouter()
    assert (await case.service.prepare(ORIGIN, DESTINATION)).status == "ready"


@pytest.mark.asyncio
async def test_reverse_requests_cancellation_and_expired_leases(case):
    entered, release = asyncio.Event(), asyncio.Event()
    router = FakeRouter()

    async def route(*args):
        entered.set()
        await release.wait()
        return await router.route(*args)

    case.service.router = SimpleNamespace(route=route)
    task = asyncio.create_task(case.service.prepare(ORIGIN, DESTINATION))
    await entered.wait()
    assert await case.service.prepare(DESTINATION, ORIGIN) is None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with case.db.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM routing_leases").fetchone()[0]
            == 0
        )
        assert (
            conn.execute("SELECT count(*) FROM routing_relations").fetchone()[
                0
            ]
            == 0
        )
    entered.clear()
    task = asyncio.create_task(case.service.prepare(ORIGIN, DESTINATION))
    await entered.wait()
    case.clock[0] += 200
    release.set()
    assert await task is None
    assert case.anchors.get(ORIGIN, "truck") is None


@pytest.mark.asyncio
async def test_connection_publication_rolls_back_both_directions_and_anchors(
    case,
):
    original = case.store.relations.publish
    calls = []

    def failing_publish(*args):
        calls.append(args)
        if len(calls) == 2:
            return False
        return original(*args)

    with patch.object(
        case.store.relations,
        "publish",
        side_effect=failing_publish,
    ):
        with pytest.raises(RuntimeError, match="lost its lease"):
            await case.service.prepare(ORIGIN, DESTINATION)
    assert case.anchors.get(ORIGIN, "truck") is None
    assert case.store.get(relation_identity(ORIGIN, DESTINATION)) is None
    assert case.store.get(relation_identity(DESTINATION, ORIGIN)) is None
    with case.db.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM route_cache").fetchone()[0] == 0
        )


@pytest.mark.asyncio
async def test_inputs_changed_during_await_cannot_publish(case):
    router = FakeRouter()

    async def changed(*args):
        case.service.provider_identity = "changed"
        return await router.route(*args)

    case.service.router = SimpleNamespace(route=changed)
    assert await case.service.prepare(ORIGIN, DESTINATION) is None
    assert case.anchors.get(ORIGIN, "truck") is None
    case.service.timeout = 0.001

    async def slow(*args):
        await asyncio.sleep(10)

    case.service.router = SimpleNamespace(route=slow)
    assert (
        await case.service.prepare(ORIGIN, DESTINATION)
    ).status == "transient_failure"


@pytest.mark.asyncio
async def test_timeout_after_input_change_does_not_publish_negative(case):
    async def changed_then_slow(*args):
        case.service.provider_identity = "changed-while-waiting"
        await asyncio.sleep(10)

    case.service.timeout = 0.01
    case.service.router = SimpleNamespace(route=changed_then_slow)
    assert await case.service.prepare(ORIGIN, DESTINATION) is None
    assert case.store.get(relation_identity(ORIGIN, DESTINATION)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["anchor", "graph"])
async def test_commit_rechecks_anchor_and_graph_inside_transaction(
    case, changed
):
    publish = case.store.publish_connection

    def change_before_commit(connection, *args, **kwargs):
        if changed == "anchor":
            case.anchors.put(replace(connection.origin, validated_at=99))
        else:
            case.store.observe_provider_revision("fake", "new")
        return publish(connection, *args, **kwargs)

    with patch.object(
        case.store, "publish_connection", side_effect=change_before_commit
    ):
        assert await case.service.prepare(ORIGIN, DESTINATION) is None
    assert case.store.get(relation_identity(ORIGIN, DESTINATION)) is None
    assert case.store.get(relation_identity(DESTINATION, ORIGIN)) is None


@pytest.mark.asyncio
async def test_anchor_fingerprints_survive_sqlite_numeric_normalization(case):
    await case.service.prepare(ORIGIN, DESTINATION)
    anchor = case.anchors.get(ORIGIN, "truck")
    integer = replace(
        anchor,
        anchor=Coordinates(50, 13),
        facility_coordinates=Coordinates(50, 13),
    )
    case.anchors.put(integer)
    assert anchor_identity(integer) == anchor_identity(
        case.anchors.get(ORIGIN, "truck")
    )
    assert anchor_identity(integer) != anchor_identity(anchor)
