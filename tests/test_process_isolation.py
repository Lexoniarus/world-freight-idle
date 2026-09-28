"""Process ownership, fencing and cleanup under cancellation and failures."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app import launcher
from app.services.preparation_lease import WORKER_SUBJECT, PreparationLease
from app.services.preparation_worker import MarketPreparationWorker
from tests.test_routing_readiness_store import routing_store


@pytest.mark.asyncio
async def test_real_supervisor_starts_outside_repository_and_closes_children(
    tmp_path,
    monkeypatch,
    unused_tcp_port,
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "isolated.db"))
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", str(unused_tcp_port))
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("VALHALLA_URL", "http://127.0.0.1:1")
    children: list[asyncio.subprocess.Process] = []
    original_start = launcher.start_child

    async def record_child(role: str) -> asyncio.subprocess.Process:
        child = await original_start(role)
        children.append(child)
        return child

    with patch("app.launcher.start_child", side_effect=record_child):
        task = asyncio.create_task(launcher.supervise())
        try:
            async with httpx.AsyncClient(timeout=1, trust_env=False) as client:
                async with asyncio.timeout(30):
                    while True:
                        assert not task.done(), "Supervisor exited at startup"
                        try:
                            response = await client.get(
                                f"http://127.0.0.1:{unused_tcp_port}/api/v1/system/health"
                            )
                            if response.status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        await asyncio.sleep(0.1)
                assert len(children) == 2
                assert all(child.returncode is None for child in children)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            # Also reclaim a child if an assertion detects an early exit.
            for child in children:
                await launcher.stop_child(child)
    assert all(child.returncode == 0 for child in children)


@pytest.mark.asyncio
async def test_worker_lease_excludes_competitors_and_cancels_on_loss(tmp_path):
    _, store = routing_store(tmp_path)
    first, second = (
        PreparationLease(store, lambda: 10),
        PreparationLease(store, lambda: 10),
    )
    assert first.claim() and first.claim() and first.owned()
    assert not second.claim() and not second.owned()
    operation = AsyncMock()
    assert not await second.run(operation)
    operation.assert_not_awaited()
    assert await first.run(operation)
    operation.assert_awaited_once()
    with patch.object(first, "_heartbeat", side_effect=RuntimeError("lost")):
        cancelled = asyncio.Event()

        async def blocked():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        with pytest.raises(RuntimeError, match="lost"):
            await first.run(blocked)
        assert cancelled.is_set()
    with (
        patch.object(store, "renew", side_effect=[True, False]),
        patch("app.services.preparation_lease.asyncio.sleep", new=AsyncMock()),
    ):
        with pytest.raises(RuntimeError, match="lease lost"):
            await first._heartbeat()
    first.close()
    assert not first.owned()
    assert second.claim()
    second.close()
    assert not store.holds(WORKER_SUBJECT, second.owner, 10)


@pytest.mark.asyncio
async def test_worker_iteration_waits_for_global_ownership_and_releases_it(
    tmp_path,
):
    _, store = routing_store(tmp_path)
    lease = PreparationLease(store, lambda: 10)
    jobs = Mock()
    jobs.next_player.return_value = "owner"
    jobs.status.return_value = SimpleNamespace(
        preparation_id="p", generation="g"
    )
    worker = MarketPreparationWorker(jobs, Mock(), lambda: 10, lease)
    with (
        patch.object(lease, "run", return_value=False),
        patch(
            "app.services.preparation_worker.asyncio.sleep", new=AsyncMock()
        ) as sleep,
    ):
        await worker._iteration()
        sleep.assert_awaited_once_with(1)
    with patch.object(lease, "run", return_value=True) as run:
        await worker._iteration()
        run.assert_awaited_once()
    assert lease.claim()
    await worker.close()
    assert not lease.owned()

    assert lease.claim()

    async def failed():
        raise RuntimeError("failed task")

    worker._task = asyncio.create_task(failed())
    await asyncio.sleep(0)
    with pytest.raises(RuntimeError, match="failed task"):
        await worker.close()
    assert not lease.owned()


@pytest.mark.asyncio
async def test_child_creation_and_bounded_shutdown(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    child = Mock(
        stdin=Mock(),
        returncode=None,
        wait=AsyncMock(),
        terminate=Mock(),
        kill=Mock(),
    )
    with patch(
        "app.launcher.asyncio.create_subprocess_exec", return_value=child
    ) as create:
        assert await launcher.start_child("runtime") is child
        assert create.call_args.kwargs["env"]["WFI_MANAGED_CHILD"] == "1"
        assert create.call_args.kwargs.get("creationflags", 0) == 0
        assert create.call_args.args[-1] == "runtime"
        assert Path(create.call_args.args[1]) == (
            Path(launcher.__file__).resolve().parents[1] / "main.py"
        )
    await launcher.stop_child(child)
    child.stdin.close.assert_called_once()
    child.wait.side_effect = [TimeoutError(), TimeoutError(), 0]
    await launcher.stop_child(child)
    child.terminate.assert_called_once()
    child.kill.assert_called_once()
    child.wait.side_effect = [TimeoutError(), 0]
    await launcher.stop_child(child)
    child.returncode, child.stdin = 0, None
    await launcher.stop_child(child)


@pytest.mark.asyncio
@pytest.mark.parametrize("start_failure", [False, True])
async def test_supervisor_restarts_only_worker_and_closes_children(
    start_failure,
):
    runtime_done = asyncio.Event()
    runtime = SimpleNamespace(returncode=None, stdin=Mock())

    async def runtime_wait():
        await runtime_done.wait()
        return runtime.returncode

    runtime.wait = runtime_wait
    workers = []
    calls = 0

    async def start(role):
        nonlocal calls
        if role == "runtime":
            return runtime
        calls += 1
        if calls == 1 and start_failure:
            raise OSError("start failed")
        worker = SimpleNamespace(
            returncode=1, stdin=Mock(), wait=AsyncMock(return_value=1)
        )
        workers.append(worker)
        if calls == 2:
            runtime.returncode = 0
            runtime_done.set()
        return worker

    with patch("app.launcher.start_child", side_effect=start):
        assert await launcher.supervise() == 0
    assert calls == 2
    runtime.stdin.close.assert_called_once()
    for worker in workers:
        worker.stdin.close.assert_called_once()


@pytest.mark.asyncio
async def test_role_selection_parent_eof_and_runtime_cleanup(monkeypatch):
    monkeypatch.setenv("WFI_MANAGED_CHILD", "1")
    with (
        patch("app.launcher.threading.Thread") as thread,
        patch(
            "app.launcher.run_runtime", new=AsyncMock(return_value=0)
        ) as runtime,
        patch("app.launcher.run_prewarm", new=AsyncMock()) as prewarm,
    ):
        assert await launcher.run_role("runtime") == 0
        assert await launcher.run_role("prewarm") == 0
        runtime.assert_awaited_once()
        prewarm.assert_awaited_once()
        assert thread.return_value.start.call_count == 2
    with patch("app.launcher.supervise", return_value=9):
        assert await launcher.run_role("all") == 9
    with pytest.raises(ValueError):
        await launcher.run_role("unknown")
    stop = asyncio.Event()
    loop = Mock()
    with (
        patch(
            "app.launcher.sys.stdin",
            SimpleNamespace(fileno=Mock(return_value=7)),
        ),
        patch("app.launcher.os.read") as read,
    ):
        launcher.parent_eof(loop, stop)
        read.assert_called_once_with(7, 1)
        loop.call_soon_threadsafe.assert_called_once_with(stop.set)
        loop.call_soon_threadsafe.side_effect = RuntimeError("closed")
        launcher.parent_eof(loop, stop)
    stop.set()
    server = SimpleNamespace(serve=AsyncMock(), should_exit=False)
    with patch("app.launcher.uvicorn.Server", return_value=server):
        assert await launcher.run_runtime(stop) == 0
    assert server.should_exit
    server = SimpleNamespace(
        serve=AsyncMock(side_effect=SystemExit(3)), should_exit=False
    )
    with patch("app.launcher.uvicorn.Server", return_value=server):
        assert await launcher.run_runtime(asyncio.Event()) == 3
    assert server.should_exit

    loop = asyncio.get_running_loop()
    with (
        patch("app.launcher.sys.platform", "linux"),
        patch.object(loop, "add_signal_handler") as add,
        patch.object(loop, "remove_signal_handler") as remove,
        patch(
            "app.launcher.execute_role", side_effect=asyncio.CancelledError()
        ),
    ):
        with pytest.raises(asyncio.CancelledError):
            await launcher.run_role("all")
        add.assert_called_once()
        remove.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_prewarm_resources_close_when_worker_start_fails(failure):
    client = AsyncMock()
    worker = SimpleNamespace(start=AsyncMock(), close=AsyncMock())
    runtime = SimpleNamespace(
        database=Mock(), clock=lambda: 10, preparation_jobs=Mock()
    )
    if failure:
        worker.start.side_effect = RuntimeError("worker failed")
    stop = asyncio.Event()
    stop.set()
    with (
        patch("app.launcher.httpx.AsyncClient", return_value=client),
        patch("app.launcher.build_game_runtime", return_value=runtime),
        patch("app.launcher.build_preparation_worker", return_value=worker),
        patch("app.launcher.SqliteMarketStartupStore") as store,
    ):
        store.return_value.player_ids.return_value = ("owner",)
        if failure:
            with pytest.raises(RuntimeError):
                await launcher.run_prewarm(stop)
        else:
            await launcher.run_prewarm(stop)
        runtime.preparation_jobs.ensure.assert_called_once_with("owner", 10)
    client.__aexit__.assert_awaited_once()
    worker.close.assert_awaited_once()
    runtime.database.close.assert_called_once()
