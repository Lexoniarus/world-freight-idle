"""Read certified routing evidence without invoking external providers."""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from hashlib import sha256

from app.domain.ports import WorldCatalogue
from app.domain.readiness_ports import RoutingReadinessStore
from app.domain.routing_anchor_ports import RoutingAnchorStore
from app.domain.routing_anchors import (
    NEGATIVE_TTL,
    VALIDATION_VERSION,
    RoutingAnchor,
)
from app.domain.routing_connections import anchor_identity
from app.domain.routing_readiness import (
    RoutePayload,
    RouteReference,
    RoutingRelation,
    relation_identity,
)
from app.domain.world import WorldSnapshot


@dataclass
class ReadinessView:
    """Keep evidence memoization scoped to one synchronous read operation."""

    relations: dict[tuple[str, str], RoutingRelation | None] = field(
        default_factory=dict
    )
    fingerprints: dict[tuple[str, str], str] = field(default_factory=dict)
    stored_relations: dict[tuple[str, str], RoutingRelation | None] = field(
        default_factory=dict
    )
    anchors: dict[str, RoutingAnchor | None] = field(default_factory=dict)
    connected: dict[tuple[str, str], bool] = field(default_factory=dict)


class RoutingEvidenceReader:
    """Load versioned proofs through one request-scoped read snapshot."""

    def __init__(
        self,
        store: RoutingReadinessStore,
        anchor_store: RoutingAnchorStore,
        world: WorldCatalogue,
        provider_identity: str,
        clock: Callable[[], float],
        maximum_snap_distance_m: float,
        provider_revision: Callable[[], str | None] | None = None,
    ) -> None:
        """Inject immutable policy and the repositories needed for reads."""
        self.store = store
        self.anchor_store = anchor_store
        self.world = world
        self.provider_identity = provider_identity
        self.clock = clock
        self.maximum_snap_distance_m = maximum_snap_distance_m
        self.provider_revision = provider_revision
        self._view: ContextVar[ReadinessView | None] = ContextVar(
            "readiness_view", default=None
        )
        self._world_snapshot: WorldSnapshot | None = None
        self._locations: dict = {}

    @contextmanager
    def reading(
        self,
        pairs: Iterable[tuple[str, str]] = (),
    ) -> Iterator[None]:
        """Reuse synchronous evidence without leaking it across requests."""
        requested = tuple(dict.fromkeys(pairs))
        current = self._view.get()
        if current is not None:
            self._preload(current, requested)
            yield
            return
        view = ReadinessView()
        token = self._view.set(view)
        try:
            with self.store.read_transaction():
                self._preload(view, requested)
                yield
        finally:
            self._view.reset(token)

    def _preload(
        self,
        view: ReadinessView,
        pairs: tuple[tuple[str, str], ...],
    ) -> None:
        """Load relation, anchor and proof evidence in bounded queries."""
        missing = tuple(
            pair for pair in pairs if pair not in view.stored_relations
        )
        if not missing:
            return
        directed = tuple(
            dict.fromkeys(
                pair
                for origin, destination in missing
                for pair in ((origin, destination), (destination, origin))
            )
        )
        relation_ids = tuple(relation_identity(*pair) for pair in directed)
        stored = self.store.get_many(relation_ids)
        for pair, relation_id in zip(directed, relation_ids):
            view.stored_relations[pair] = stored.get(relation_id)
        facility_uids = tuple(
            sorted({uid for pair in directed for uid in pair})
        )
        anchors = self.anchor_store.get_many(facility_uids, "truck")
        for uid in facility_uids:
            view.anchors[uid] = anchors.get(uid)
        references = []
        reference_pairs = []
        for pair in missing:
            forward = view.stored_relations[pair]
            reverse = view.stored_relations[(pair[1], pair[0])]
            if (
                forward is not None
                and reverse is not None
                and forward.status == "ready"
                and reverse.status == "ready"
            ):
                reference_pair = (forward.reference, reverse.reference)
                references.append(reference_pair)
                reference_pairs.append((pair, reference_pair))
            else:
                view.connected[pair] = False
        connected = self.store.connected_many(tuple(references))
        for pair, reference_pair in reference_pairs:
            value = reference_pair in connected
            view.connected[pair] = value
            view.connected[(pair[1], pair[0])] = value

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
                (
                    view.anchors[origin]
                    if view is not None and origin in view.anchors
                    else self.anchor_store.get(origin, "truck")
                ),
                (
                    view.anchors[destination]
                    if view is not None and destination in view.anchors
                    else self.anchor_store.get(destination, "truck")
                ),
            )
        )
        facts = (
            VALIDATION_VERSION,
            self.provider_identity,
            self.provider_revision() if self.provider_revision else None,
            self.maximum_snap_distance_m,
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
        view = self._view.get()
        key = (origin, destination)
        relation = (
            view.stored_relations[key]
            if view is not None and key in view.stored_relations
            else self.store.get(relation_identity(origin, destination))
        )
        if relation is None:
            return None
        now = self.clock()
        stale = relation.fingerprint != self.fingerprint(origin, destination)
        if relation.status == "ready":
            reverse_key = (destination, origin)
            reverse = (
                view.stored_relations[reverse_key]
                if view is not None and reverse_key in view.stored_relations
                else self.store.get(relation_identity(destination, origin))
            )
            connected = (
                view.connected[key]
                if view is not None and key in view.connected
                else (
                    reverse is not None
                    and self.store.connected(
                        relation.reference, reverse.reference
                    )
                )
            )
            stale = stale or (
                reverse is None
                or reverse.status != "ready"
                or reverse.fingerprint != self.fingerprint(destination, origin)
                or not connected
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
