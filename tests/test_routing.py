from __future__ import annotations

import httpx
import pytest

from app.domain.errors import RoutingError
from app.providers.routing import ValhallaTruckRouter, decode_polyline6
from app.repositories.provider_cache import SqliteProviderCache


@pytest.mark.asyncio
async def test_route_calls_valhalla_and_caches(cache: SqliteProviderCache):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "trip": {
                    "summary": {"length": 100.5, "time": 3600},
                    "legs": [
                        {
                            "shape": {
                                "type": "LineString",
                                "coordinates": [[13.0, 52.0], [12.0, 53.0]],
                            }
                        }
                    ],
                }
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = ValhallaTruckRouter(cache, client, "https://v.test", "client-id")
    try:
        first = await router.route(52.0, 13.0, 53.0, 12.0)
        second = await router.route(52.0, 13.0, 53.0, 12.0)
    finally:
        await client.aclose()
    assert first.distance_km == 100.5
    assert first.coordinates[1] == (12.0, 53.0)
    assert second == first
    assert len(calls) == 1
    assert calls[0].headers["X-Client-Id"] == "client-id"


def test_build_cache_key_is_stable(cache: SqliteProviderCache):
    client = httpx.AsyncClient()
    router = ValhallaTruckRouter(cache, client, "https://v.test", "id")
    first = router._build_cache_key(1.0, 2.0, 3.0, 4.0)
    second = router._build_cache_key(1.0, 2.0, 3.0, 4.0)
    assert first == second
    assert len(first) == 64
    import asyncio

    asyncio.run(client.aclose())


def test_extract_route_supports_geojson_and_rejects_empty(
    cache: SqliteProviderCache,
):
    client = httpx.AsyncClient()
    router = ValhallaTruckRouter(cache, client, "https://v.test", "id")
    result = router._extract_route(
        {
            "trip": {
                "summary": {"length": 5, "time": 60},
                "legs": [
                    {
                        "shape": {
                            "type": "LineString",
                            "coordinates": [[1, 2], [3, 4]],
                        }
                    }
                ],
            }
        }
    )
    assert result.duration_seconds == 60
    with pytest.raises(RoutingError) as caught:
        router._extract_route(
            {"trip": {"summary": {"length": 1, "time": 1}, "legs": []}}
        )
    assert caught.value.category == "invalid_response"
    assert caught.value.retryable is False
    import asyncio

    asyncio.run(client.aclose())


def test_decode_polyline6_and_invalid_input():
    points = decode_polyline6("_ibE_seK")
    assert len(points) == 1
    assert abs(points[0][0] - 0.2) < 1e-6
    assert abs(points[0][1] - 0.1) < 1e-6
    with pytest.raises(RoutingError) as caught:
        decode_polyline6("_")
    assert caught.value.category == "invalid_response"
    assert caught.value.retryable is False


def test_routing_error_has_provider_independent_defaults():
    error = RoutingError("offline")
    assert error.category == "provider_unavailable"
    assert error.provider_code is None
    assert error.provider_message is None
    assert error.retryable is True


