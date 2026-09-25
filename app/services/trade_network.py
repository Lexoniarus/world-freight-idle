"""Immutable NHM compatibility network derived from the world snapshot."""

from __future__ import annotations

import logging

from app.domain.cargo import FacilityNhmProfile
from app.domain.errors import WorldCatalogueError
from app.domain.market import TradeOption
from app.domain.world import Facility

LOGGER = logging.getLogger(__name__)

InboundEntry = tuple[Facility, FacilityNhmProfile]
InboundIndex = dict[int, tuple[InboundEntry, ...]]


class TradeNetwork:
    """Index destinations and lazily derive NHM trades for one revision."""

    def __init__(self, facilities: tuple[Facility, ...]) -> None:
        """Index routable destinations without computing origin relations."""
        candidates = tuple(
            facility for facility in facilities if facility.is_routable()
        )
        if len(candidates) < 2:
            raise WorldCatalogueError("Zu wenige geeignete Frachtstandorte.")
        inbound_by_row, inbound_by_ancestor = self._index_inbound_profiles(
            candidates
        )
        self._origins = {f.facility_uid: f for f in candidates}
        self._inbound_by_row = inbound_by_row
        self._inbound_by_ancestor = inbound_by_ancestor
        self._options_by_origin: dict[str, tuple[TradeOption, ...]] = {}
        LOGGER.info(
            "NHM trade network indexed",
            extra={
                "event": "market.trade_network_indexed",
                "data": {
                    "origins": len(candidates),
                },
            },
        )

    def options_for(self, facility_uid: str) -> tuple[TradeOption, ...]:
        """Resolve and cache trade options for one requested origin."""
        if facility_uid not in self._origins:
            raise WorldCatalogueError("Unbekannter Frachtstandort.")
        if facility_uid not in self._options_by_origin:
            self._options_by_origin[facility_uid] = self._build_trade_options(
                self._origins[facility_uid],
                self._inbound_by_row,
                self._inbound_by_ancestor,
            )
        return self._options_by_origin[facility_uid]

    @staticmethod
    def _index_inbound_profiles(
        candidates: tuple[Facility, ...],
    ) -> tuple[InboundIndex, InboundIndex]:
        """Index inbound profiles by exact NHM node and every ancestor."""
        by_row: dict[int, list[InboundEntry]] = {}
        by_ancestor: dict[int, list[InboundEntry]] = {}
        for facility in candidates:
            for profile in facility.inbound_profiles():
                entry = (facility, profile)
                by_row.setdefault(profile.product.nhm_row_id, []).append(entry)
                for ancestor_row_id in profile.product.ancestor_row_ids:
                    by_ancestor.setdefault(ancestor_row_id, []).append(entry)
        return (
            {key: tuple(value) for key, value in by_row.items()},
            {key: tuple(value) for key, value in by_ancestor.items()},
        )

    @staticmethod
    def _build_trade_options(
        origin: Facility,
        inbound_by_row: InboundIndex,
        inbound_by_ancestor: InboundIndex,
    ) -> tuple[TradeOption, ...]:
        """Build compatible NHM trades from one origin without SQL access."""
        options: list[TradeOption] = []
        seen: set[tuple[int, str, int]] = set()
        for origin_cargo in origin.outbound_profiles():
            matches = list(
                inbound_by_ancestor.get(origin_cargo.product.nhm_row_id, ())
            )
            for ancestor_row_id in origin_cargo.product.ancestor_row_ids:
                matches.extend(inbound_by_row.get(ancestor_row_id, ()))
            for destination, destination_cargo in matches:
                if destination.facility_uid == origin.facility_uid:
                    continue
                key = (
                    origin_cargo.product.nhm_row_id,
                    destination.facility_uid,
                    destination_cargo.product.nhm_row_id,
                )
                if key in seen:
                    continue
                seen.add(key)
                cargo = max(
                    (origin_cargo.product, destination_cargo.product),
                    key=lambda item: len(item.ancestor_row_ids),
                )
                match_type = (
                    "exact"
                    if origin_cargo.product.nhm_row_id
                    == destination_cargo.product.nhm_row_id
                    else "ancestor"
                )
                options.append(
                    TradeOption(
                        origin,
                        origin_cargo,
                        destination,
                        destination_cargo,
                        cargo,
                        match_type,
                    )
                )
        return tuple(options)
