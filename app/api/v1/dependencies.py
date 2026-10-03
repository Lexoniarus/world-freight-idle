"""FastAPI dependencies for API v1."""

from fastapi import Depends, HTTPException, Request

from app.bootstrap import (
    build_fleet_service,
    build_leaderboard_reader,
    build_map_service,
    build_player_service,
    build_runtime_reader,
    build_runtime_view,
    build_traffic_reader,
    build_vehicle_catalogue,
)
from app.domain.errors import (
    CatalogueError,
    DuplicateAccountError,
    SupabaseAuthUnavailable,
)
from app.domain.ports import VehicleCatalogue
from app.domain.read_ports import LeaderboardReader, TrafficReader
from app.domain.runtime_views import RuntimeReader
from app.services.auth import SESSION_COOKIE, AuthService
from app.services.fleet import FleetService
from app.services.game import GameService
from app.services.map_locations import MapLocationService
from app.services.runtime_views import RuntimeViewService


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
    """Prefer a locally verified Supabase JWT, then legacy sessions."""
    authorization = request.headers.get("authorization", "")
    if authorization:
        scheme, _, token = authorization.partition(" ")
        verifier = request.app.state.supabase_auth
        if scheme.lower() != "bearer" or not token or verifier is None:
            raise HTTPException(401, "Bitte anmelden.")
        try:
            identity = verifier.verify(token)
            return dict(
                auth.accounts.ensure_external_user(
                    identity["id"], identity["username"]
                )
            )
        except SupabaseAuthUnavailable as exc:
            raise HTTPException(
                503, "Anmeldung derzeit nicht verfügbar."
            ) from exc
        except DuplicateAccountError as exc:
            raise HTTPException(
                409, "Spielerprofil konnte nicht angelegt werden."
            ) from exc
        except ValueError as exc:
            raise HTTPException(401, "Bitte anmelden.") from exc
    token = request.cookies.get(SESSION_COOKIE, "")
    user = auth.accounts.session_user(token)
    if user is None:
        raise HTTPException(401, "Bitte anmelden.")
    return dict(user)


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
    """Resolve the authenticated catalogue map service."""
    return build_map_service(game)


def get_traffic_reader(request: Request) -> TrafficReader:
    """Resolve the shared read-only multiplayer traffic projection."""
    return build_traffic_reader(request.app.state.game)


def get_runtime_reader(request: Request) -> RuntimeReader:
    """Resolve independent scalar and geometry read resources."""
    return build_runtime_reader(request.app.state.game)


def get_runtime_view(
    request: Request,
    user: dict = Depends(get_current_user),
) -> RuntimeViewService:
    """Bind summary reads to the authenticated owner only."""
    return build_runtime_view(request.app.state.game, user["id"])


def get_vehicle_catalogue(request: Request) -> VehicleCatalogue:
    """Resolve the read-only catalogue through the composition root."""
    return build_vehicle_catalogue(request.app.state.settings)


def get_leaderboard_reader(request: Request) -> LeaderboardReader:
    """Resolve the public projection separately from account operations."""
    return build_leaderboard_reader(request.app.state.game)
