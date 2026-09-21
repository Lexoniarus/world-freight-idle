"""Immutable NHM compatibility network derived from the world snapshot."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.domain.errors import WorldCatalogueError
from app.domain.world import CargoProfile, Facility

LOGGER = logging.getLogger(__name__)

InboundEntry = tuple[Facility, CargoProfile]
InboundIndex = dict[int, tuple[InboundEntry, ...]]


@dataclass(frozen=True, slots=True)
class TradeOption:
    """One compatible origin/destination NHM relation."""

    origin: Facility
    origin_cargo: CargoProfile
    destination: Facility
    destination_cargo: CargoProfile
    cargo: CargoProfile
    match_type: str


class TradeNetwork:
    """Precompute all NHM trade options for one immutable world revision."""

    def __init__(self, facilities: tuple[Facility, ...]) -> None:
        candidates = tuple(
            facility for facility in facilities if facility.is_routable()
        )
        if len(candidates) < 2:
            raise WorldCatalogueError("Zu wenige geeignete Frachtstandorte.")
        self.facility_uids = tuple(
            facility.facility_uid for facility in candidates
        )
        inbound_by_row, inbound_by_ancestor = self._index_inbound_cargo(
            candidates
        )
        self._options_by_origin = {
            origin.facility_uid: self._build_trade_options(
                origin,
                inbound_by_row,
                inbound_by_ancestor,
            )
            for origin in candidates
        }
        LOGGER.info(
            "NHM trade network indexed",
            extra={
                "event": "market.trade_network_indexed",
                "data": {
                    "origins": len(candidates),
                    "trade_options": sum(
                        len(options)
                        for options in self._options_by_origin.values()
                    ),
                },
            },
        )

    def options_for(self, facility_uid: str) -> tuple[TradeOption, ...]:
        """Return immutable precomputed trade options for one origin."""
        try:
            return self._options_by_origin[facility_uid]
        except KeyError as exc:
            raise WorldCatalogueError(
                "Kein kompatibler NHM-Warenstrom für diesen Standort."
            ) from exc

    @staticmethod
    def _index_inbound_cargo(
        candidates: tuple[Facility, ...],
    ) -> tuple[InboundIndex, InboundIndex]:
        """Index inbound profiles by exact NHM node and every ancestor."""
        by_row: dict[int, list[InboundEntry]] = {}
        by_ancestor: dict[int, list[InboundEntry]] = {}
        for facility in candidates:
            for profile in facility.inbound_cargo():
                entry = (facility, profile)
                by_row.setdefault(profile.nhm_row_id, []).append(entry)
                for ancestor_row_id in profile.ancestor_row_ids:
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
        for origin_cargo in origin.outbound_cargo():
            matches = list(
                inbound_by_ancestor.get(origin_cargo.nhm_row_id, ())
            )
            for ancestor_row_id in origin_cargo.ancestor_row_ids:
                matches.extend(inbound_by_row.get(ancestor_row_id, ()))
            for destination, destination_cargo in matches:
                if destination.facility_uid == origin.facility_uid:
                    continue
                key = (
                    origin_cargo.nhm_row_id,
                    destination.facility_uid,
                    destination_cargo.nhm_row_id,
                )
                if key in seen:
                    continue
                seen.add(key)
                cargo = max(
                    (origin_cargo, destination_cargo),
                    key=lambda item: len(item.ancestor_row_ids),
                )
                match_type = (
                    "exact"
                    if origin_cargo.nhm_row_id == destination_cargo.nhm_row_id
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
        if not options:
            raise WorldCatalogueError(
                "Kein kompatibler NHM-Warenstrom für diesen Standort."
            )
        return tuple(options)
