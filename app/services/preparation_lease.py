"""Own one renewable provider worker lease across separate processes."""

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.domain.readiness_ports import RoutingReadinessStore

WORKER_SUBJECT = "worker:market-preparation"
ResultT = TypeVar("ResultT")


class PreparationLease:
    """Fence publication and cancel provider work after ownership is lost."""

    def __init__(
        self, store: RoutingReadinessStore, clock: Callable[[], float]
    ) -> None:
        """Inject persisted ownership independently of request contexts."""
        self.store = store
        self.clock = clock
        self.owner = uuid.uuid4().hex

    def owned(self) -> bool:
        """Check the worker inside the publication's write transaction."""
        return self.store.holds(WORKER_SUBJECT, self.owner, self.clock())

    def claim(self) -> bool:
        """Renew current ownership or take an abandoned worker lease."""
        now = self.clock()
        return self.store.renew(
            WORKER_SUBJECT, self.owner, now, now + 180
        ) or self.store.acquire(WORKER_SUBJECT, self.owner, now, now + 180)

    async def run(self, operation: Callable[[], Awaitable[ResultT]]) -> bool:
        """Run one batch only while renewal succeeds; always join children."""
        if not self.claim():
            return False
        work = asyncio.ensure_future(operation())
        heartbeat = asyncio.create_task(self._heartbeat())
        try:
            done, _ = await asyncio.wait(
                (work, heartbeat), return_when=asyncio.FIRST_COMPLETED
            )
            if heartbeat in done:
                await heartbeat
            await work
            return True
        finally:
            work.cancel()
            heartbeat.cancel()
            await asyncio.gather(work, heartbeat, return_exceptions=True)

    async def _heartbeat(self) -> None:
        """Keep ownership alive during slow provider responses."""
        while True:
            await asyncio.sleep(30)
            now = self.clock()
            if not self.store.renew(
                WORKER_SUBJECT, self.owner, now, now + 180
            ):
                raise RuntimeError("Preparation worker lease lost.")

    def close(self) -> None:
        """Release only this process's lease after its work has stopped."""
        self.store.release(WORKER_SUBJECT, self.owner)
