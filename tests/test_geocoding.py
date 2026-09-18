from __future__ import annotations

import asyncio

import httpx
import pytest

from app.providers import geocoding as module
from app.providers.geocoding import GeocodingError, NominatimGeocoder
from app.repositories.sqlite_store import SqliteStore


@pytest.mark.asyncio
async def test_geocode_uses_persistent_cache(store: SqliteStore):
    store.put_geocode("cached", 1.0, 2.0, "Cached Address")

    async def handler(_request):
        raise AssertionError("network should not be called")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    geocoder = NominatimGeocoder(store, client, "https://n.test", "agent", 0)
    try:
        assert await geocoder.geocode("cached") == (1.0, 2.0, "Cached Address")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_geocode_calls_nominatim_and_caches(store: SqliteStore):
    seen = {}

    async def handler(request):
        seen["headers"] = request.headers
        seen["query"] = str(request.url)
        return httpx.Response(
            200,
            json=[{"lat": "52.5", "lon": "13.4", "display_name": "Berlin"}],
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    geocoder = NominatimGeocoder(store, client, "https://n.test", "agent", 0)
    try:
        result = await geocoder.geocode("Berlin test")
    finally:
        await client.aclose()
    assert result == (52.5, 13.4, "Berlin")
    assert "q=Berlin+test" in seen["query"]
    assert seen["headers"]["user-agent"] == "agent"
    assert store.get_geocode("Berlin test") is not None


@pytest.mark.asyncio
async def test_geocode_raises_for_no_result(store: SqliteStore):
    async def handler(_request):
        return httpx.Response(200, json=[])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    geocoder = NominatimGeocoder(store, client, "https://n.test", "agent", 0)
    try:
        with pytest.raises(GeocodingError):
            await geocoder.geocode("nowhere")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_respect_rate_limit_sleeps_remaining_time(
    monkeypatch, store: SqliteStore
):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200))
    )
    geocoder = NominatimGeocoder(store, client, "https://n.test", "agent", 1.0)
    geocoder._last_request_monotonic = 9.5
    monkeypatch.setattr(module.time, "monotonic", lambda: 10.0)
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    try:
        await geocoder._respect_rate_limit()
    finally:
        await client.aclose()
    assert slept == [0.5]
