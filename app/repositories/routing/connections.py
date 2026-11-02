"""Bidirectional connection proofs and atomic route publication."""

import json
import sqlite3
from dataclasses import asdict

from app.domain.routing_anchors import VALIDATION_VERSION, RoutingAnchor
from app.domain.routing_connections import (
    ValidatedConnection,
    connection_identity,
    connection_leases,
)
from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingRelation,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.routing.relations import (
    SqliteRoutingRelationRepository,
)
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository


class SqliteRoutingConnectionRepository:
    """Own shared proofs and atomic bidirectional publication."""

    def __init__(
        self,
        database: SqliteGameDatabase,
        relations: SqliteRoutingRelationRepository,
        anchors: SqliteRoutingAnchorRepository,
    ) -> None:
        """Inject relation and anchor owners used by publication."""
        self.database = database
        self.relations = relations
        self.anchors = anchors

    def connected(
        self,
        forward: RouteReference,
        reverse: RouteReference,
    ) -> bool:
        """Require both current directional revisions in one shared proof."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM routing_connection_proofs WHERE "
                "validation_version=? AND ((forward_id=? AND "
                "forward_revision=? AND reverse_id=? AND reverse_revision=?)"
                " OR (reverse_id=? AND reverse_revision=? AND forward_id=? "
                "AND forward_revision=?))",
                (
                    VALIDATION_VERSION,
                    forward.relation_id,
                    forward.revision,
                    reverse.relation_id,
                    reverse.revision,
                    forward.relation_id,
                    forward.revision,
                    reverse.relation_id,
                    reverse.revision,
                ),
            ).fetchone()
        return row is not None

    def connected_many(
        self,
        pairs: tuple[tuple[RouteReference, RouteReference], ...],
    ) -> frozenset[tuple[RouteReference, RouteReference]]:
        """Read shared proofs for requested revision pairs in one query."""
        if not pairs:
            return frozenset()
        relation_ids = tuple(
            sorted(
                {reference.relation_id for pair in pairs for reference in pair}
            )
        )
        placeholders = ",".join("?" for _ in relation_ids)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT forward_id, forward_revision, reverse_id, "
                "reverse_revision FROM routing_connection_proofs WHERE "
                "validation_version=? AND (forward_id IN ("
                f"{placeholders}) OR reverse_id IN ({placeholders}))",
                (VALIDATION_VERSION, *relation_ids, *relation_ids),
            ).fetchall()
        available = {
            frozenset(
                (
                    RouteReference(str(row[0]), str(row[1])),
                    RouteReference(str(row[2]), str(row[3])),
                )
            )
            for row in rows
        }
        return frozenset(
            pair for pair in pairs if frozenset(pair) in available
        )

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
        """Atomically fence anchors, geometries and their shared proof."""
        start, end = forward.origin_uid, forward.destination_uid
        with self.database.transaction(), self.database.connect() as database:
            if not self._leases_are_owned(database, start, end, owner, now):
                return False
            if (
                self.anchors.get(start, "truck"),
                self.anchors.get(end, "truck"),
            ) != expected or self.relations.provider_revision(
                provider
            ) != provider_revision:
                return False
            self.anchors.put(connection.origin)
            self.anchors.put(connection.destination)
            for relation, route in (
                (forward, connection.forward),
                (reverse, connection.reverse),
            ):
                payload = RoutePayload(
                    route.coordinates,
                    route.distance_km,
                    route.duration_seconds,
                    route.provider,
                )
                if not self.relations.publish(relation, payload, owner, now):
                    raise RuntimeError(
                        "Connection publication lost its lease."
                    )
            self._store_proof(database, connection, forward, reverse, now)
            return True

    @staticmethod
    def _leases_are_owned(
        database: sqlite3.Connection,
        start: str,
        end: str,
        owner: str,
        now: float,
    ) -> bool:
        """Require all leases inside the publication transaction."""
        return all(
            database.execute(
                "SELECT 1 FROM routing_leases WHERE subject=? "
                "AND owner=? AND expires_at>?",
                (subject, owner, now),
            ).fetchone()
            is not None
            for subject in connection_leases(start, end)
        )

    @staticmethod
    def _store_proof(
        database: sqlite3.Connection,
        connection: ValidatedConnection,
        forward: RoutingRelation,
        reverse: RoutingRelation,
        now: float,
    ) -> None:
        """Persist the shared bidirectional proof and anchor snapshot."""
        database.execute(
            "INSERT INTO routing_connection_proofs VALUES "
            "(?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(pair_id) DO UPDATE SET "
            "forward_id=excluded.forward_id, "
            "forward_revision=excluded.forward_revision, "
            "reverse_id=excluded.reverse_id, "
            "reverse_revision=excluded.reverse_revision, "
            "validation_version=excluded.validation_version, "
            "anchors=excluded.anchors, checked_at=excluded.checked_at",
            (
                connection_identity(
                    forward.origin_uid, forward.destination_uid
                ),
                forward.reference.relation_id,
                forward.reference.revision,
                reverse.reference.relation_id,
                reverse.reference.revision,
                VALIDATION_VERSION,
                json.dumps(
                    [asdict(connection.origin), asdict(connection.destination)]
                ),
                now,
            ),
        )
