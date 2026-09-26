from __future__ import annotations

import httpx
import pytest

from app.domain.geography import Coordinates
from app.providers.routing_anchor import ValhallaTruckAnchorLocator


@pytest.mark.asyncio
async def test_truck_anchor_locator_uses_real_locate_edge_shape():
    calls: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            headers={"X-Graph-Revision": "graph-2026"},
            json=[
                {
                    "input_lat": 52.519011,
                    "input_lon": 13.433188,
                    "edges": [
                        {
                            "way_id": 316869462,
                            "correlated_lat": 52.519011,
                            "correlated_lon": 13.433186,
                        },
                        {
                            "way_id": 1107965737,
                            "correlated_lat": 52.518964,
                            "correlated_lon": 13.43317,
                        },
                    ],
                }
            ],
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        locator = ValhallaTruckAnchorLocator(
            client,
            "https://v.test/",
            "client-id",
        )
        result = await locator.locate(Coordinates(52.519011, 13.433188))

    assert result.accepted
    assert result.status == "validated"
    assert result.coordinates == Coordinates(52.519011, 13.433186)
    assert result.snap_distance_m is not None
    assert result.snap_distance_m < 1
    assert result.provider_revision == "graph-2026"
    assert len(calls) == 1
    assert calls[0].url.path == "/locate"
    assert calls[0].headers["X-Client-Id"] == "client-id"
    assert "X-Trace-Id" in calls[0].headers
    body = calls[0].read().decode("utf-8")
    assert '"costing":"truck"' in body
    assert '"verbose":true' in body


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ([{"edges": []}], "no_truck_edge"),
        ({}, "invalid_response"),
        ([None], "invalid_response"),
        ([{"edges": "bad"}], "invalid_response"),
        ([{"edges": [None]}], "invalid_response"),
        ([{"edges": [{}]}], "invalid_response"),
    ],
)
async def test_truck_anchor_locator_rejects_missing_or_malformed_edges(
    payload,
    status,
):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        locator = ValhallaTruckAnchorLocator(
            client,
            "https://v.test",
            "client-id",
        )
        result = await locator.locate(Coordinates(52.5, 13.4))

    assert not result.accepted
    assert result.coordinates is None
    assert result.status == status


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "text", "expected"),
    [
        (503, "offline", "provider_unavailable"),
        (429, "slow down", "provider_unavailable"),
        (400, "No suitable edges near location", "no_truck_edge"),
        (400, "Malformed locate request", "invalid_response"),
    ],
)
async def test_truck_anchor_locator_classifies_http_failures(
    status_code,
    text,
    expected,
):
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text=text)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        locator = ValhallaTruckAnchorLocator(
            client,
            "https://v.test",
            "client-id",
        )
        result = await locator.locate(Coordinates(52.5, 13.4))

    assert result.status == expected
    assert not result.accepted


@pytest.mark.asyncio
async def test_truck_anchor_locator_classifies_transport_failure():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        locator = ValhallaTruckAnchorLocator(
            client,
            "https://v.test",
            "client-id",
        )
        result = await locator.locate(Coordinates(52.5, 13.4))

    assert result.status == "provider_unavailable"
    assert result.provider_revision is None


def test_truck_anchor_locator_helpers_cover_unusable_metadata():
    locator = ValhallaTruckAnchorLocator.__new__(ValhallaTruckAnchorLocator)
    assert locator._edge_count({"edges": "bad"}) == 0
    assert locator._revision(httpx.Headers()) is None
    with pytest.raises(ValueError, match="Unsupported"):
        locator._correlated_location([])
