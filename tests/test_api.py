from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_game_service
from app.config import Settings
from app.main import create_app
from app.providers.routing import RoutingError


class FakeGame:
    def dashboard(self):
        return {
            "player": {"cash": 1},
            "featured_contracts": [],
            "transports": [],
        }

    def list_contracts(self):
        return [{"id": "c1"}]

    def get_contract(self, contract_id):
        if contract_id == "missing":
            raise KeyError("missing")
        return {"id": contract_id}

    async def quote_contract(self, contract_id, vehicle_id=None):
        if contract_id == "routing-error":
            raise RoutingError("down")
        if contract_id == "missing":
            raise KeyError("missing")
        return {"id": contract_id, "distance_km": 10}

    async def dispatch(self, contract_id, vehicle_id):
        if contract_id == "bad":
            raise ValueError("bad")
        if contract_id == "missing":
            raise KeyError("missing")
        if contract_id == "routing-error":
            raise RoutingError("down")
        return {"id": "trip1", "vehicle_id": vehicle_id}

    def refresh_market(self, force=False):
        return [{"id": "fresh", "force": force}]

    def list_vehicles(self):
        return [{"id": "truck_01"}]

    def get_vehicle(self, vehicle_id):
        if vehicle_id == "missing":
            raise KeyError("missing")
        return {"id": vehicle_id}

    def list_transports(self):
        return [{"id": "trip1"}]

    def get_transport(self, transport_id):
        if transport_id == "missing":
            raise KeyError("missing")
        return {"id": transport_id}

    def reset(self):
        return {"player": {"cash": 25000}}


def make_settings(tmp_path: Path) -> Settings:
    catalogue = tmp_path / "vehicles.sqlite3"
    shutil.copyfile(
        Path(__file__).resolve().parents[1]
        / "data"
        / "world_freight_vehicle_catalog.sqlite3",
        catalogue,
    )
    return Settings(
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


def test_v1_resource_endpoints_and_error_mapping(tmp_path: Path):
    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        app.dependency_overrides[get_game_service] = FakeGame
        client.headers["X-Freight-Request"] = "1"
        assert client.get("/api/v1/dashboard").status_code == 200
        assert (
            client.get("/api/v1/contracts").json()["contracts"][0]["id"]
            == "c1"
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
                "force"
            ]
            is True
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
        app.dependency_overrides[get_game_service] = FakeGame
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
