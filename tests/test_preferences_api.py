"""Authenticated preference validation and session isolation."""

from fastapi.testclient import TestClient

from app.main import create_app
from tests.support.api import create_minimal_static_files
from tests.support.application_settings import (
    build_synthetic_application_settings,
)


def test_color_preference_http_validation_and_session_isolation(tmp_path):
    create_minimal_static_files(tmp_path)
    application = create_app(build_synthetic_application_settings(tmp_path))
    with TestClient(application) as client:
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
            response = client.put(
                "/api/v1/auth/preferences",
                json={"company_color": value},
            )
            assert response.status_code == 422
        assert client.put(
            "/api/v1/auth/preferences",
            json={"company_color": color},
        ).json() == {"company_color": color}
        assert client.get("/api/v1/auth/me").json()["company_color"] == color
        assert (
            client.get("/api/v1/auth/preferences").json()["company_color"]
            == color
        )
        response = client.put(
            "/api/v1/auth/preferences",
            json={"company_color": color},
            headers={"Origin": "https://foreign.invalid"},
        )
        assert response.status_code == 403
