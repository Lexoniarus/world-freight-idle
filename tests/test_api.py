from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.v1.dependencies import get_game_service
from app.api.v1.game_projection import project_contract
from app.domain.contracts import HistoricalContractSnapshot
from app.domain.results import AvailableContract
from app.domain.routing_readiness import RouteReference
from app.main import create_app
from tests.support.api import FakeGame, make_settings, make_static_files


def test_route_reference_belongs_only_to_available_market_projection(
    synthetic_game,
):
    offer = synthetic_game.state_repository.list_offers()[0]
    reference = RouteReference("relation1", "revision1")
    available = AvailableContract(offer, ("truck_01",), reference)
    assert project_contract(available)["route_reference"] == {
        "relation_id": "relation1",
        "revision": "revision1",
    }
    assert "route_reference" not in project_contract(offer)
    historical = HistoricalContractSnapshot.from_offer(offer)
    assert "route_reference" not in project_contract(historical)


def test_v1_resource_endpoints_and_error_mapping(
    tmp_path: Path, synthetic_game
):
    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        app.dependency_overrides[get_game_service] = lambda: FakeGame(
            synthetic_game
        )
        client.headers["X-Freight-Request"] = "1"
        assert client.get("/api/v1/dashboard").status_code == 200
        assert client.get("/api/v1/contracts").status_code == 422
        assert client.get("/api/v1/contracts?vehicle_id=truck_01").json()[
            "preparation"
        ] == {
            "preparation_id": "preparation1",
            "generation": "generation1",
            "status": "partial",
            "next_retry_at": 30,
        }
        assert (
            client.get(
                "/api/v1/contracts?vehicle_id=truck_01&bbox=13,52,14,53&zoom=7"
            ).json()["contracts"][0]["id"]
            == "c1"
        )
        assert (
            client.get(
                "/api/v1/contracts?vehicle_id=truck_01&bbox=bad&zoom=7"
            ).status_code
            == 200
        )
        assert client.get("/api/v1/contracts/c1").json()["id"] == "c1"
        assert client.get("/api/v1/contracts/missing").status_code == 404
        assert (
            client.post(
                "/api/v1/contracts/c1/quote", json={"vehicle_id": "truck_01"}
            ).json()["distance_km"]
            == 10
        )
        assert (
            client.post(
                "/api/v1/contracts/missing/quote",
                json={"vehicle_id": "truck_01"},
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/v1/contracts/routing-error/quote",
                json={"vehicle_id": "truck_01"},
            ).status_code
            == 502
        )
        for body in ({}, {"vehicle_id": None}, {"vehicle_id": ""}):
            assert (
                client.post(
                    "/api/v1/contracts/c1/quote", json=body
                ).status_code
                == 422
            )
        assert client.post("/api/v1/contracts/c1/quote").status_code == 422
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
        assert client.post("/api/v1/contracts/refresh").status_code == 422
        assert (
            client.post(
                "/api/v1/contracts/refresh?vehicle_id=truck_01"
            ).json()["contracts"][0]["id"]
            == "fresh"
        )
        assert (
            client.post(
                "/api/v1/contracts/refresh?vehicle_id=truck_01&bbox=bad&zoom=7"
            ).status_code
            == 200
        )
        assert (
            client.get("/api/v1/fleet").json()["vehicles"][0]["id"]
            == "truck_01"
        )
        assert client.get("/api/v1/fleet/missing").status_code == 404
        assert (
            client.get("/api/v1/fleet/truck_01").json()["energy_level"] == 1010
        )
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
            "/fleet/truck_01": "fleet-detail.html",
            "/company": "company.html",
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


def test_market_reference_errors_have_explicit_http_responses(
    tmp_path, synthetic_game
):
    from unittest.mock import patch

    from app.domain.errors import CatalogueError, UnresolvedVehicleModel

    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    app.dependency_overrides[get_game_service] = lambda: synthetic_game
    with TestClient(app) as client:
        for error, status, message in (
            (CatalogueError("private path"), 503, "Fahrzeugkatalog"),
            (
                UnresolvedVehicleModel("private identity"),
                409,
                "Bestand prüfen",
            ),
        ):
            with patch.object(
                synthetic_game, "read_market", side_effect=error
            ):
                response = client.get("/api/v1/contracts?vehicle_id=truck_01")
            assert response.status_code == status
            assert message in response.json()["detail"]
            assert "private" not in response.text


def test_color_preference_http_validation_and_session_isolation(tmp_path):
    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        client.headers["X-Freight-Request"] = "1"
        assert client.get("/api/v1/auth/preferences").status_code == 401
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "ColorOwner",
                "password": "a-valid-password-123",
            },
        )
        assert response.status_code == 201
        initial = client.get("/api/v1/auth/preferences").json()
        assert len(initial["palette"]) == 10
        color = initial["palette"][0]
        for value in ["red", "#000000", "", None]:
            assert (
                client.put(
                    "/api/v1/auth/preferences",
                    json={
                        "company_color": value,
                    },
                ).status_code
                == 422
            )
        assert client.put(
            "/api/v1/auth/preferences",
            json={
                "company_color": color,
            },
        ).json() == {"company_color": color}
        assert client.get("/api/v1/auth/me").json()["company_color"] == color
        assert (
            client.get("/api/v1/auth/preferences").json()["company_color"]
            == color
        )
        assert (
            client.put(
                "/api/v1/auth/preferences",
                json={
                    "company_color": color,
                },
                headers={"Origin": "https://foreign.invalid"},
            ).status_code
            == 403
        )


def test_request_initialization_catalogue_failure_is_explicit(tmp_path):
    from unittest.mock import patch

    from app.domain.errors import CatalogueError

    make_static_files(tmp_path)
    app = create_app(make_settings(tmp_path))
    with TestClient(app) as client:
        client.headers["X-Freight-Request"] = "1"
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "OfflineOwner",
                "password": "a-valid-password-123",
            },
        )
        with patch(
            "app.api.v1.dependencies.build_player_service",
            side_effect=CatalogueError("Unavailable catalogue"),
        ):
            assert client.get("/api/v1/dashboard").status_code == 503
