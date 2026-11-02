"""Owned-fleet HTTP resource boundaries."""

from tests.support.http_application import fake_game_api_client


def test_fleet_api_lists_and_gets_owned_vehicles(tmp_path, synthetic_game):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        assert (
            client.get("/api/v1/fleet").json()["vehicles"][0]["id"]
            == "truck_01"
        )
        assert client.get("/api/v1/fleet/missing").status_code == 404
        vehicle = client.get("/api/v1/fleet/truck_01").json()
        assert vehicle["energy_level"] == 1010
