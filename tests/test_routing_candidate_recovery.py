"""Real Wolfsburg regression and atomic bidirectional readiness invariants."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.domain.errors import RoutingError
from app.domain.geography import Coordinates
from app.domain.world_scopes import WorldScope
from app.providers.request_limiter import ProviderRequestLimiter
from app.providers.routing import ValhallaTruckRouter
from app.providers.routing_anchor import ValhallaTruckAnchorLocator
from app.services.routing.anchors import RoutingAnchorResolver
from tests.support.catalogues import (
    BERLIN_UID,
    build_wolfsburg_routing_catalogue,
)
from tests.support.routing import (
    FakeGeocoder,
    FakeLocator,
    FakeRouter,
    FakeRoutingAnchorResolver,
)
from tests.support.routing_cases import build_routing_test_case

ORIGIN = BERLIN_UID
DESTINATION = "10000000-0000-4000-8000-000000000003"
REFERENCE_ORIGIN = "53e47547-aa34-4234-a41c-4fe81bb86290"
REFERENCE_DESTINATION = "18e6c54b-658c-4a10-ab92-d518bca060f7"


@pytest.fixture
def case(tmp_path, synthetic_world_catalogue):
    return build_routing_test_case(tmp_path, synthetic_world_catalogue)


@pytest.fixture(scope="module")
def wolfsburg_world():
    return build_wolfsburg_routing_catalogue()


@pytest.fixture
def wolfsburg_case(tmp_path, wolfsburg_world):
    return build_routing_test_case(tmp_path, wolfsburg_world)


@pytest.mark.asyncio
async def test_primary_candidate_recovers_wolfsburg_connection(
    wolfsburg_case,
):
    case = wolfsburg_case
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
        ready = await case.service.prepare(
            REFERENCE_ORIGIN, REFERENCE_DESTINATION
        )
        assert ready.status == "ready"
        anchor = case.anchors.get(REFERENCE_ORIGIN, "truck")
        assert 503 < anchor.snap_distance_m < 505
        assert anchor.anchor == Coordinates(52.429326, 10.780732)
        assert case.service.ready(REFERENCE_DESTINATION, REFERENCE_ORIGIN)
        assert (
            case.service.load(
                REFERENCE_ORIGIN, REFERENCE_DESTINATION
            ).road_distance_km
            == 143.915
        )
        assert (
            case.service.load(
                REFERENCE_DESTINATION, REFERENCE_ORIGIN
            ).road_distance_km
            == 143.496
        )
        count = len(calls)
        assert (
            await case.service.prepare(REFERENCE_DESTINATION, REFERENCE_ORIGIN)
        ).status == "ready"
        assert len(calls) == count
        assert WorldScope(case.service.world.read()).facility(
            REFERENCE_ORIGIN
        ).coordinates == Coordinates(52.433806, 10.779611)


@pytest.mark.asyncio
async def test_shifted_endpoint_tries_the_next_candidate(case):
    scope = WorldScope(case.service.world.read())
    origin = scope.facility(ORIGIN)
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
            if facility.facility_uid == ORIGIN
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
        assert (
            await case.service.prepare(ORIGIN, DESTINATION)
        ).status == "ready"
    assert case.anchors.get(ORIGIN, "truck").anchor == shifted


@pytest.mark.asyncio
async def test_unreachable_destination_keeps_certified_anchors(case):
    await case.service.prepare(ORIGIN, DESTINATION)
    before = case.anchors.get(ORIGIN, "truck")
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
    result = await case.service.prepare(ORIGIN, DESTINATION)
    assert result.status == "deterministic_failure"
    assert case.anchors.get(ORIGIN, "truck") == before
    assert case.service.router.route.await_count == 1
    assert locator.calls == []
    with case.db.connect() as conn:
        conn.execute(
            "UPDATE routing_relations SET fingerprint='legacy-negative'"
        )
    assert case.service.current(ORIGIN, DESTINATION).status == "stale"
