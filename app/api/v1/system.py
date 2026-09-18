"""Operational endpoints."""

from fastapi import APIRouter, Request

from app.config import Settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def get_health(request: Request) -> dict:
    """Return the configured real provider integration status."""
    settings: Settings = request.app.state.settings
    return {
        "ok": True,
        "api_version": "v1",
        "routing_provider": settings.valhalla_url,
        "geocoding_provider": settings.nominatim_url,
        "routing_profile": "truck",
    }
