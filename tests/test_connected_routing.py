"""Real Wolfsburg regression and atomic bidirectional readiness invariants."""

import asyncio
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.domain.errors import RoutingError
from app.domain.geography import Coordinates
from app.domain.routing_anchors import (
    POSITIVE_TTL,
    RoutingCandidate,
    distance_m,
)
from app.domain.routing_connections import (
    anchor_identity,
    connection_identity,
    connection_leases,
)
from app.domain.routing_readiness import relation_identity
from app.domain.world_scopes import WorldScope
from app.providers.request_limiter import ProviderRequestLimiter
from app.providers.routing import ValhallaTruckRouter
from app.providers.routing_anchor import ValhallaTruckAnchorLocator
from app.repositories.cached_world_catalogue import CachedWorldCatalogue
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.provider_cache import SqliteProviderCache
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository
from app.repositories.routing_readiness import SqliteRoutingReadinessStore
from app.repositories.world_catalogue import SqliteWorldCatalogue
from app.services.routing_anchors import RoutingAnchorResolver
from app.services.routing_connections import RoutingConnectionValidator
from app.services.routing_readiness import RoutingReadinessService
from tests.conftest import WORLD_PATH, FakeRouter, FakeRoutingAnchorResolver
from tests.test_routing_anchors import FakeGeocoder, FakeLocator

WOLF = "53e47547-aa34-4234-a41c-4fe81bb86290"
STENDAL = "18e6c54b-658c-4a10-ab92-d518bca060f7"


@pytest.fixture(scope="module")
def connection_world():
    world = CachedWorldCatalogue(SqliteWorldCatalogue(WORLD_PATH))
    world.read()
    return world


@pytest.fixture
def case(tmp_path, connection_world):
    database = SqliteGameDatabase(tmp_path / "game.db")
    database.initialize()
    cache = SqliteProviderCache(database)
    store = SqliteRoutingReadinessStore(database)
    anchors = SqliteRoutingAnchorRepository(database)
    clock = [100.0]
    service = RoutingReadinessService(
        store,
        FakeRoutingAnchorResolver(),
        anchors,
        FakeRouter(),
        connection_world,
        "fake",
        lambda: clock[0],
    )
    return SimpleNamespace(
        db=database,
        cache=cache,
        store=store,
        anchors=anchors,
        clock=clock,
        service=service,
    )


