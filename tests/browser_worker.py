"""Separate deterministic preparation process for isolated browser tests."""

import asyncio
import sys
import threading
from pathlib import Path

import httpx

from app.bootstrap import build_game_runtime, build_preparation_worker
from app.launcher import parent_eof
from tests.browser_settings import isolated_browser_settings
from tests.conftest import FakeRouter, FakeRoutingAnchorResolver


async def main() -> None:
    settings = isolated_browser_settings(Path(sys.argv[1]))
    stop = asyncio.Event()
    threading.Thread(
        target=parent_eof, args=(asyncio.get_running_loop(), stop), daemon=True
    ).start()
    async with httpx.AsyncClient() as client:
        runtime = build_game_runtime(settings, client)
        runtime.router = FakeRouter()
        runtime.anchors = FakeRoutingAnchorResolver()
        assert runtime.readiness is not None
        runtime.readiness.router = runtime.router
        runtime.readiness.anchors = runtime.anchors
        worker = build_preparation_worker(runtime)
        try:
            await worker.start()
            await stop.wait()
        finally:
            await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