@pytest.mark.parametrize(
    (
        "payload",
        "status_code",
        "category",
        "provider_code",
        "provider_message",
        "retryable",
    ),
    [
        (
            {
                "error_code": 171,
                "error": "No suitable edges near location",
                "status_code": 400,
            },
            400,
            "endpoint_unreachable",
            171,
            "No suitable edges near location",
            False,
        ),
        (
            {
                "error_code": 170,
                "error": "Locations are in unconnected regions.",
                "status_code": 400,
            },
            400,
            "no_path",
            170,
            "Locations are in unconnected regions.",
            False,
        ),
        (
            {
                "error_code": 442,
                "error": "No path could be found for input",
                "status_code": 400,
            },
            400,
            "no_path",
            442,
            "No path could be found for input",
            False,
        ),
        (
            {
                "error_code": 154,
                "error": "Path distance exceeds the max distance limit",
                "status_code": 400,
            },
            400,
            "distance_limit",
            154,
            "Path distance exceeds the max distance limit",
            False,
        ),
        (
            {
                "error_code": 599,
                "error": "Unknown provider failure",
                "status_code": 503,
            },
            503,
            "provider_unavailable",
            599,
            "Unknown provider failure",
            True,
        ),
    ],
)
@pytest.mark.asyncio
async def test_route_classifies_valhalla_http_failures(
    cache: SqliteProviderCache,
    payload,
    status_code,
    category,
    provider_code,
    provider_message,
    retryable,
):
    async def handler(_request):
        return httpx.Response(status_code, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        router = ValhallaTruckRouter(
            cache, client, "https://v.test", "client-id"
        )
        with pytest.raises(RoutingError) as caught:
            await router.route(1, 2, 3, 4)

    error = caught.value
    assert error.category == category
    assert error.provider_code == provider_code
    assert error.provider_message == provider_message
    assert error.retryable is retryable
    key = router._build_cache_key(1, 2, 3, 4)
    assert cache.get_route(key) is None


@pytest.mark.asyncio
async def test_route_raises_on_provider_http_error(cache: SqliteProviderCache):
    async def handler(_request):
        return httpx.Response(429, text="slow down")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = ValhallaTruckRouter(cache, client, "https://v.test", "client-id")
    try:
        with pytest.raises(RoutingError) as caught:
            await router.route(1, 2, 3, 4)
    finally:
        await client.aclose()

    error = caught.value
    assert error.category == "provider_unavailable"
    assert error.provider_code is None
    assert error.provider_message == "slow down"
    assert error.retryable is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exception_type", [httpx.ConnectError, httpx.ReadTimeout]
)
async def test_route_classifies_transport_failure_as_provider_unavailable(
    cache: SqliteProviderCache,
    exception_type,
):
    async def handler(request):
        raise exception_type("provider offline", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        router = ValhallaTruckRouter(
            cache, client, "https://v.test", "client-id"
        )
        with pytest.raises(RoutingError) as caught:
            await router.route(1, 2, 3, 4)

    error = caught.value
    assert error.category == "provider_unavailable"
    assert error.provider_code is None
    assert "provider offline" in (error.provider_message or "")
    assert error.retryable is True


@pytest.mark.asyncio
async def test_route_classifies_invalid_provider_response(
    cache: SqliteProviderCache,
):
    async def handler(_request):
        return httpx.Response(200, text="not-json")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        router = ValhallaTruckRouter(
            cache, client, "https://v.test", "client-id"
        )
        with pytest.raises(RoutingError) as caught:
            await router.route(1, 2, 3, 4)

    error = caught.value
    assert error.category == "invalid_response"
    assert error.provider_code is None
    assert error.provider_message == "not-json"
    assert error.retryable is False


def test_extract_route_supports_polyline_duplicate_join_and_malformed(
    cache: SqliteProviderCache,
):
    client = httpx.AsyncClient()
    router = ValhallaTruckRouter(cache, client, "https://v.test", "id")
    data = {
        "trip": {
            "summary": {"length": 5, "time": 60},
            "legs": [
                {"shape": "_ibE_seK"},
                {
                    "shape": {
                        "type": "LineString",
                        "coordinates": [[0.2, 0.1], [0.3, 0.2]],
                    }
                },
            ],
        }
    }
    result = router._extract_route(data)
    assert result.coordinates == ((0.2, 0.1), (0.3, 0.2))
    with pytest.raises(RoutingError, match="keine verwertbare") as caught:
        router._extract_route(
            {
                "trip": {
                    "summary": {"length": 1, "time": 1},
                    "legs": [{"shape": None}],
                }
            }
        )
    assert caught.value.category == "invalid_response"
    with pytest.raises(RoutingError, match="unerwartete") as caught:
        router._extract_route({"unexpected": True})
    assert caught.value.category == "invalid_response"
    assert caught.value.provider_message == '{"unexpected": true}'
    import asyncio

    asyncio.run(client.aclose())
