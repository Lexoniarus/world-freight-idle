from __future__ import annotations

import httpx
import pytest

from app.providers.routing import (
    RoutingError,
    ValhallaTruckRouter,
    decode_polyline6,
)
from app.repositories.sqlite_store import SqliteStore


@pytest.mark.asyncio
async def test_route_calls_valhalla_and_caches(store: SqliteStore):
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
    router = ValhallaTruckRouter(store, client, "https://v.test", "client-id")
    try:
        first = await router.route(52.0, 13.0, 53.0, 12.0)
        second = await router.route(52.0, 13.0, 53.0, 12.0)
    finally:
        await client.aclose()
    assert first.distance_km == 100.5
    assert first.route_geojson["coordinates"][1] == [12.0, 53.0]
    assert second == first
    assert len(calls) == 1
    assert calls[0].headers["X-Client-Id"] == "client-id"


def test_build_cache_key_is_stable(store: SqliteStore):
    client = httpx.AsyncClient()
    router = ValhallaTruckRouter(store, client, "https://v.test", "id")
    first = router._build_cache_key(1.0, 2.0, 3.0, 4.0)
    second = router._build_cache_key(1.0, 2.0, 3.0, 4.0)
    assert first == second
    assert len(first) == 64
    import asyncio

    asyncio.run(client.aclose())


def test_extract_route_supports_geojson_and_rejects_empty(store: SqliteStore):
    client = httpx.AsyncClient()
    router = ValhallaTruckRouter(store, client, "https://v.test", "id")
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
    with pytest.raises(RoutingError):
        router._extract_route(
            {"trip": {"summary": {"length": 1, "time": 1}, "legs": []}}
        )
    import asyncio

    asyncio.run(client.aclose())


def test_decode_polyline6_and_invalid_input():
    points = decode_polyline6("_ibE_seK")
    assert len(points) == 1
    assert abs(points[0][0] - 0.2) < 1e-6
    assert abs(points[0][1] - 0.1) < 1e-6
    with pytest.raises(RoutingError):
        decode_polyline6("_")


@pytest.mark.asyncio
async def test_route_raises_on_provider_http_error(store: SqliteStore):
    async def handler(_request):
        return httpx.Response(429, text="slow down")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    router = ValhallaTruckRouter(store, client, "https://v.test", "client-id")
    try:
        with pytest.raises(RoutingError, match="HTTP 429"):
            await router.route(1, 2, 3, 4)
    finally:
        await client.aclose()


def test_extract_route_supports_polyline_duplicate_join_and_malformed(
    store: SqliteStore,
):
    client = httpx.AsyncClient()
    router = ValhallaTruckRouter(store, client, "https://v.test", "id")
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
    assert result.route_geojson["coordinates"] == [[0.2, 0.1], [0.3, 0.2]]
    with pytest.raises(RoutingError, match="keine verwertbare"):
        router._extract_route(
            {
                "trip": {
                    "summary": {"length": 1, "time": 1},
                    "legs": [{"shape": None}],
                }
            }
        )
    with pytest.raises(RoutingError, match="Unerwartete"):
        router._extract_route({"unexpected": True})
    import asyncio

    asyncio.run(client.aclose())
