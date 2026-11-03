"""Dashboard and system HTTP resource boundaries."""

from tests.support.http_application import fake_game_api_client


def test_dashboard_and_system_api_expose_supported_resources(
    tmp_path,
    synthetic_game,
):
    with fake_game_api_client(tmp_path, synthetic_game) as client:
        assert client.get("/api/v1/dashboard").status_code == 200
        health = client.get("/api/v1/system/health").json()
        assert health["api_version"] == "v1"
        assert client.post("/api/v1/system/reset").status_code == 404
