"""Prepare global truck relations outside player write transactions."""

import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, replace
from hashlib import sha256

from app.domain.errors import RoutingError
from app.domain.ports import TruckRouter, WorldCatalogue
from app.domain.readiness_ports import RoutingReadinessStore
from app.domain.routing_anchor_ports import (
    RoutingAnchorResolverPort,
    RoutingAnchorStore,
)
from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingAttempt,
    RoutingRelation,
    relation_identity,
)
from app.domain.world_scopes import WorldScope
from app.tracing import get_trace_id


class RoutingReadinessService:
    """Coordinate anchor resolution and globally fenced route validation."""

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
    ) -> None:
        """Inject infrastructure ports and a bounded provider-work deadline."""
        if timeout_seconds <= 0:
            raise ValueError("Readiness timeout must be positive.")
        self.store = store
        self.anchors = anchors
        self.anchor_store = anchor_store
        self.router = router
        self.world = world
        self.provider_identity = provider_identity
        self.clock = clock
        self.timeout = timeout_seconds
        self.provider_revision = provider_revision

    def fingerprint(self, origin: str, destination: str) -> str:
        """Bind readiness to current facilities, anchors and provider graph."""
        scope = WorldScope(self.world.read())
        facts: list[object] = [
            self.provider_identity,
            self.provider_revision() if self.provider_revision else None,
        ]
        for uid in (origin, destination):
            facility = scope.facility(uid)
            anchor = self.anchor_store.get(uid, "truck")
            facts.append(
                (
                    uid,
                    facility.address.display_text(),
                    asdict(facility.coordinates)
                    if facility.coordinates
                    else None,
                    (
                        anchor.anchor,
                        anchor.provider_revision,
                        anchor.validation_status,
                        anchor.facility_coordinates,
                    )
                    if anchor
                    else None,
                )
            )
        return sha256(json.dumps(facts, default=str).encode()).hexdigest()

    def current(self, origin: str, destination: str) -> RoutingRelation | None:
        """Return current ready or negative evidence without any HTTP call."""
        relation = self.store.get(relation_identity(origin, destination))
        if relation is None:
            return None
        if relation.fingerprint != self.fingerprint(origin, destination):
            return replace(
                relation, status="stale", cache_key=None, retry_at=None
            )
        if relation.status == "ready" and not self.store.payload(
            relation.reference
        ):
            return replace(
                relation, status="stale", cache_key=None, retry_at=None
            )
        return relation

    def ready(self, origin: str, destination: str) -> RouteReference | None:
        """Expose only a validated current relation to market publication."""
        relation = self.current(origin, destination)
        if relation is None or relation.status != "ready":
            return None
        return relation.reference

    def load(self, origin: str, destination: str) -> RoutePayload:
        """Load validated metrics without a quote-time provider fallback."""
        reference = self.ready(origin, destination)
        payload = self.store.payload(reference) if reference else None
        if payload is None:
            raise ValueError("Straßenverbindung wird vorbereitet.")
        return payload

    async def prepare(
        self, origin: str, destination: str
    ) -> RoutingRelation | None:
        """Deduplicate directed work globally and reuse negative evidence."""
        cached = self.current(origin, destination)
        now = self.clock()
        if cached is not None and (
            cached.status in {"ready", "deterministic_failure"}
            or (cached.retry_at is not None and cached.retry_at > now)
        ):
            return cached
        subject = relation_identity(origin, destination)
        owner = uuid.uuid4().hex
        if not self.store.acquire(
            subject, owner, now, now + self.timeout + 10
        ):
            return None
        try:
            async with asyncio.timeout(self.timeout):
                return await self._validate(origin, destination, owner)
        except TimeoutError:
            return self._failure(
                origin, destination, owner, "provider_unavailable"
            )
        finally:
            self.store.release(subject, owner)

    async def _validate(
        self,
        origin: str,
        destination: str,
        owner: str,
        revalidated: bool = False,
    ) -> RoutingRelation | None:
        """Resolve truck endpoints and validate one provider route."""
        snapshot = self.world.read()
        scope = WorldScope(snapshot)
        start = await self.anchors.resolve(scope.facility(origin))
        end = await self.anchors.resolve(scope.facility(destination))
        if start.anchor is None or end.anchor is None:
            transient = any(
                a.validation_status in {"provider_unavailable"}
                for a in (start, end)
            )
            return self._failure(
                origin,
                destination,
                owner,
                "provider_unavailable"
                if transient
                else "endpoint_unreachable",
            )
        if self.world.read() != snapshot:
            return None
        expected_fingerprint = self.fingerprint(origin, destination)
        if not self.store.renew(
            relation_identity(origin, destination),
            owner,
            self.clock(),
            self.clock() + self.timeout + 10,
        ):
            return None
        try:
            route = await self.router.route(
                start.anchor.latitude,
                start.anchor.longitude,
                end.anchor.latitude,
                end.anchor.longitude,
            )
        except RoutingError as error:
            if self.fingerprint(origin, destination) != expected_fingerprint:
                return None
            if error.category == "endpoint_unreachable" and not revalidated:
                self.store.append_attempt(
                    RoutingAttempt(
                        relation_identity(origin, destination),
                        "truck_route",
                        error.category,
                        self.clock(),
                        get_trace_id(),
                        provider_code=error.provider_code,
                        provider_message=error.provider_message,
                    )
                )
                await self.anchors.resolve(scope.facility(origin), force=True)
                await self.anchors.resolve(
                    scope.facility(destination), force=True
                )
                return await self._validate(
                    origin, destination, owner, revalidated=True
                )
            return self._failure(
                origin,
                destination,
                owner,
                error.category,
                error.provider_code,
                error.provider_message,
            )
        if self.fingerprint(origin, destination) != expected_fingerprint:
            return None
        payload = RoutePayload(
            route.coordinates,
            route.distance_km,
            route.duration_seconds,
            route.provider,
        )
        reference = RouteReference(
            relation_identity(origin, destination), uuid.uuid4().hex
        )
        relation = RoutingRelation(
            reference,
            origin,
            destination,
            expected_fingerprint,
            "ready",
            f"readiness:v1:{reference.relation_id}:{reference.revision}",
            None,
            None,
            self.clock(),
        )
        self.store.append_attempt(
            RoutingAttempt(
                reference.relation_id,
                "truck_route",
                "validated",
                self.clock(),
                get_trace_id(),
            )
        )
        if self.store.publish(relation, payload, owner, self.clock()):
            return relation
        return None

    def _failure(
        self,
        origin: str,
        destination: str,
        owner: str,
        category: str,
        code: int | None = None,
        message: str | None = None,
    ) -> RoutingRelation | None:
        """Persist diagnostic failure and its bounded retry schedule."""
        transient = category == "provider_unavailable"
        relation = RoutingRelation(
            RouteReference(
                relation_identity(origin, destination), uuid.uuid4().hex
            ),
            origin,
            destination,
            self.fingerprint(origin, destination),
            "transient_failure" if transient else "deterministic_failure",
            None,
            category,
            self.clock() + 60 if transient else None,
            self.clock(),
        )
        self.store.append_attempt(
            RoutingAttempt(
                relation.reference.relation_id,
                "truck_route",
                category,
                self.clock(),
                get_trace_id(),
                provider_code=code,
                provider_message=message,
            )
        )
        if self.store.publish(relation, None, owner, self.clock()):
            return relation
        return None
