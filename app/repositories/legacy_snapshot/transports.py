"""Historical active-transport decoding."""

from dataclasses import dataclass
from typing import Any

from app.domain.journeys import unmetered_journey
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.repositories.legacy_import_values import (
    TRANSPORT_FIELDS,
    read_legacy_route,
    reject_unknown_fields,
)
from app.repositories.legacy_snapshot.contracts import LegacyContractReader
from app.repositories.legacy_snapshot.locations import LegacyLocationReader


@dataclass(frozen=True, slots=True)
class LegacyTransportReader:
    """Restore saved transport snapshots without rerouting."""

    locations: LegacyLocationReader
    contracts: LegacyContractReader

    def read(
        self, value: dict[str, Any], path: str = "transport"
    ) -> ActiveTransport:
        """Copy the saved route, timeline and economics; never reroute."""
        reject_unknown_fields(value, TRANSPORT_FIELDS, path)
        coordinates = read_legacy_route(
            value["route_geojson"], path + ".route_geojson"
        )
        if (
            value["profit_eur"]
            != value["payout_eur"] - value["operating_cost_eur"]
        ):
            raise ValueError("Conflicting historical economics.")
        if (
            value["origin"] != value["origin_snapshot"]
            or value["destination"] != value["destination_snapshot"]
        ):
            raise ValueError("Conflicting transport endpoint snapshots.")
        return ActiveTransport(
            id=value["id"],
            vehicle_id=value["vehicle_id"],
            contract=self.contracts.read_historical_contract(
                value["contract"], path + ".contract"
            ),
            origin=self.locations.read(
                value["origin_snapshot"], path + ".origin_snapshot"
            ),
            destination=self.locations.read(
                value["destination_snapshot"],
                path + ".destination_snapshot",
            ),
            route=RouteSnapshot(
                coordinates,
                value["distance_km"],
                value["routing_duration_seconds"],
                value["provider"],
            ),
            departed_at=value["departed_at"],
            arrives_at=value["arrives_at"],
            journey=unmetered_journey(
                value["distance_km"],
                value["arrives_at"] - value["departed_at"],
            ),
            payout_eur=value["payout_eur"],
            operating_cost_eur=value["operating_cost_eur"],
            status=value.get("status", "active"),
            settled_at=value.get("settled_at"),
        )
