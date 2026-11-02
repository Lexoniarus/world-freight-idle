"""Contract HTTP projection, validation and error translation."""

from app.api.v1.game_projection import project_contract
from app.domain.contracts import HistoricalContractSnapshot
from app.domain.results import AvailableContract
from app.domain.routing_readiness import RouteReference
from tests.support.http_application import fake_game_api_client


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


def test_contract_list_requires_vehicle_scope(tmp_path, synthetic_game):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        assert client.get("/api/v1/contracts").status_code == 422


def test_contract_list_projects_preparation_status(tmp_path, synthetic_game):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        response = client.get("/api/v1/contracts?vehicle_id=truck_01")
        assert response.json()["preparation"] == {
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


def test_contract_detail_maps_present_and_missing_offer(
    tmp_path,
    synthetic_game,
):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        assert client.get("/api/v1/contracts/c1").json()["id"] == "c1"
        assert client.get("/api/v1/contracts/missing").status_code == 404


def test_contract_quote_maps_validation_and_routing_failures(
    tmp_path,
    synthetic_game,
):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        quote_url = "/api/v1/contracts/c1/quote"
        assert (
            client.post(quote_url, json={"vehicle_id": "truck_01"}).json()[
                "distance_km"
            ]
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
                "/api/v1/contracts/bad/quote",
                json={"vehicle_id": "truck_01"},
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/v1/contracts/routing-error/quote",
                json={"vehicle_id": "truck_01"},
            ).status_code
            == 502
        )
        for body in ({}, {"vehicle_id": None}, {"vehicle_id": ""}):
            assert client.post(quote_url, json=body).status_code == 422
        assert client.post(quote_url).status_code == 422


def test_contract_dispatch_maps_domain_and_routing_failures(
    tmp_path,
    synthetic_game,
):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        accept_url = "/api/v1/contracts/c1/accept"
        assert (
            client.post(accept_url, json={"vehicle_id": "truck_01"}).json()[
                "id"
            ]
            == "trip1"
        )
        for contract_id, status in (
            ("bad", 400),
            ("missing", 404),
            ("routing-error", 502),
        ):
            response = client.post(
                f"/api/v1/contracts/{contract_id}/accept",
                json={"vehicle_id": "truck_01"},
            )
            assert response.status_code == status


def test_contract_refresh_requires_vehicle_scope(tmp_path, synthetic_game):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        assert client.post("/api/v1/contracts/refresh").status_code == 422


def test_contract_refresh_returns_authoritative_stock(
    tmp_path,
    synthetic_game,
):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        refreshed = client.post(
            "/api/v1/contracts/refresh?vehicle_id=truck_01"
        )
        assert refreshed.json()["contracts"][0]["id"] == "fresh"
        assert (
            client.post(
                "/api/v1/contracts/refresh?vehicle_id=truck_01&bbox=bad&zoom=7"
            ).status_code
            == 200
        )