@pytest.mark.asyncio
async def test_wolfsburg_real_candidates_recover_without_changing_facility(
    case,
):
    fixture = json.loads(
        (
            Path(__file__).parent / "fixtures" / "wolfsburg-routing.json"
        ).read_text()
    )
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append((request.url.path, body))
        if request.url.path == "/locate":
            if body["locations"][0]["lon"] < 11:
                return httpx.Response(200, json=fixture["locate"]["response"])
            return httpx.Response(
                200,
                json=[
                    {
                        "edges": [
                            {
                                "correlated_lat": 52.605959,
                                "correlated_lon": 11.85784,
                                "edge": {"access": {"truck": True}},
                            }
                        ]
                    }
                ],
            )
        start, end = body["locations"]
        if start["lon"] < 11:
            key = (
                "anchor_to_stendal"
                if start["lat"] > 52.43
                else "historic_endpoint_to_stendal"
            )
        else:
            key = (
                "stendal_to_anchor"
                if end["lat"] > 52.43
                else "stendal_to_historic_endpoint"
            )
        recorded = fixture[key]
        return httpx.Response(recorded["status"], json=recorded["response"])

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as client:
        limiter = ProviderRequestLimiter(1, 0)
        case.service.router = ValhallaTruckRouter(
            case.cache,
            client,
            "https://fixture.test",
            "test",
            limiter,
            cache_enabled=False,
        )
        locator = ValhallaTruckAnchorLocator(
            client, "https://fixture.test", "test", limiter
        )
        case.service.anchors = RoutingAnchorResolver(
            case.anchors,
            locator,
            FakeGeocoder(),
            1000,
            lambda: case.clock[0],
            case.store,
        )
        ready = await case.service.prepare(WOLF, STENDAL)
        assert ready.status == "ready"
        anchor = case.anchors.get(WOLF, "truck")
        assert 503 < anchor.snap_distance_m < 505
        assert anchor.anchor == Coordinates(52.429326, 10.780732)
        assert case.service.ready(STENDAL, WOLF)
        assert case.service.load(WOLF, STENDAL).road_distance_km == 143.915
        assert case.service.load(STENDAL, WOLF).road_distance_km == 143.496
        count = len(calls)
        assert (await case.service.prepare(STENDAL, WOLF)).status == "ready"
        assert len(calls) == count
        assert WorldScope(case.service.world.read()).facility(
            WOLF
        ).coordinates == Coordinates(52.433806, 10.779611)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "return",
        "wrong_start",
        "wrong_end",
        "return_wrong_start",
        "return_wrong_end",
        "rate_limit",
    ],
)
async def test_no_direction_is_published_without_matching_return_geometry(
    case, failure
):
    router = FakeRouter()

    async def route(*coordinates):
        start_lat, start_lon, end_lat, end_lon = coordinates
        if failure == "return" and start_lon > 11:
            error = RoutingError("no return")
            error.category = "no_path"
            raise error
        if failure == "rate_limit" and start_lon > 11:
            error = RoutingError("provider rate limit")
            error.provider_code = 429
            raise error
        result = await router.route(*coordinates)
        if failure == "wrong_start" or (
            failure == "return_wrong_start" and start_lon > 11
        ):
            return replace(
                result, coordinates=((10, 50), result.coordinates[-1])
            )
        if failure == "wrong_end" or (
            failure == "return_wrong_end" and start_lon > 11
        ):
            return replace(
                result, coordinates=(result.coordinates[0], (10, 50))
            )
        return result

    case.service.router = SimpleNamespace(route=route)
    result = await case.service.prepare(WOLF, STENDAL)
    assert result.status == (
        "transient_failure"
        if failure == "rate_limit"
        else "deterministic_failure"
    )
    assert not case.service.ready(WOLF, STENDAL)
    assert not case.service.ready(STENDAL, WOLF)
    assert case.anchors.get(WOLF, "truck") is None
    with case.db.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM routing_connection_proofs"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.asyncio
async def test_shifted_success_endpoint_tries_next_real_candidate(case):
    scope = WorldScope(case.service.world.read())
    origin = scope.facility(WOLF)
    original = origin.coordinates
    assert original is not None
    shifted = Coordinates(original.latitude - 0.0045, original.longitude)
    anchors = FakeRoutingAnchorResolver()
    resolve = anchors.resolve
    router = FakeRouter()

    async def candidates(facility, *, force=False):
        result = await resolve(facility, force=force)
        assert result
        return (
            result + (replace(result[0], coordinates=shifted, distance_m=500),)
            if facility.facility_uid == WOLF
            else result
        )

    async def wrong_success(*points):
        route = await router.route(*points)
        if points[:2] == (original.latitude, original.longitude):
            return replace(
                route,
                coordinates=(
                    (shifted.longitude, shifted.latitude),
                    route.coordinates[-1],
                ),
            )
        return route

    with patch.object(anchors, "resolve", side_effect=candidates):
        case.service.anchors = anchors
        case.service.router = SimpleNamespace(route=wrong_success)
        assert (await case.service.prepare(WOLF, STENDAL)).status == "ready"
    assert case.anchors.get(WOLF, "truck").anchor == shifted


@pytest.mark.asyncio
async def test_connection_deadline_is_transient_for_direct_planning(case):
    scope = WorldScope(case.service.world.read())
    validator = RoutingConnectionValidator()
    with patch.object(validator, "_search", side_effect=TimeoutError):
        with pytest.raises(RoutingError) as failure:
            await validator.validate(
                scope.facility(WOLF),
                scope.facility(STENDAL),
                case.service.router,
                case.service.anchors,
                lambda: 1,
            )
    assert failure.value.category == "provider_unavailable"


