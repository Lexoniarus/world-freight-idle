"""Composition facade for focused routing persistence repositories."""

from contextlib import AbstractContextManager
from sqlite3 import Row

from app.domain.routing_anchors import RoutingAnchor
from app.domain.routing_connections import ValidatedConnection
from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingAttempt,
    RoutingRelation,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.routing.attempts import SqliteRoutingAttemptRepository
from app.repositories.routing.connections import (
    SqliteRoutingConnectionRepository,
)
from app.repositories.routing.leases import SqliteRoutingLeaseRepository
from app.repositories.routing.offer_routes import SqliteOfferRouteStore
from app.repositories.routing.payloads import decode_route_payload
from app.repositories.routing.relations import (
    SqliteRoutingRelationRepository,
)
from app.repositories.routing.schema import SCHEMA
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository

__all__ = (
    "SqliteOfferRouteStore",
    "SqliteRoutingReadinessStore",
    "decode_route_payload",
)


class SqliteRoutingReadinessStore:
    """Compose routing read, lease, proof and attempt repositories."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Initialize additive schema and focused repository owners."""
        self.database = database
        self.anchors = SqliteRoutingAnchorRepository(database)
        self.relations = SqliteRoutingRelationRepository(database)
        self.leases = SqliteRoutingLeaseRepository(database)
        self.connections = SqliteRoutingConnectionRepository(
            database,
            self.relations,
            self.anchors,
        )
        self.attempts = SqliteRoutingAttemptRepository(database)
        self._validated_payloads = self.relations._validated_payloads
        with database.connect() as connection:
            connection.executescript(SCHEMA)

    def read_transaction(self) -> AbstractContextManager[None]:
        """Delegate a bounded consistent evidence read."""
        return self.relations.read_transaction()

    def get(self, relation_id: str) -> RoutingRelation | None:
        """Read one current directed relation."""
        return self.relations.get(relation_id)

    def get_many(
        self, relation_ids: tuple[str, ...]
    ) -> dict[str, RoutingRelation]:
        """Read current directed relations in one bounded query."""
        return self.relations.get_many(relation_ids)

    @staticmethod
    def _relation(row: Row) -> RoutingRelation:
        """Decode one row through the relation repository."""
        return SqliteRoutingRelationRepository._decode_relation(row)

    def payload(self, reference: RouteReference) -> RoutePayload | None:
        """Load one validated immutable route payload."""
        return self.relations.payload(reference)

    def payload_available(self, reference: RouteReference) -> bool:
        """Report whether one exact payload is valid and available."""
        return self.relations.payload_available(reference)

    def _payload_document(self, reference: RouteReference) -> str | None:
        """Read one raw payload document for compatibility diagnostics."""
        return self.relations._payload_document(reference)

    def acquire(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool:
        """Acquire one absent or expired routing lease."""
        return self.leases.acquire(subject, owner, now, expires_at)

    def renew(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool:
        """Renew one live lease owned by the caller."""
        return self.leases.renew(subject, owner, now, expires_at)

    def release(self, subject: str, owner: str) -> None:
        """Release one lease owned by the caller."""
        self.leases.release(subject, owner)

    def holds(self, subject: str, owner: str, now: float) -> bool:
        """Check live lease ownership."""
        return self.leases.holds(subject, owner, now)

    def publish(
        self,
        relation: RoutingRelation,
        payload: RoutePayload | None,
        owner: str,
        now: float,
    ) -> bool:
        """Publish one directed relation behind its lease fence."""
        return self.relations.publish(relation, payload, owner, now)

    def connected(
        self,
        forward: RouteReference,
        reverse: RouteReference,
    ) -> bool:
        """Check one shared bidirectional proof."""
        return self.connections.connected(forward, reverse)

    def connected_many(
        self,
        pairs: tuple[tuple[RouteReference, RouteReference], ...],
    ) -> frozenset[tuple[RouteReference, RouteReference]]:
        """Read shared proofs for a bounded relation collection."""
        return self.connections.connected_many(pairs)

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
    ) -> bool:
        """Publish one fenced bidirectional connection atomically."""
        return self.connections.publish_connection(
            connection,
            forward,
            reverse,
            expected,
            owner,
            now,
            provider,
            provider_revision,
        )

    def append_attempt(self, attempt: RoutingAttempt) -> None:
        """Append one provider attempt diagnostic."""
        self.attempts.append(attempt)

    def provider_revision(self, provider: str) -> str | None:
        """Read the latest observed provider graph revision."""
        return self.relations.provider_revision(provider)

    def observe_provider_revision(self, provider: str, revision: str) -> None:
        """Persist an observed provider graph revision."""
        self.relations.observe_provider_revision(provider, revision)
