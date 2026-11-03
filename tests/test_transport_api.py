"""Active-transport HTTP resource boundaries."""

from tests.support.http_application import fake_game_api_client


def test_transport_api_lists_and_gets_active_transports(
    tmp_path,
    synthetic_game,
):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        response = client.get("/api/v1/transports")
        assert response.json()["transports"][0]["id"] == "trip1"
        assert client.get("/api/v1/transports/missing").status_code == 404
