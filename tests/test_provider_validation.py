"""Reject malformed provider data before it changes economics or caches."""

import copy
import math

import httpx
import pytest

from app.domain.errors import GeocodingError, RoutingError
from app.domain.models import RouteResult
from app.providers.geocoding import NominatimGeocoder
from app.providers.routing import ValhallaTruckRouter
from app.providers.validation import parse_coordinates, validate_route

ROUTE = {
    "trip": {
        "summary": {"length": 100, "time": 60},
        "legs": [
            {
                "shape": {
                    "type": "LineString",
                    "coordinates": [[13, 52], [14, 53]],
                }
            }
        ],
    }
}


@pytest.mark.parametrize(
    "point",
    [
        None,
        [1],
        [None, 52],
        [True, 0],
        [181, 0],
        [0, 91],
        [math.inf, 0],
        [0, math.nan],
        ["bad", 1],
    ],
)
def test_coordinate_validation_rejects_invalid_values(point):
    with pytest.raises((ValueError, TypeError)):
        parse_coordinates(point)
    assert parse_coordinates(["13", "52"]) == (13, 52)


@pytest.mark.parametrize("metric", [-1, 0, math.inf, math.nan, True])
def test_route_metrics_must_be_finite_and_positive(metric):
    with pytest.raises(ValueError):
        validate_route(RouteResult(metric, 1, {}, "test"))


@pytest.mark.parametrize(
    "geometry",
    [
        [],
        {"type": "Point"},
        {"type": "LineString", "coordinates": []},
        {"type": "LineString", "coordinates": [[None, 0], [1, 2]]},
    ],
)
def test_route_geometry_must_be_valid(geometry):
    with pytest.raises(ValueError):
        validate_route(RouteResult(1, 1, geometry, "test"))


@pytest.mark.parametrize(
    "failure",
    ["null", "array", "trip", "leg", "negative", "boolean", "coordinate"],
)
async def test_invalid_routing_responses_never_enter_cache(store, failure):
    payload = copy.deepcopy(ROUTE)
    if failure == "null":
        payload = None
    elif failure == "array":
        payload = []
    elif failure == "trip":
        payload["trip"] = []
    elif failure == "leg":
        payload["trip"]["legs"] = [None]
    elif failure == "negative":
        payload["trip"]["summary"]["length"] = -1000
    elif failure == "boolean":
        payload["trip"]["summary"]["time"] = True
    else:
        payload["trip"]["legs"][0]["shape"]["coordinates"][0][0] = None
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )
    ) as client:
        router = ValhallaTruckRouter(
            store, client, "https://route.test", "test"
        )
        with pytest.raises(RoutingError):
            await router.route(52, 13, 53, 14)
        assert store.get_route(router._build_cache_key(52, 13, 53, 14)) is None


async def test_invalid_caches_are_replaced_by_valid_provider_results(store):
    async def respond(request):
        return httpx.Response(
            200,
            json=ROUTE
            if request.method == "POST"
            else [{"lat": "52", "lon": "13"}],
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(respond)
    ) as client:
        router = ValhallaTruckRouter(
            store, client, "https://route.test", "test"
        )
        key = router._build_cache_key(52, 13, 53, 14)
        store.put_route(key, RouteResult(-1, 60, {}, "broken").to_dict())
        assert (await router.route(52, 13, 53, 14)).distance_km == 100
        assert store.get_route(key)["distance_km"] == 100
        store.put_geocode("hub", 100, 999, "broken")
        geocoder = NominatimGeocoder(
            store, client, "https://geo.test", "test", 0
        )
        assert await geocoder.geocode("hub") == (52, 13, "hub")
        assert store.get_geocode("hub")["lon"] == 13


@pytest.mark.parametrize(
    "payload", [{"wrong": "shape"}, [None], [{"lat": 91, "lon": 13}]]
)
async def test_invalid_geocoding_results_are_normalized(store, payload):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )
    ) as client:
        geocoder = NominatimGeocoder(
            store, client, "https://geo.test", "test", 0
        )
        with pytest.raises(GeocodingError):
            await geocoder.geocode("hub")
        assert store.get_geocode("hub") is None


async def test_corrupt_json_cache_is_replaced_and_coordinates_are_numeric(
    store,
):
    payload = copy.deepcopy(ROUTE)
    payload["trip"]["legs"][0]["shape"]["coordinates"] = [
        ["13", "52"],
        ["14", "53"],
    ]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )
    ) as client:
        router = ValhallaTruckRouter(
            store, client, "https://route.test", "test"
        )
        key = router._build_cache_key(52, 13, 53, 14)
        store.put_route(key, {})
        with store.connect() as connection:
            connection.execute(
                "UPDATE route_cache SET payload='broken' WHERE cache_key=?",
                (key,),
            )
        route = await router.route(52, 13, 53, 14)
        assert route.route_geojson["coordinates"] == [
            [13.0, 52.0],
            [14.0, 53.0],
        ]
        assert store.get_route(key)["distance_km"] == 100
