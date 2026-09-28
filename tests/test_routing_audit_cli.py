"""Audit never contacts providers without explicit bounded execution."""

import argparse
import json

import httpx
import pytest

from scripts import audit_routing_readiness as cli


@pytest.mark.asyncio
async def test_audit_report_is_local_and_prewarm_counts_every_request(
    tmp_path,
    monkeypatch,
    capsys,
):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "audit.db"))
    monkeypatch.setenv("VALHALLA_URL", "https://routing.test")
    monkeypatch.setenv("VALHALLA_MINIMUM_INTERVAL", "0")
    actual_client = httpx.AsyncClient
    observed = []

    def handler(request):
        observed.append(request.url.path)
        body = json.loads(request.content)
        if request.url.path == "/route":
            points = [[p["lon"], p["lat"]] for p in body["locations"]]
            return httpx.Response(
                200,
                headers={"x-graph-revision": "test-graph"},
                json={
                    "trip": {
                        "summary": {"length": 10, "time": 600},
                        "legs": [
                            {
                                "shape": {
                                    "type": "LineString",
                                    "coordinates": points,
                                }
                            }
                        ],
                    }
                },
            )
        assert request.url.path == "/locate"
        point = body["locations"][0]
        return httpx.Response(
            200,
            headers={"x-graph-revision": "test-graph"},
            json=[
                {
                    "edges": [
                        {
                            "correlated_lat": point["lat"],
                            "correlated_lon": point["lon"],
                        }
                    ]
                }
            ],
        )

    def client(**kwargs):
        return actual_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(cli.httpx, "AsyncClient", client)
    args = argparse.Namespace(
        prewarm=False,
        report=True,
        city="Berlin",
        request_limit=2,
        allow_public_endpoint=False,
    )
    await cli.run(args)
    report = json.loads(capsys.readouterr().out)
    assert report["provider_requests"] == 0
    assert report["current_relations"]["unchecked"] > 0
    assert observed == []
    args.prewarm = True
    await cli.run(args)
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["provider_requests"] == 2
    assert len(observed) == 2
    assert "budget exhausted" in captured.err
    args.request_limit = 4
    await cli.run(args)
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["provider_requests"] == 4
    assert resumed["current_relations"]["ready"] == 1
    assert observed.count("/route") == 2
    monkeypatch.setenv("VALHALLA_URL", "https://valhalla1.openstreetmap.de")
    with pytest.raises(ValueError, match="allow-public"):
        await cli.run(args)
    args.allow_public_endpoint = True
    args.request_limit = 0
    with pytest.raises(ValueError, match="positive"):
        await cli.run(args)
