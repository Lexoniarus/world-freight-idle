"""Prepare certified routing evidence outside gameplay transactions."""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from app.domain.errors import RoutingError
from app.domain.ports import TruckRouter, WorldCatalogue
from app.domain.readiness_ports import RoutingReadinessStore
from app.domain.routing_anchor_ports import RoutingAnchorResolverPort
from app.domain.routing_anchors import NEGATIVE_TTL
from app.domain.routing_connections import connection_leases
from app.domain.routing_readiness import (
    RouteReference,
    RoutingAttempt,
    RoutingRelation,
    relation_identity,
)
from app.domain.world_scopes import WorldScope
from app.services.routing.evidence import RoutingEvidenceReader
from app.services.routing_connections import RoutingConnectionValidator
from app.tracing import get_trace_id


@dataclass(slots=True)
class RoutingPreparationService:
    """Own provider calls, leases and atomic evidence publication."""

    evidence: RoutingEvidenceReader
    store: RoutingReadinessStore
    anchors: RoutingAnchorResolverPort
    router: TruckRouter
    world: WorldCatalogue
    clock: Callable[[], float]
    timeout_seconds: float = 120
    connections: RoutingConnectionValidator = field(
        default_factory=RoutingConnectionValidator
    )

    def __post_init__(self) -> None:
        """Bound provider work to a positive two-minute deadline."""
        if self.timeout_seconds <= 0:
            raise ValueError("Lease must have a positive timeout.")
        self.timeout_seconds = min(self.timeout_seconds, 120)

    async def prepare(
        self, origin: str, destination: str
    ) -> RoutingRelation | None:
        """Deduplicate both directions and release leases on every exit."""
        if origin == destination:
            raise ValueError("Connection requires different facilities.")
        cached = self.evidence.current(origin, destination)
        now = self.clock()
        if cached and (
            cached.status in {"ready", "deterministic_failure"}
            or (cached.retry_at is not None and cached.retry_at > now)
        ):
            return cached
        owner = uuid.uuid4().hex
        acquired: list[str] = []
        expected = self.evidence.fingerprint(origin, destination)
        try:
            for subject in connection_leases(origin, destination):
                if not self.store.acquire(
                    subject,
                    owner,
                    now,
                    now + self.timeout_seconds + 10,
                ):
                    return None
                acquired.append(subject)
            async with asyncio.timeout(self.timeout_seconds):
                return await self._validate(origin, destination, owner)
        except TimeoutError:
            if self.evidence.fingerprint(origin, destination) != expected:
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
            self.evidence.anchor_store.get(origin, "truck"),
            self.evidence.anchor_store.get(destination, "truck"),
        )
        expected = self.evidence.fingerprint(origin, destination)
        if self.world.read() != snapshot:
            return None
        for subject in connection_leases(origin, destination):
            if not self.store.renew(
                subject,
                owner,
                self.clock(),
                self.clock() + self.timeout_seconds + 10,
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
                or self.evidence.fingerprint(origin, destination) != expected
            ):
                return None
            return self._failure(origin, destination, owner, error)
        if (
            self.world.read() != snapshot
            or self.evidence.fingerprint(origin, destination) != expected
        ):
            return None
        now = self.clock()
        forward = self._ready_relation(
            origin,
            destination,
            self.evidence.fingerprint(
                origin,
                destination,
                (result.origin, result.destination),
            ),
            now,
        )
        reverse = self._ready_relation(
            destination,
            origin,
            self.evidence.fingerprint(
                destination,
                origin,
                (result.destination, result.origin),
            ),
            now,
        )
        revision = (
            self.evidence.provider_revision()
            if self.evidence.provider_revision
            else None
        )
        if self.store.publish_connection(
            result,
            forward,
            reverse,
            expected_anchors,
            owner,
            now,
            self.evidence.provider_identity,
            revision,
        ):
            return forward
        return None

    def _ready_relation(
        self,
        origin: str,
        destination: str,
        fingerprint: str,
        now: float,
    ) -> RoutingRelation:
        """Build one immutable ready relation for atomic publication."""
        return RoutingRelation(
            RouteReference(
                relation_identity(origin, destination),
                uuid.uuid4().hex,
            ),
            origin,
            destination,
            fingerprint,
            "ready",
            None,
            None,
            now,
        )

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
                relation_identity(origin, destination),
                uuid.uuid4().hex,
            ),
            origin,
            destination,
            self.evidence.fingerprint(origin, destination),
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
        if self.store.publish(relation, None, owner, self.clock()):
            return relation
        return None
