"""Infrastructure ports for globally shared routing readiness."""

from typing import Protocol

from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingAttempt,
    RoutingRelation,
)


class RoutingReadinessStore(Protocol):
    """Persist global evidence and fence concurrent provider work."""

    def get(self, relation_id: str) -> RoutingRelation | None: ...

    def payload(self, reference: RouteReference) -> RoutePayload | None: ...

    def acquire(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool: ...

    def renew(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool: ...

    def release(self, subject: str, owner: str) -> None: ...

    def publish(
        self,
        relation: RoutingRelation,
        payload: RoutePayload | None,
        owner: str,
        now: float,
    ) -> bool: ...

    def append_attempt(self, attempt: RoutingAttempt) -> None: ...


class OfferRouteStore(Protocol):
    """Bind open offers to routing revisions within the market transaction."""

    def get(self, offer_id: str) -> RouteReference | None: ...

    def replace(
        self, references: tuple[tuple[str, RouteReference], ...]
    ) -> None: ...
