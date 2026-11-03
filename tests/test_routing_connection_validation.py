"""Real Wolfsburg regression and atomic bidirectional readiness invariants."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.domain.errors import RoutingError
from app.domain.geography import Coordinates
from app.domain.routing_anchors import (
    RoutingCandidate,
    distance_m,
)
from app.domain.routing_connections import (
    connection_identity,
    connection_leases,
)
from app.domain.world_scopes import WorldScope
from app.services.routing.connections import RoutingConnectionValidator
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
async def test_connection_requires_both_route_directions(case, failure):
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
    result = await case.service.prepare(ORIGIN, DESTINATION)
    assert result.status == (
        "transient_failure"
        if failure == "rate_limit"
        else "deterministic_failure"
    )
    assert not case.service.ready(ORIGIN, DESTINATION)
    assert not case.service.ready(DESTINATION, ORIGIN)
    assert case.anchors.get(ORIGIN, "truck") is None
    with case.db.connect() as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM routing_connection_proofs"
            ).fetchone()[0]
            == 0
        )


@pytest.mark.asyncio
async def test_connection_deadline_is_reported_as_transient(case):
    scope = WorldScope(case.service.world.read())
    validator = RoutingConnectionValidator()
    with patch.object(
        validator,
        "_search_candidate_pairs",
        side_effect=TimeoutError,
    ):
        with pytest.raises(RoutingError) as failure:
            await validator.validate(
                scope.facility(ORIGIN),
                scope.facility(DESTINATION),
                case.service.router,
                case.service.anchors,
                lambda: 1,
            )
    assert failure.value.category == "provider_unavailable"


@pytest.mark.asyncio
async def test_candidate_search_budget_is_bounded_and_direct_path_is_certified(
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
                    5 if force or facility.facility_uid == ORIGIN else 2
                )
            )

    error = RoutingError("no path")
    error.category = "no_path"
    failed_router = AsyncMock()
    failed_router.route.side_effect = error
    with pytest.raises(RoutingError, match="budget") as failure:
        await RoutingConnectionValidator().validate(
            scope.facility(ORIGIN),
            scope.facility(DESTINATION),
            failed_router,
            Candidates(),
            lambda: 1,
        )
    assert failure.value.category == "provider_unavailable"
    assert failed_router.route.await_count == 25
    assert connection_identity(ORIGIN, DESTINATION) == connection_identity(
        DESTINATION, ORIGIN
    )
    assert connection_leases(ORIGIN, DESTINATION) == connection_leases(
        DESTINATION, ORIGIN
    )
    assert distance_m(Coordinates(0, 0), Coordinates(0, 180)) > 20_000_000
    with pytest.raises(ValueError, match="different"):
        await case.service.prepare(ORIGIN, ORIGIN)
