"""Browser page delivery for the product MVP."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])


@router.get("/login", include_in_schema=False)
def login_page(request: Request) -> FileResponse:
    """Serve the registration and login form."""
    return FileResponse(_application_path(request))


@router.get("/leaderboard", include_in_schema=False)
def leaderboard_page(request: Request) -> FileResponse:
    """Serve the shared delivery ranking."""
    return FileResponse(_application_path(request))


def _application_path(request: Request) -> Path:
    """Resolve the built application shell shared by all product routes."""
    return (
        request.app.state.settings.base_dir / "static" / "dist" / "index.html"
    )


@router.get("/", include_in_schema=False)
def dashboard_page(request: Request) -> FileResponse:
    """Serve the dashboard page."""
    return FileResponse(_application_path(request))


@router.get("/contracts", include_in_schema=False)
def contracts_page(request: Request) -> FileResponse:
    """Serve the contract market page."""
    return FileResponse(_application_path(request))


@router.get("/contracts/{contract_id}", include_in_schema=False)
def contract_detail_page(request: Request, contract_id: str) -> FileResponse:
    """Serve the contract detail page; data is loaded through API v1."""
    del contract_id
    return FileResponse(_application_path(request))


@router.get("/fleet", include_in_schema=False)
def fleet_page(request: Request) -> FileResponse:
    """Serve the fleet page."""
    return FileResponse(_application_path(request))


@router.get("/transports", include_in_schema=False)
def transports_page(request: Request) -> FileResponse:
    """Serve the live transport overview page."""
    return FileResponse(_application_path(request))


@router.get("/transports/{transport_id}", include_in_schema=False)
def transport_detail_page(
    request: Request,
    transport_id: str,
) -> FileResponse:
    """Serve one live transport tracking page."""
    del transport_id
    return FileResponse(_application_path(request))
