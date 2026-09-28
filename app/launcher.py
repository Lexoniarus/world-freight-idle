"""Operating-system process composition for runtime and preparation."""

import asyncio
import logging
import os
import signal
import sys
import threading
from contextlib import AsyncExitStack
from pathlib import Path

import httpx
import uvicorn

from app.bootstrap import build_game_runtime, build_preparation_worker
from app.config import Settings
from app.logging_config import configure_logging
from app.repositories.market_startup import SqliteMarketStartupStore

LOGGER = logging.getLogger(__name__)


async def start_child(role: str) -> asyncio.subprocess.Process:
    """Inherit the parent's console and keep the managed shutdown pipe."""
    return await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "main.py"),
        "--role",
        role,
        stdin=asyncio.subprocess.PIPE,
        env={**os.environ, "WFI_MANAGED_CHILD": "1"},
    )


async def stop_child(child: asyncio.subprocess.Process) -> None:
    """Request cleanup through EOF, then bound shutdown of a stuck child."""
    if child.stdin is not None:
        child.stdin.close()
    if child.returncode is not None:
        return
    try:
        await asyncio.wait_for(child.wait(), timeout=10)
    except TimeoutError:
        child.terminate()
        try:
            await asyncio.wait_for(child.wait(), timeout=5)
        except TimeoutError:
            child.kill()
            await child.wait()


async def supervise() -> int:
    """Keep runtime serving while independently restarting preparation."""
    LOGGER.info(
        "Starting runtime and preparation processes",
        extra={"event": "process.start"},
    )
    async with AsyncExitStack() as resources:
        runtime = await start_child("runtime")
        resources.push_async_callback(stop_child, runtime)
        runtime_exit = asyncio.create_task(runtime.wait())
        delay = 1
        try:
            while runtime.returncode is None:
                try:
                    worker = await start_child("prewarm")
                    async with AsyncExitStack() as child_resources:
                        child_resources.push_async_callback(stop_child, worker)
                        worker_exit = asyncio.create_task(worker.wait())
                        try:
                            await asyncio.wait(
                                (runtime_exit, worker_exit),
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                        finally:
                            worker_exit.cancel()
                            await asyncio.gather(
                                worker_exit, return_exceptions=True
                            )
                except OSError:
                    LOGGER.exception(
                        "Preparation process could not start",
                        extra={"event": "process.prewarm_start_failed"},
                    )
                if runtime.returncode is None:
                    LOGGER.warning(
                        "Restarting preparation process",
                        extra={
                            "event": "process.prewarm_restart",
                            "data": {"delay_seconds": delay},
                        },
                    )
                    await asyncio.wait((runtime_exit,), timeout=delay)
                    delay = min(delay * 2, 30)
            return await runtime_exit
        finally:
            runtime_exit.cancel()
            await asyncio.gather(runtime_exit, return_exceptions=True)


def parent_eof(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    """Translate the parent pipe closing into a graceful shutdown request."""
    sys.stdin.buffer.read(1)
    try:
        loop.call_soon_threadsafe(stop.set)
    except RuntimeError:
        # A child that already finished has no remaining loop to notify.
        pass


async def run_runtime(stop: asyncio.Event) -> None:
    """Serve HTTP while accepting an independent supervisor stop request."""
    server = uvicorn.Server(
        uvicorn.Config(
            "app.main:app",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
        )
    )
    serving = asyncio.create_task(server.serve())
    stopping = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait(
            (serving, stopping), return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        server.should_exit = True
        stopping.cancel()
        await asyncio.gather(stopping, return_exceptions=True)
        await serving


async def run_prewarm(stop: asyncio.Event) -> None:
    """Own provider resources and resumable demand in a separate process."""
    settings = Settings.from_env()
    async with AsyncExitStack() as resources:
        client = await resources.enter_async_context(
            httpx.AsyncClient(timeout=settings.request_timeout_seconds)
        )
        runtime = build_game_runtime(settings, client)
        worker = build_preparation_worker(runtime)
        resources.push_async_callback(worker.close)
        assert runtime.preparation_jobs is not None
        for user_id in SqliteMarketStartupStore(runtime.database).player_ids():
            runtime.preparation_jobs.ensure(user_id, runtime.clock())
        await worker.start()
        await stop.wait()


async def run_role(role: str) -> int:
    """Select the composition root; standalone roles support Ctrl+C."""
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    loop, task = asyncio.get_running_loop(), asyncio.current_task()
    assert task is not None
    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        return await execute_role(role)
    finally:
        if sys.platform != "win32":
            loop.remove_signal_handler(signal.SIGTERM)


async def execute_role(role: str) -> int:
    """Own the selected role and managed-parent shutdown notification."""
    if role == "all":
        return await supervise()
    if role not in {"runtime", "prewarm"}:
        raise ValueError("Unknown process role.")
    stop = asyncio.Event()
    if os.getenv("WFI_MANAGED_CHILD") == "1":
        threading.Thread(
            target=parent_eof,
            args=(asyncio.get_running_loop(), stop),
            daemon=True,
        ).start()
    if role == "runtime":
        await run_runtime(stop)
    else:
        await run_prewarm(stop)
    return 0