@pytest.mark.asyncio
async def test_cache_versions_ttls_and_broken_reverse_evidence(case):
    first = await case.service.prepare(WOLF, STENDAL)
    assert first.status == "ready"
    for sql in [
        "UPDATE routing_connection_proofs SET validation_version='old'",
        "UPDATE routing_relations SET fingerprint='legacy-locate'",
        "DELETE FROM route_cache WHERE cache_key IN (SELECT cache_key FROM routing_relations WHERE origin_uid='"
        + STENDAL
        + "')",
        "DELETE FROM routing_relations WHERE origin_uid='" + STENDAL + "'",
    ]:
        with case.db.connect() as conn:
            conn.execute(sql)
        assert case.service.current(WOLF, STENDAL).status == "stale"
        assert (await case.service.prepare(WOLF, STENDAL)).status == "ready"
    case.clock[0] += POSITIVE_TTL
    assert case.service.current(WOLF, STENDAL).status == "stale"
    assert (await case.service.prepare(WOLF, STENDAL)).status == "ready"
    case.clock[0] += POSITIVE_TTL
    error = RoutingError("no road")
    error.category = "no_path"
    case.service.router = SimpleNamespace(route=AsyncMock(side_effect=error))
    failure = await case.service.prepare(WOLF, STENDAL)
    assert failure.retry_at == case.clock[0] + 3600
    assert await case.service.prepare(WOLF, STENDAL) == failure
    case.clock[0] += 3600
    assert case.service.current(WOLF, STENDAL).status == "stale"
    error.category = "provider_unavailable"
    transient = await case.service.prepare(WOLF, STENDAL)
    assert transient.retry_at == case.clock[0] + 60
    assert await case.service.prepare(WOLF, STENDAL) == transient
    case.clock[0] += 60
    case.service.router = FakeRouter()
    assert (await case.service.prepare(WOLF, STENDAL)).status == "ready"


@pytest.mark.asyncio
async def test_reverse_requests_cancellation_and_expired_leases(case):
    entered, release = asyncio.Event(), asyncio.Event()
    router = FakeRouter()

    async def route(*args):
        entered.set()
        await release.wait()
        return await router.route(*args)

    case.service.router = SimpleNamespace(route=route)
    task = asyncio.create_task(case.service.prepare(WOLF, STENDAL))
    await entered.wait()
    assert await case.service.prepare(STENDAL, WOLF) is None
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
    task = asyncio.create_task(case.service.prepare(WOLF, STENDAL))
    await entered.wait()
    case.clock[0] += 200
    release.set()
    assert await task is None
    assert case.anchors.get(WOLF, "truck") is None


@pytest.mark.asyncio
async def test_connection_publication_rolls_back_both_directions_and_anchors(
    case,
):
    original = case.store.publish
    calls = []

    def failing_publish(*args):
        calls.append(args)
        if len(calls) == 2:
            return False
        return original(*args)

    with patch.object(case.store, "publish", side_effect=failing_publish):
        with pytest.raises(RuntimeError, match="lost its lease"):
            await case.service.prepare(WOLF, STENDAL)
    assert case.anchors.get(WOLF, "truck") is None
    assert case.store.get(relation_identity(WOLF, STENDAL)) is None
    assert case.store.get(relation_identity(STENDAL, WOLF)) is None
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
    assert await case.service.prepare(WOLF, STENDAL) is None
    assert case.anchors.get(WOLF, "truck") is None
    case.service.timeout = 0.001

    async def slow(*args):
        await asyncio.sleep(10)

    case.service.router = SimpleNamespace(route=slow)
    assert (
        await case.service.prepare(WOLF, STENDAL)
    ).status == "transient_failure"


@pytest.mark.asyncio
async def test_timeout_after_input_change_does_not_publish_negative(case):
    async def changed_then_slow(*args):
        case.service.provider_identity = "changed-while-waiting"
        await asyncio.sleep(10)

    case.service.timeout = 0.01
    case.service.router = SimpleNamespace(route=changed_then_slow)
    assert await case.service.prepare(WOLF, STENDAL) is None
    assert case.store.get(relation_identity(WOLF, STENDAL)) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["anchor", "graph"])
