"""Prepare certified two-way road connections outside player transactions."""

import asyncio
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from hashlib import sha256

from app.domain.errors import RoutingError
from app.domain.ports import TruckRouter, WorldCatalogue
from app.domain.readiness_ports import RoutingReadinessStore
from app.domain.routing_anchor_ports import (
    RoutingAnchorResolverPort,
    RoutingAnchorStore,
)
from app.domain.routing_anchors import (
    NEGATIVE_TTL,
    POSITIVE_TTL,
    VALIDATION_VERSION,
    RoutingAnchor,
)
from app.domain.routing_connections import anchor_identity, connection_leases
from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingAttempt,
    RoutingRelation,
    relation_identity,
)
from app.domain.world import WorldSnapshot
from app.domain.world_scopes import WorldScope
from app.services.routing_connections import RoutingConnectionValidator
from app.tracing import get_trace_id


@dataclass
class ReadinessView:
    """Keep evidence memoization scoped to one synchronous read operation."""

    relations: dict[tuple[str, str], RoutingRelation | None] = field(
        default_factory=dict
    )
    fingerprints: dict[tuple[str, str], str] = field(default_factory=dict)


class RoutingReadinessService:
    """Coordinate versioned proofs, global leases and atomic publication."""

    def __init__(
        self,
        store: RoutingReadinessStore,
        anchors: RoutingAnchorResolverPort,
        anchor_store: RoutingAnchorStore,
        router: TruckRouter,
        world: WorldCatalogue,
        provider_identity: str,
        clock: Callable[[], float],
        timeout_seconds: float = 120,
        provider_revision: Callable[[], str | None] | None = None,
        connections: RoutingConnectionValidator | None = None,
    ) -> None:
        """Inject infrastructure; enforce the total provider-work deadline."""
        if timeout_seconds <= 0:
            raise ValueError("Lease must have a positive timeout.")
        self.store = store
        self.anchors = anchors
        self.anchor_store = anchor_store
        self.router = router
        self.world = world
        self.provider_identity = provider_identity
        self.clock = clock
        self.timeout = min(timeout_seconds, 120)
        self.provider_revision = provider_revision
        self.connections = connections or RoutingConnectionValidator()
        self.worker_owner: str | None = None
        self._view: ContextVar[ReadinessView | None] = ContextVar(
            "readiness_view", default=None
        )
        self._world_snapshot: WorldSnapshot | None = None
        self._locations: dict = {}

    @contextmanager
    def reading(self) -> Iterator[None]:
        """Reuse synchronous evidence without leaking it across requests."""
        if self._view.get() is not None:
            yield
            return
        token = self._view.set(ReadinessView())
        try:
            with self.store.read_transaction():
                yield
        finally:
            self._view.reset(token)

    def fingerprint(
        self,
        origin: str,
        destination: str,
        anchors: tuple[RoutingAnchor | None, RoutingAnchor | None]
        | None = None,
    ) -> str:
        """Bind evidence to policy, graph, locations and road access."""
        view = self._view.get()
        key = (origin, destination)
        if view is not None and anchors is None and key in view.fingerprints:
            return view.fingerprints[key]
        snapshot = self.world.read()
        if snapshot is not self._world_snapshot:
            self._world_snapshot = snapshot
            self._locations = {f.facility_uid: f for f in snapshot.facilities}
        selected = (
            anchors
            if anchors is not None
            else (
                self.anchor_store.get(origin, "truck"),
                self.anchor_store.get(destination, "truck"),
            )
        )
        facts = (
            VALIDATION_VERSION,
            self.provider_identity,
            self.provider_revision() if self.provider_revision else None,
            self.anchors.max_snap_distance_m,
            tuple(
                (
                    uid,
                    self._locations[uid].address.display_text(),
                    self._locations[uid].coordinates,
                    anchor_identity(anchor),
                )
                for uid, anchor in zip((origin, destination), selected)
            ),
        )
        fingerprint = sha256(repr(facts).encode()).hexdigest()
        if view is not None and anchors is None:
            view.fingerprints[key] = fingerprint
        return fingerprint

    def current(self, origin: str, destination: str) -> RoutingRelation | None:
        """Reject expired, legacy or one-sided evidence without HTTP."""
        view = self._view.get()
        key = (origin, destination)
        if view is not None and key in view.relations:
            return view.relations[key]
        result = self._current(origin, destination)
        if view is not None:
            view.relations[key] = result
        return result

    def _current(
        self, origin: str, destination: str
    ) -> RoutingRelation | None:
        """Validate fresh persisted evidence for one synchronous read view."""
        relation = self.store.get(relation_identity(origin, destination))
        if relation is None:
            return None
        now = self.clock()
        stale = relation.fingerprint != self.fingerprint(origin, destination)
        if relation.status == "ready":
            reverse = self.store.get(relation_identity(destination, origin))
            stale = stale or (
                now - relation.checked_at >= POSITIVE_TTL
                or reverse is None
                or reverse.status != "ready"
                or now - reverse.checked_at >= POSITIVE_TTL
                or reverse.fingerprint != self.fingerprint(destination, origin)
                or not self.store.connected(
                    relation.reference, reverse.reference
                )
                or not self.store.payload_available(relation.reference)
                or not self.store.payload_available(reverse.reference)
            )
        elif relation.status == "deterministic_failure":
            stale = stale or now - relation.checked_at >= NEGATIVE_TTL
        if stale:
            return replace(relation, status="stale", retry_at=None)
        return relation

    def ready(self, origin: str, destination: str) -> RouteReference | None:
        """Expose only current two-way evidence to the market and dispatch."""
        relation = self.current(origin, destination)
        return (
            relation.reference
            if relation and relation.status == "ready"
            else None
        )

    def load(self, origin: str, destination: str) -> RoutePayload:
        """Load certified metrics without a quote-time provider fallback."""
        reference = self.ready(origin, destination)
        payload = self.store.payload(reference) if reference else None
        if payload is None:
            raise ValueError("Straßenverbindung wird vorbereitet.")
        return payload

    async def prepare(
        self, origin: str, destination: str
    ) -> RoutingRelation | None:
        """Deduplicate both directions and release all leases on every exit."""
        if origin == destination:
            raise ValueError("Connection requires different facilities.")
        cached = self.current(origin, destination)
        now = self.clock()
        if cached and (
            cached.status in {"ready", "deterministic_failure"}
            or (cached.retry_at is not None and cached.retry_at > now)
        ):
            return cached
        owner = uuid.uuid4().hex
        acquired: list[str] = []
        expected = self.fingerprint(origin, destination)
        try:
            for subject in connection_leases(origin, destination):
                if not self.store.acquire(
                    subject, owner, now, now + self.timeout + 10
                ):
                    return None
                acquired.append(subject)
            async with asyncio.timeout(self.timeout):
                return await self._validate(origin, destination, owner)
        except TimeoutError:
            if self.fingerprint(origin, destination) != expected:
                return None
            return self._failure(
                origin, destination, owner, RoutingError("Timeout")
            )
        finally:
            for subject in reversed(acquired):
                self.store.release(subject, owner)

    async def _validate(
        self,
        origin: str,
        destination: str,
        owner: str,
    ) -> RoutingRelation | None:
        """Revalidate inputs after awaits before committing the proof."""
        snapshot = self.world.read()
        scope = WorldScope(snapshot)
        expected_anchors = (
            self.anchor_store.get(origin, "truck"),
            self.anchor_store.get(destination, "truck"),
        )
        expected = self.fingerprint(origin, destination)
        if self.world.read() != snapshot:
            return None
        for subject in connection_leases(origin, destination):
            if not self.store.renew(
                subject, owner, self.clock(), self.clock() + self.timeout + 10
            ):
                return None
        try:
            result = await self.connections.validate(
                scope.facility(origin),
                scope.facility(destination),
                self.router,
                self.anchors,
                self.clock,
                self.store.append_attempt,
            )
        except RoutingError as error:
            if (
                self.world.read() != snapshot
                or self.fingerprint(origin, destination) != expected
            ):
                return None
            return self._failure(origin, destination, owner, error)
        if (
            self.world.read() != snapshot
            or self.fingerprint(origin, destination) != expected
        ):
            return None
        now = self.clock()
        forward = RoutingRelation(
            RouteReference(
                relation_identity(origin, destination), uuid.uuid4().hex
            ),
            origin,
            destination,
            self.fingerprint(
                origin, destination, (result.origin, result.destination)
            ),
            "ready",
            None,
            None,
            now,
        )
        reverse = RoutingRelation(
            RouteReference(
                relation_identity(destination, origin), uuid.uuid4().hex
            ),
            destination,
            origin,
            self.fingerprint(
                destination, origin, (result.destination, result.origin)
            ),
            "ready",
            None,
            None,
            now,
        )
        revision = self.provider_revision() if self.provider_revision else None
        if self.store.publish_connection(
            result,
            forward,
            reverse,
            expected_anchors,
            owner,
            now,
            self.provider_identity,
            revision,
            worker_owner=self.worker_owner,
        ):
            return forward
        return None

    def _failure(
        self,
        origin: str,
        destination: str,
        owner: str,
        error: RoutingError,
    ) -> RoutingRelation | None:
        """Cache negative evidence with its cause for a bounded period."""
        transient = error.category in {
            "provider_unavailable",
            "invalid_response",
        }
        relation = RoutingRelation(
            RouteReference(
                relation_identity(origin, destination), uuid.uuid4().hex
            ),
            origin,
            destination,
            self.fingerprint(origin, destination),
            "transient_failure" if transient else "deterministic_failure",
            error.category,
            self.clock() + (60 if transient else NEGATIVE_TTL),
            self.clock(),
        )
        self.store.append_attempt(
            RoutingAttempt(
                relation.reference.relation_id,
                "truck_connection_failure",
                error.category,
                self.clock(),
                get_trace_id(),
                provider_code=error.provider_code,
                provider_message=error.provider_message,
            )
        )
        if self.store.publish(
            relation, None, owner, self.clock(), worker_owner=self.worker_owner
        ):
            return relation
        return None
