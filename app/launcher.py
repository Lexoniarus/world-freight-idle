"""Single-process local application launcher."""

import asyncio
import os

import uvicorn

from app.logging_config import configure_logging


async def run_application() -> int:
    """Serve HTTP while the FastAPI lifespan owns background work."""
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    server = uvicorn.Server(
        uvicorn.Config(
            "app.main:app",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
        )
    )
    await server.serve()
    return 0


def run() -> int:
    """Translate interactive cancellation into a clean local exit."""
    try:
        return asyncio.run(run_application())
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0
