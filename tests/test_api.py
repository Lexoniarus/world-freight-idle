from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_game_service
from app.config import Settings
from app.domain.contracts import HistoricalContractSnapshot
from app.domain.game import PlayerState
from app.domain.journeys import unmetered_journey
from app.domain.pricing import PriceQuote
from app.domain.results import ContractQuote, GameSnapshot
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.main import create_app
from app.providers.routing import RoutingError


class FakeGame:
    def __init__(self, game):
        self.offer = replace(game.state_repository.list_offers()[0], id="c1")
        self.vehicle = game.state_repository.list_vehicles()[0]
        self.route = RouteSnapshot(((1, 1), (2, 2)), 10, 20, "fixture")
        self.trip = ActiveTransport(
            "trip1",
            self.vehicle.id,
            HistoricalContractSnapshot.from_offer(self.offer),
            self.offer.origin,
            self.offer.destination,
            self.route,
            1,
            21,
            1000,
            100,
            journey=unmetered_journey((self.route).distance_km, (21) - (1)),
        )

    def now(self):
        return 1

    def dashboard(self):
        return GameSnapshot(
            1, 1, PlayerState(1, 0, 0), (self.vehicle,), (self.trip,)
        )

    def list_contracts(self, query=None, zoom=None):
        return [self.offer]

    def get_contract(self, contract_id):
        if contract_id == "missing":
            raise KeyError("missing")
        return self.offer

    async def quote_contract(self, contract_id, vehicle_id=None):
        if contract_id == "routing-error":
            raise RoutingError("down")
        if contract_id == "missing":
            raise KeyError("missing")
        return ContractQuote(
            self.offer,
            self.route,
            PriceQuote(1000, 100, 900),
            vehicle_id,
            0.62,
        )

    async def dispatch(self, contract_id, vehicle_id):
        if contract_id == "bad":
            raise ValueError("bad")
        if contract_id == "missing":
            raise KeyError("missing")
        if contract_id == "routing-error":
            raise RoutingError("down")
        return self.trip

    def refresh_contracts(self, query=None, zoom=None):
        return [replace(self.offer, id="fresh")]

    def list_vehicles(self):
        return (self.vehicle,)

    def get_vehicle(self, vehicle_id):
        if vehicle_id == "missing":
            raise KeyError("missing")
        return self.vehicle

    def list_transports(self):
        return (self.trip,)

    def get_transport(self, transport_id):
        if transport_id == "missing":
            raise KeyError("missing")
        return self.trip


def make_settings(tmp_path: Path) -> Settings:
    catalogue = tmp_path / "vehicles.sqlite3"
    shutil.copyfile(
        Path(__file__).resolve().parents[1]
        / "data"
        / "world_freight_vehicle_catalog.sqlite3",
        catalogue,
    )
    world = tmp_path / "world.sqlite3"
    shutil.copyfile(
        Path(__file__).resolve().parents[1]
        / "data"
        / "world_freight_company_facility_mvp.sqlite3",
        world,
    )
    return Settings(
        world_catalogue_path=world,
        vehicle_catalogue_path=catalogue,
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "game.db",
        nominatim_url="https://n.test",
        valhalla_url="https://v.test",
        http_user_agent="agent",
        valhalla_client_id="client",
        request_timeout_seconds=1,
        game_time_scale=1,
        log_level="CRITICAL",
    )


def make_static_files(tmp_path: Path):
    static = tmp_path / "static"
    static.mkdir(parents=True)
    (static / "dist").mkdir()
    (static / "dist" / "index.html").write_text("<html>world-map-shell</html>")
    for filename in (
        "login.html",
        "leaderboard.html",
        "index.html",
        "contracts.html",
        "contract-detail.html",
        "fleet.html",
        "transports.html",
        "transport-detail.html",
    ):
        (static / filename).write_text(f"<html>{filename}</html>")


def test_v1_resource_endpoints_and_error_mapping(tmp_path: Path, game):
    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        app.dependency_overrides[get_game_service] = lambda: FakeGame(game)
        client.headers["X-Freight-Request"] = "1"
        assert client.get("/api/v1/dashboard").status_code == 200
        assert (
            client.get("/api/v1/contracts?bbox=13,52,14,53&zoom=7").json()[
                "contracts"
            ][0]["id"]
            == "c1"
        )
        assert (
            client.get("/api/v1/contracts?bbox=bad&zoom=7").status_code == 422
        )
        assert client.get("/api/v1/contracts/c1").json()["id"] == "c1"
        assert client.get("/api/v1/contracts/missing").status_code == 404
        assert (
            client.post("/api/v1/contracts/c1/quote").json()["distance_km"]
            == 10
        )
        assert (
            client.post("/api/v1/contracts/missing/quote").status_code == 404
        )
        assert (
            client.post("/api/v1/contracts/routing-error/quote").status_code
            == 502
        )
        accepted = client.post(
            "/api/v1/contracts/c1/accept", json={"vehicle_id": "truck_01"}
        )
        assert accepted.json()["id"] == "trip1"
        assert (
            client.post(
                "/api/v1/contracts/bad/accept", json={"vehicle_id": "truck_01"}
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/v1/contracts/missing/accept",
                json={"vehicle_id": "truck_01"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/v1/contracts/routing-error/accept",
                json={"vehicle_id": "truck_01"},
            ).status_code
            == 502
        )
        assert (
            client.post("/api/v1/contracts/refresh").json()["contracts"][0][
                "id"
            ]
            == "fresh"
        )
        assert (
            client.post(
                "/api/v1/contracts/refresh?bbox=bad&zoom=7"
            ).status_code
            == 422
        )
        assert (
            client.get("/api/v1/fleet").json()["vehicles"][0]["id"]
            == "truck_01"
        )
        assert client.get("/api/v1/fleet/missing").status_code == 404
        assert (
            client.get("/api/v1/transports").json()["transports"][0]["id"]
            == "trip1"
        )
        assert client.get("/api/v1/transports/missing").status_code == 404
        health = client.get("/api/v1/system/health").json()
        assert health["api_version"] == "v1"
        assert client.post("/api/v1/system/reset").status_code == 404


def test_product_pages_are_distinct_routes(tmp_path: Path):
    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        client.headers["X-Freight-Request"] = "1"
        expected = {
            "/login": "login.html",
            "/leaderboard": "leaderboard.html",
            "/": "index.html",
            "/contracts": "contracts.html",
            "/contracts/c1": "contract-detail.html",
            "/fleet": "fleet.html",
            "/transports": "transports.html",
            "/transports/t1": "transport-detail.html",
        }
        for route, marker in expected.items():
            response = client.get(route)
            assert response.status_code == 200
            assert "world-map-shell" in response.text


def test_persistence_outage_does_not_expose_database_details(tmp_path):
    from app.domain.errors import PersistenceError

    (tmp_path / "static").mkdir()
    app = create_app(make_settings(tmp_path))

    def unavailable():
        raise PersistenceError("private database path and contents")

    app.dependency_overrides[get_game_service] = unavailable
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/dashboard")
    assert response.status_code == 503
    assert response.json() == {"detail": "Spielstand derzeit nicht verfügbar."}
    assert "private" not in response.text
    assert response.headers["x-trace-id"]
