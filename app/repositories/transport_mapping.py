"""Historical transport document encoding and decoding."""

from typing import Any

from app.domain.contracts import ContractOffer
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.domain.world import FacilityLocationSnapshot


def load_transport(value: dict[str, Any]) -> ActiveTransport:
    """Hydrate a current-model transport without consulting any catalogue."""
    geometry = value["route_geojson"]
    if geometry["type"] == "Feature":
        geometry = geometry["geometry"]
    return ActiveTransport(
        id=value["id"],
        vehicle_id=value["vehicle_id"],
        contract=ContractOffer.from_dict(value["contract"]),
        origin=FacilityLocationSnapshot.from_dict(value["origin_snapshot"]),
        destination=FacilityLocationSnapshot.from_dict(
            value["destination_snapshot"]
        ),
        route=RouteSnapshot(
            coordinates=tuple(
                (point[0], point[1]) for point in geometry["coordinates"]
            ),
            distance_km=value["distance_km"],
            duration_seconds=value["routing_duration_seconds"],
            provider=value["provider"],
        ),
        departed_at=value["departed_at"],
        arrives_at=value["arrives_at"],
        payout_eur=value["payout_eur"],
        operating_cost_eur=value["operating_cost_eur"],
        status=value.get("status", "active"),
        settled_at=value.get("settled_at"),
    )


def dump_transport(trip: ActiveTransport) -> dict[str, Any]:
    """Serialize the stable transport envelope at the adapter boundary."""
    return {
        "id": trip.id,
        "vehicle_id": trip.vehicle_id,
        "contract": trip.contract.to_dict(),
        "origin": trip.origin.to_dict(),
        "destination": trip.destination.to_dict(),
        "origin_snapshot": trip.origin.to_dict(),
        "destination_snapshot": trip.destination.to_dict(),
        "route_geojson": {
            "type": "LineString",
            "coordinates": [list(point) for point in trip.route.coordinates],
        },
        "distance_km": trip.route.distance_km,
        "routing_duration_seconds": trip.route.duration_seconds,
        "provider": trip.route.provider,
        "departed_at": trip.departed_at,
        "arrives_at": trip.arrives_at,
        "payout_eur": trip.payout_eur,
        "operating_cost_eur": trip.operating_cost_eur,
        "profit_eur": trip.payout_eur - trip.operating_cost_eur,
    }
