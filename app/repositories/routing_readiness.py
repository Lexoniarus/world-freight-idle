"""Global routing infrastructure on the existing relational runtime."""

import json
from collections import OrderedDict
from contextlib import AbstractContextManager
from dataclasses import asdict
from hashlib import sha256
from typing import Any

from app.domain.routing_anchors import VALIDATION_VERSION, RoutingAnchor
from app.domain.routing_connections import (
    ValidatedConnection,
    connection_identity,
    connection_leases,
)
from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingAttempt,
    RoutingRelation,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.routing_anchors import SqliteRoutingAnchorRepository

SCHEMA = """
CREATE TABLE IF NOT EXISTS routing_connection_proofs (
    pair_id TEXT PRIMARY KEY,
    forward_id TEXT NOT NULL, forward_revision TEXT NOT NULL,
    reverse_id TEXT NOT NULL, reverse_revision TEXT NOT NULL,
    validation_version TEXT NOT NULL, anchors TEXT NOT NULL,
    checked_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_provider_revisions (
    provider TEXT PRIMARY KEY, revision TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_relations (
    relation_id TEXT PRIMARY KEY, revision TEXT NOT NULL,
    origin_uid TEXT NOT NULL, destination_uid TEXT NOT NULL,
    fingerprint TEXT NOT NULL, status TEXT NOT NULL,
    cache_key TEXT, failure_category TEXT, retry_at REAL,
    checked_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_leases (
    subject TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS routing_attempts (
    attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id TEXT NOT NULL, method TEXT NOT NULL, outcome TEXT NOT NULL,
    observed_at REAL NOT NULL, trace_id TEXT NOT NULL,
    candidate_lat REAL, candidate_lon REAL,
    provider_code INTEGER, provider_message TEXT
);
CREATE TABLE IF NOT EXISTS offer_route_references (
    user_id TEXT NOT NULL, contract_id TEXT NOT NULL,
    relation_id TEXT NOT NULL, revision TEXT NOT NULL,
    PRIMARY KEY (user_id, contract_id),
    FOREIGN KEY (user_id, contract_id)
        REFERENCES contract_offers(user_id, contract_id) ON DELETE CASCADE
);
"""


def _load_relation(row: Any) -> RoutingRelation:
    """Decode one adapter row into a directed routing relation."""
    values = dict(row)
    reference = RouteReference(
        values.pop("relation_id"), values.pop("revision")
    )
    values.pop("cache_key")
    return RoutingRelation(reference=reference, **values)


