"""Directed routing relations and immutable cached payloads."""

import json
import sqlite3
from collections import OrderedDict
from contextlib import AbstractContextManager
from hashlib import sha256
from sqlite3 import Row

from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingRelation,
)
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.routing.payloads import decode_route_payload


class SqliteRoutingRelationRepository:
    """Own directed relation reads, payloads and fenced publication."""

    def __init__(self, database: SqliteGameDatabase) -> None:
        """Bind relation operations and payload validation to one database."""
        self.database = database
        self._validated_payloads: OrderedDict[str, bool] = OrderedDict()

    def read_transaction(self) -> AbstractContextManager[None]:
        """Share one consistent connection for a bounded evidence read."""
        return self.database.read_transaction()

    def get(self, relation_id: str) -> RoutingRelation | None:
        """Read the currently published revision of a directed relation."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM routing_relations WHERE relation_id=?",
                (relation_id,),
            ).fetchone()
        return self._decode_relation(row) if row is not None else None

    def get_many(
        self, relation_ids: tuple[str, ...]
    ) -> dict[str, RoutingRelation]:
        """Read a bounded relation collection with one set-based query."""
        if not relation_ids:
            return {}
        placeholders = ",".join("?" for _ in relation_ids)
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM routing_relations WHERE relation_id IN ("
                f"{placeholders})",
                relation_ids,
            ).fetchall()
        relations = (self._decode_relation(row) for row in rows)
        return {
            relation.reference.relation_id: relation for relation in relations
        }

    @staticmethod
    def _decode_relation(row: Row) -> RoutingRelation:
        """Decode one database row into immutable routing evidence."""
        values = dict(row)
        reference = RouteReference(
            values.pop("relation_id"), values.pop("revision")
        )
        values.pop("cache_key")
        return RoutingRelation(reference=reference, **values)

    def payload(self, reference: RouteReference) -> RoutePayload | None:
        """Reject missing, stale or malformed cached route documents."""
        document = self._payload_document(reference)
        return decode_route_payload(document) if document is not None else None

    def payload_available(self, reference: RouteReference) -> bool:
        """Validate each immutable payload once, detecting byte changes."""
        document = self._payload_document(reference)
        if document is None:
            return False
        digest = sha256(document.encode()).hexdigest()
        if digest not in self._validated_payloads:
            self._validated_payloads[digest] = (
                decode_route_payload(document) is not None
            )
            if len(self._validated_payloads) > 2048:
                self._validated_payloads.popitem(last=False)
        self._validated_payloads.move_to_end(digest)
        return self._validated_payloads[digest]

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

    def publish(
        self,
        relation: RoutingRelation,
        payload: RoutePayload | None,
        owner: str,
        now: float,
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
        with (
            self.database.transaction(),
            self.database.connect() as connection,
        ):
            lease = connection.execute(
                "SELECT 1 FROM routing_leases "
                "WHERE subject=? AND owner=? AND expires_at>?",
                (reference.relation_id, owner, now),
            ).fetchone()
            if lease is None:
                return False
            if payload is not None:
                assert cache_key is not None
                self._store_payload(connection, cache_key, payload, now)
            connection.execute(
                "INSERT INTO routing_relations VALUES "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(relation_id) DO UPDATE SET "
                "revision=excluded.revision, fingerprint=excluded.fingerprint,"
                "status=excluded.status, cache_key=excluded.cache_key, "
                "failure_category=excluded.failure_category, "
                "retry_at=excluded.retry_at, checked_at=excluded.checked_at",
                (
                    reference.relation_id,
                    reference.revision,
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

    @staticmethod
    def _store_payload(
        connection: sqlite3.Connection,
        cache_key: str,
        payload: RoutePayload,
        now: float,
    ) -> None:
        """Persist one canonical route-cache document."""
        connection.execute(
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

    def provider_revision(self, provider: str) -> str | None:
        """Read the latest actually observed graph revision."""
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
