"""FastAPI application composition root."""

from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import build_v1_router
from app.bootstrap import build_game_service, game_store
from app.config import Settings
from app.domain.errors import WorldCatalogueError
from app.logging_config import configure_logging
from app.repositories.accounts import AccountRepository
from app.services.auth import AuthService
from app.tracing import TraceIdMiddleware
from app.web import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create and close provider HTTP clients for the application lifetime."""
    settings: Settings = app.state.settings
    async with AsyncExitStack() as resources:
        routing_client = httpx.AsyncClient(
            timeout=settings.request_timeout_seconds
        )
        resources.push_async_callback(routing_client.aclose)
        app.state.routing_client = routing_client
        app.state.game = build_game_service(
            settings,
            routing_client,
        )
        app.state.auth = AuthService(
            AccountRepository(game_store(app.state.game))
        )
        yield


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the product MVP with explicit web and versioned API layers."""
    active_settings = settings or Settings.from_env()
    configure_logging(active_settings.log_level)
    app = FastAPI(
        title="World Freight Idle",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.settings = active_settings
    app.add_exception_handler(WorldCatalogueError, world_catalogue_error)
    app.add_middleware(TraceIdMiddleware)
    app.mount(
        "/static",
        StaticFiles(directory=active_settings.base_dir / "static"),
        name="static",
    )
    app.mount(
        "/assets",
        StaticFiles(
            directory=active_settings.base_dir / "assets",
            check_dir=False,
        ),
        name="assets",
    )
    app.include_router(build_v1_router())
    app.include_router(web_router)
    return app


async def world_catalogue_error(
    request: Request, exc: Exception
) -> JSONResponse:
    """Expose a stable outage response without leaking SQL or local paths."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Weltkatalog derzeit nicht verfügbar.",
        },
    )


app = create_app()
