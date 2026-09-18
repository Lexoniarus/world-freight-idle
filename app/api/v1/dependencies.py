"""FastAPI dependencies for API v1."""

from fastapi import Depends, HTTPException, Request

from app.bootstrap import (
    build_fleet_service,
    build_map_service,
    build_player_service,
    build_vehicle_catalogue,
)
from app.domain.errors import CatalogueError
from app.domain.ports import VehicleCatalogue
from app.services.auth import SESSION_COOKIE, AuthService
from app.services.fleet import FleetService
from app.services.game import GameService
from app.services.map_locations import MapLocationService


def get_auth_service(request: Request) -> AuthService:
    """Return the shared account authentication service."""
    return request.app.state.auth


def require_same_origin(request: Request) -> None:
    """Reject browser cross-origin writes, including login CSRF."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if request.headers.get("x-freight-request") != "1" or (
        origin and origin != str(request.base_url).rstrip("/")
    ):
        raise HTTPException(
            403, "Anfrage stammt nicht aus der Spieloberfläche."
        )


def get_current_user(
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> dict:
    """Require an unexpired server-side session for private resources."""
    token = request.cookies.get(SESSION_COOKIE, "")
    user = auth.accounts.session_user(token)
    if user is None:
        raise HTTPException(401, "Bitte anmelden.")
    return user


def get_game_service(
    request: Request,
    user: dict = Depends(get_current_user),
) -> GameService:
    """Build a request-scoped game service for the authenticated owner."""
    try:
        return build_player_service(request.app.state.game, user["id"])
    except CatalogueError as exc:
        raise HTTPException(503, str(exc)) from exc


def get_fleet_service(
    request: Request,
    game: GameService = Depends(get_game_service),
) -> FleetService:
    """Resolve the authenticated fleet service through the composition root."""
    return build_fleet_service(game, request.app.state.settings)


def get_map_service(
    game: GameService = Depends(get_game_service),
) -> MapLocationService:
    """Resolve the map service through the composition root."""
    return build_map_service(game)


def get_vehicle_catalogue(request: Request) -> VehicleCatalogue:
    """Resolve the read-only catalogue through the composition root."""
    return build_vehicle_catalogue(request.app.state.settings)
