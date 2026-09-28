"""Provider pacing has independent concurrency and Retry-After semantics."""

import asyncio

import pytest

from app.providers.request_limiter import (
    ProviderRequestLimiter,
    retry_after_seconds,
)


def test_retry_after_and_invalid_provider_limits():
    assert retry_after_seconds(None, 0) == 0
    assert retry_after_seconds("2", 0) == 2
    assert retry_after_seconds("nan", 0) == 0
    assert retry_after_seconds("invalid", 0) == 0
    assert retry_after_seconds("Thu, 01 Jan 1970 00:00:10 GMT", 2) == 8
    for count, interval in ((0, 1), (1, -1), (1, float("nan"))):
        with pytest.raises(ValueError):
            ProviderRequestLimiter(count, interval)


@pytest.mark.asyncio
async def test_limiter_serializes_and_releases_cancelled_waiters():
    limiter = ProviderRequestLimiter(1, 0.001)
    active = 0
    peak = 0

    async def request():
        nonlocal active, peak
        async with limiter.request():
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1

    limiter.defer("0.002")
    await asyncio.gather(request(), request(), request())
    assert peak == 1
    async with limiter.request():
        task = asyncio.create_task(request())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    await request()


def test_background_trace_never_retains_request_context():
    from app.tracing import background_trace, get_trace_id

    before = get_trace_id()
    with pytest.raises(RuntimeError), background_trace("preparation"):
        assert get_trace_id().startswith("preparation:")
        assert get_trace_id() != before
        raise RuntimeError("cleanup")
    assert get_trace_id() == before


def test_locate_candidates_are_bounded_and_exclude_nontruck_edges():
    from app.providers.routing_anchor import ValhallaTruckAnchorLocator

    edges = [
        {
            "correlated_lat": 50,
            "correlated_lon": 10 + index,
            "access": {"truck": index != 0},
        }
        for index in range(8)
    ]
    edges.insert(2, edges[1])
    from app.domain.geography import Coordinates

    candidates = ValhallaTruckAnchorLocator._access_candidates(
        edges, Coordinates(50, 10), None
    )
    assert len(candidates) == 5
    assert len(set(candidates)) == 5
    assert all(c.coordinates.longitude != 10 for c in candidates)


def test_locate_failure_preserves_bounded_provider_diagnostics():
    import httpx

    from app.providers.routing_anchor import ValhallaTruckAnchorLocator

    response = httpx.Response(
        400, json={"error_code": 171, "error": "unreachable"}
    )
    result = ValhallaTruckAnchorLocator._response_failure(
        response, "no_truck_edge", "graph"
    )
    assert result.provider_code == 171
    assert result.provider_message is not None
    assert "unreachable" in result.provider_message
    result = ValhallaTruckAnchorLocator._response_failure(
        httpx.Response(503, text="x" * 600), "provider_unavailable", None
    )
    assert result.provider_message is not None
    assert len(result.provider_message) == 400


def test_graph_revision_prefers_graph_metadata_without_inventing_versions():
    from app.providers.valhalla_metadata import graph_revision

    assert graph_revision({}) is None
    assert graph_revision({"x-valhalla-version": "engine"}) == "engine"
    assert (
        graph_revision(
            {"x-valhalla-version": "engine", "x-graph-revision": "graph"}
        )
        == "graph"
    )