class SqliteRoutingReadinessStore:
    """Own routing SQL, atomic publication and lease fencing."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Create additive infrastructure without changing game columns."""
        self.database = database
        self._validated_payloads: OrderedDict[str, bool] = OrderedDict()
        self.anchors = SqliteRoutingAnchorRepository(database)
        with database.connect() as connection:
            connection.executescript(SCHEMA)

    def read_transaction(self) -> AbstractContextManager[None]:
        """Share one consistent connection for a bounded evidence read."""
        return self.database.read_transaction()

    def get(self, relation_id: str) -> RoutingRelation | None:
        """Read the currently published revision of a directed relation."""
        return self.get_many((relation_id,)).get(relation_id)

    def get_many(
        self, relation_ids: tuple[str, ...]
    ) -> dict[str, RoutingRelation]:
        """Read a bounded relation set with one relational query."""
        if not relation_ids:
            return {}
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM routing_relations WHERE relation_id IN "
                "(SELECT value FROM json_each(?))",
                (json.dumps(relation_ids),),
            ).fetchall()
        return {
            relation.reference.relation_id: relation
            for row in rows
            if (relation := _load_relation(row)) is not None
        }

    def available_payloads(
        self, references: tuple[RouteReference, ...]
    ) -> frozenset[RouteReference]:
        """Validate a bounded revision set after one payload query."""
        if not references:
            return frozenset()
        expected = {(ref.relation_id, ref.revision): ref for ref in references}
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT r.relation_id, r.revision, c.payload FROM "
                "routing_relations r JOIN route_cache c "
                "ON c.cache_key=r.cache_key WHERE r.status='ready' AND "
                "r.relation_id IN (SELECT value FROM json_each(?))",
                (json.dumps(tuple(uid for uid, _ in expected)),),
            ).fetchall()
        return frozenset(
            expected[key]
            for row in rows
            if (key := (str(row[0]), str(row[1]))) in expected
            and self._valid_payload(str(row[2]))
        )

    def connected_references(
        self, relation_ids: tuple[str, ...]
    ) -> frozenset[tuple[RouteReference, RouteReference]]:
        """Read all current connection proofs touching a relation set."""
        if not relation_ids:
            return frozenset()
        document = json.dumps(relation_ids)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT forward_id, forward_revision, reverse_id, "
                "reverse_revision FROM routing_connection_proofs WHERE "
                "validation_version=? AND (forward_id IN "
                "(SELECT value FROM json_each(?)) OR reverse_id IN "
                "(SELECT value FROM json_each(?)))",
                (VALIDATION_VERSION, document, document),
            ).fetchall()
        return frozenset(
            (
                RouteReference(str(row[0]), str(row[1])),
                RouteReference(str(row[2]), str(row[3])),
            )
            for row in rows
        )

    def _valid_payload(self, document: str) -> bool:
        """Memoize validation by immutable payload digest."""
        digest = sha256(document.encode()).hexdigest()
        if digest not in self._validated_payloads:
            self._validated_payloads[digest] = (
                decode_route_payload(document) is not None
            )
            if len(self._validated_payloads) > 2048:
                self._validated_payloads.popitem(last=False)
        self._validated_payloads.move_to_end(digest)
        return self._validated_payloads[digest]

    def payload_available(self, reference: RouteReference) -> bool:
        """Validate each immutable payload once, detecting any byte change."""
        document = self._payload_document(reference)
        return document is not None and self._valid_payload(document)

    def _payload_document(self, reference: RouteReference) -> str | None:
        """Read the exact revision without constructing geometry objects."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT c.payload FROM routing_relations r "
                "JOIN route_cache c ON c.cache_key=r.cache_key "
                "WHERE r.relation_id=? AND r.revision=? AND r.status='ready'",
                (reference.relation_id, reference.revision),
            ).fetchone()
        return row[0] if row else None

    def payload(self, reference: RouteReference) -> RoutePayload | None:
        """Reject missing, stale or malformed cached route documents."""
        document = self._payload_document(reference)
        return decode_route_payload(document) if document is not None else None

    def acquire(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool:
        """Acquire only an absent or expired globally shared lease."""
        if expires_at <= now:
            raise ValueError("Lease must expire in the future.")
        with self.database.connect() as connection:
            result = connection.execute(
                "INSERT INTO routing_leases VALUES (?, ?, ?) "
                "ON CONFLICT(subject) DO UPDATE SET owner=excluded.owner, "
                "expires_at=excluded.expires_at "
                "WHERE routing_leases.expires_at<=?",
                (subject, owner, expires_at, now),
            )
            return result.rowcount == 1

    def renew(
        self, subject: str, owner: str, now: float, expires_at: float
    ) -> bool:
        """Extend a still-owned lease without resurrecting expired work."""
        if expires_at <= now:
            raise ValueError("Lease must expire in the future.")
        with self.database.connect() as connection:
            result = connection.execute(
                "UPDATE routing_leases SET expires_at=? "
                "WHERE subject=? AND owner=? AND expires_at>?",
                (expires_at, subject, owner, now),
            )
            return result.rowcount == 1

    def release(self, subject: str, owner: str) -> None:
        """Release only this owner's lease, including cancellation cleanup."""
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM routing_leases WHERE subject=? AND owner=?",
                (subject, owner),
            )

    def publish(
        self,
        relation: RoutingRelation,
        payload: RoutePayload | None,
        owner: str,
        now: float,
        worker_owner: str | None = None,
    ) -> bool:
        """Atomically fence the writer and publish metrics with readiness."""
        if (relation.status == "ready") != (payload is not None):
            raise ValueError("Ready relation requires a payload.")
        reference = relation.reference
        cache_key = (
            f"readiness:v1:{reference.relation_id}:{reference.revision}"
            if payload is not None
            else None
        )
        with self.database.transaction(), self.database.connect() as conn:
            if worker_owner is not None and not self.holds(
                "worker:market-preparation", worker_owner, now
            ):
                return False
            lease = conn.execute(
                "SELECT 1 FROM routing_leases "
                "WHERE subject=? AND owner=? AND expires_at>?",
                (relation.reference.relation_id, owner, now),
            ).fetchone()
            if lease is None:
                return False
            if payload is not None:
                conn.execute(
                    "INSERT INTO route_cache VALUES (?, ?, ?) "
                    "ON CONFLICT(cache_key) DO UPDATE SET "
                    "payload=excluded.payload, updated_at=excluded.updated_at",
                    (
                        cache_key,
                        json.dumps(
                            {
                                "coordinates": payload.coordinates,
                                "road_distance_km": payload.road_distance_km,
                                "provider_duration_seconds": (
                                    payload.provider_duration_seconds
                                ),
                                "provider": payload.provider,
                            }
                        ),
                        now,
                    ),
                )
            conn.execute(
                "INSERT INTO routing_relations VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(relation_id) DO UPDATE SET "
                "revision=excluded.revision, fingerprint=excluded.fingerprint,"
                "status=excluded.status, cache_key=excluded.cache_key, "
                "failure_category=excluded.failure_category, "
                "retry_at=excluded.retry_at, checked_at=excluded.checked_at",
                (
                    relation.reference.relation_id,
                    relation.reference.revision,
                    relation.origin_uid,
                    relation.destination_uid,
                    relation.fingerprint,
                    relation.status,
                    cache_key,
                    relation.failure_category,
                    relation.retry_at,
                    relation.checked_at,
                ),
            )
            return True

    def connected(
        self,
        forward: RouteReference,
        reverse: RouteReference,
    ) -> bool:
        """Require both current directional revisions in one shared proof."""
        with self.database.connect() as conn:
            row = conn.execute(
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
    ) -> bool:
        """Atomically fence anchors, both geometries and their shared proof."""
        anchors = self.anchors
        start, end = forward.origin_uid, forward.destination_uid
        with self.database.transaction(), self.database.connect() as conn:
            if worker_owner is not None and not self.holds(
                "worker:market-preparation", worker_owner, now
            ):
                return False
            for subject in connection_leases(start, end):
                if (
                    conn.execute(
                        "SELECT 1 FROM routing_leases WHERE subject=? "
                        "AND owner=? AND expires_at>?",
                        (subject, owner, now),
                    ).fetchone()
                    is None
                ):
                    return False
            if (
                anchors.get(start, "truck"),
                anchors.get(end, "truck"),
            ) != expected or self.provider_revision(
                provider
            ) != provider_revision:
                return False
            anchors.put(connection.origin)
            anchors.put(connection.destination)
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
                if not self.publish(relation, payload, owner, now):
                    raise RuntimeError(
                        "Connection publication lost its lease."
                    )
            conn.execute(
                "INSERT INTO routing_connection_proofs VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(pair_id) DO UPDATE SET "
                "forward_id=excluded.forward_id, "
                "forward_revision=excluded.forward_revision, "
                "reverse_id=excluded.reverse_id, "
                "reverse_revision=excluded.reverse_revision, "
                "validation_version=excluded.validation_version, "
                "anchors=excluded.anchors, checked_at=excluded.checked_at",
                (
                    connection_identity(start, end),
                    forward.reference.relation_id,
                    forward.reference.revision,
                    reverse.reference.relation_id,
                    reverse.reference.revision,
                    VALIDATION_VERSION,
                    json.dumps(
                        [
                            asdict(connection.origin),
                            asdict(connection.destination),
                        ]
                    ),
                    now,
                ),
            )
            return True

    def append_attempt(self, attempt: RoutingAttempt) -> None:
        """Append evidence; previous failures are never overwritten."""
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO routing_attempts "
                "(subject_id, method, outcome, observed_at, trace_id, "
                "candidate_lat, candidate_lon, provider_code, "
                "provider_message)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                tuple(asdict(attempt).values()),
            )

    def holds(self, subject: str, owner: str, now: float) -> bool:
        """Check ownership in the caller's publication transaction."""
        with self.database.connect() as conn:
            return (
                conn.execute(
                    "SELECT 1 FROM routing_leases WHERE subject=? "
                    "AND owner=? AND expires_at>?",
                    (subject, owner, now),
                ).fetchone()
                is not None
            )

    def provider_revision(self, provider: str) -> str | None:
        """Read the latest actually observed graph revision for a provider."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT revision FROM routing_provider_revisions "
                "WHERE provider=?",
                (provider,),
            ).fetchone()
        return row[0] if row else None

    def observe_provider_revision(self, provider: str, revision: str) -> None:
        """Persist known provider metadata independently of player state."""
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO routing_provider_revisions VALUES (?, ?) "
                "ON CONFLICT(provider) DO UPDATE SET "
                "revision=excluded.revision",
                (provider, revision),
            )


def decode_route_payload(document: str) -> RoutePayload | None:
    """Validate canonical provider geometry independently of availability."""
    try:
        values = json.loads(document)
        values["coordinates"] = tuple(
            tuple(point) for point in values["coordinates"]
        )
        return RoutePayload(**values)
    except (ValueError, KeyError, TypeError):
        return None


class SqliteOfferRouteStore:
    """Project open-offer references without changing snapshot envelopes."""

    def __init__(self, database: SqliteGameDatabase, user_id: str) -> None:
        """Bind infrastructure references to one authenticated owner."""
        self.database = database
        self.user_id = user_id

    def get(self, offer_id: str) -> RouteReference | None:
        """Read only the bound player's open-offer reference."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT relation_id, revision FROM offer_route_references "
                "WHERE user_id=? AND contract_id=?",
                (self.user_id, offer_id),
            ).fetchone()
        return RouteReference(*row) if row is not None else None

    def replace(
        self, references: tuple[tuple[str, RouteReference], ...]
    ) -> None:
        """Replace bindings atomically, joining the market transaction."""
        with (
            self.database.transaction(),
            self.database.connect() as connection,
        ):
            current = tuple(
                (row[0], RouteReference(row[1], row[2]))
                for row in connection.execute(
                    "SELECT contract_id, relation_id, revision "
                    "FROM offer_route_references WHERE user_id=? "
                    "ORDER BY contract_id",
                    (self.user_id,),
                )
            )
            if current == tuple(sorted(references, key=lambda item: item[0])):
                return
            connection.execute(
                "DELETE FROM offer_route_references WHERE user_id=?",
                (self.user_id,),
            )
            connection.executemany(
                "INSERT INTO offer_route_references VALUES (?, ?, ?, ?)",
                (
                    (self.user_id, offer_id, ref.relation_id, ref.revision)
                    for offer_id, ref in references
                ),
            )