async def test_commit_rechecks_anchor_and_graph_inside_transaction(
    case, changed
):
    publish = case.store.publish_connection

    def change_before_commit(connection, *args):
        if changed == "anchor":
            case.anchors.put(replace(connection.origin, validated_at=99))
        else:
            case.store.observe_provider_revision("fake", "new")
        return publish(connection, *args)

    with patch.object(
        case.store, "publish_connection", side_effect=change_before_commit
    ):
        assert await case.service.prepare(WOLF, STENDAL) is None
    assert case.store.get(relation_identity(WOLF, STENDAL)) is None
    assert case.store.get(relation_identity(STENDAL, WOLF)) is None


@pytest.mark.asyncio
async def test_certified_anchors_stay_fixed_for_unreachable_destination(case):
    await case.service.prepare(WOLF, STENDAL)
    before = case.anchors.get(WOLF, "truck")
    locator = FakeLocator([])
    resolver = RoutingAnchorResolver(
        case.anchors,
        locator,
        FakeGeocoder(),
        1000,
        lambda: case.clock[0],
    )
    case.service.anchors = resolver
    error = RoutingError("remote endpoint has no return")
    error.category = "no_path"
    case.service.router = SimpleNamespace(route=AsyncMock(side_effect=error))
    # A different provider identity expires the relation, not the access.
    case.service.provider_identity = "retry"
    result = await case.service.prepare(WOLF, STENDAL)
    assert result.status == "deterministic_failure"
    assert case.anchors.get(WOLF, "truck") == before
    assert case.service.router.route.await_count == 1
    assert locator.calls == []
    with case.db.connect() as conn:
        conn.execute(
            "UPDATE routing_relations SET fingerprint='legacy-negative'"
        )
    assert case.service.current(WOLF, STENDAL).status == "stale"


@pytest.mark.asyncio
async def test_anchor_fingerprints_survive_sqlite_numeric_normalization(case):
    await case.service.prepare(WOLF, STENDAL)
    anchor = case.anchors.get(WOLF, "truck")
    integer = replace(
        anchor,
        anchor=Coordinates(50, 13),
        facility_coordinates=Coordinates(50, 13),
    )
    case.anchors.put(integer)
    assert anchor_identity(integer) == anchor_identity(
        case.anchors.get(WOLF, "truck")
    )
    assert anchor_identity(integer) != anchor_identity(anchor)


@pytest.mark.asyncio
async def test_search_budget_is_transient_and_successful_direct_path_is_certified(
    case,
):
    scope = WorldScope(case.service.world.read())

    class Candidates:
        max_snap_distance_m = 1000.0

        async def resolve(self, facility, *, force=False):
            point = facility.coordinates
            return tuple(
                RoutingCandidate(
                    Coordinates(
                        point.latitude
                        + (index + (5 if force else 0)) * 0.0001,
                        point.longitude,
                    ),
                    index * 12,
                    "test",
                    None,
                )
                for index in range(
                    5 if force or facility.facility_uid == WOLF else 2
                )
            )

    error = RoutingError("no path")
    error.category = "no_path"
    failed_router = AsyncMock()
    failed_router.route.side_effect = error
    with pytest.raises(RoutingError, match="budget") as failure:
        await RoutingConnectionValidator().validate(
            scope.facility(WOLF),
            scope.facility(STENDAL),
            failed_router,
            Candidates(),
            lambda: 1,
        )
    assert failure.value.category == "provider_unavailable"
    assert failed_router.route.await_count == 25
    assert connection_identity(WOLF, STENDAL) == connection_identity(
        STENDAL, WOLF
    )
    assert connection_leases(WOLF, STENDAL) == connection_leases(STENDAL, WOLF)
    assert distance_m(Coordinates(0, 0), Coordinates(0, 180)) > 20_000_000
    with pytest.raises(ValueError, match="different"):
        await case.service.prepare(WOLF, WOLF)
