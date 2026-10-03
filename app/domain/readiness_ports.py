"""Infrastructure ports for globally shared routing readiness."""

from contextlib import AbstractContextManager
from typing import Protocol

from app.domain.routing_anchors import RoutingAnchor
from app.domain.routing_connections import ValidatedConnection
from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingAttempt,
    RoutingRelation,
)


class RoutingReadinessStore(Protocol):
    """Persist global evidence and fence concurrent provider work."""

    def read_transaction(self) -> AbstractContextManager[None]: ...

    def get(self, relation_id: str) -> RoutingRelation | None: ...

    def get_many(
        self, relation_ids: tuple[str, ...]
    ) -> dict[str, RoutingRelation]: ...

    def payload(self, reference: RouteReference) -> RoutePayload | None: ...

    def payload_available(self, reference: RouteReference) -> bool: ...

    def available_payloads(
        self, references: tuple[RouteReference, ...]
    ) -> frozenset[RouteReference]: ...

    def acquire(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool: ...

    def renew(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool: ...

    def release(self, subject: str, owner: str) -> None: ...

    def holds(self, subject: str, owner: str, now: float) -> bool: ...

    def publish(
        self,
        relation: RoutingRelation,
        payload: RoutePayload | None,
        owner: str,
        now: float,
        worker_owner: str | None = None,
    ) -> bool: ...

    def connected(
        self,
        forward: RouteReference,
        reverse: RouteReference,
    ) -> bool: ...

    def connected_references(
        self, relation_ids: tuple[str, ...]
    ) -> frozenset[tuple[RouteReference, RouteReference]]: ...

    def publish_connection(
        self,
        connection: ValidatedConnection,
        forward: RoutingRelation,
        reverse: RoutingRelation,
        expected: tuple[RoutingAnchor | None, RoutingAnchor | None],
        owner: str,
        now: float,
        provider: str,
        provider_revision: str | None,
        worker_owner: str | None = None,
    ) -> bool: ...

    def append_attempt(self, attempt: RoutingAttempt) -> None: ...


class OfferRouteStore(Protocol):
    """Bind open offers to routing revisions within the market transaction."""

    def get(self, offer_id: str) -> RouteReference | None: ...

    def replace(
        self, references: tuple[tuple[str, RouteReference], ...]
    ) -> None: ...
