"""Resolve vehicle-aware market candidates from NHM trade relations."""

from collections.abc import Sequence

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle
from app.domain.market import (
    CompatibleVehicle,
    MarketCandidate,
    MarketVehicle,
    TradeOption,
)
from app.domain.market_calculations import (
    distance_band,
    evidence_weight,
    great_circle_km,
)
from app.domain.market_compatibility import (
    can_carry_offer,
    market_vehicle,
    vehicle_suitability,
)
from app.domain.market_profiles import NhmMarketProfile
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.world import WorldSnapshot
from app.domain.world_scopes import WorldScope
from app.services.trade_network import TradeNetwork


class MarketCandidateService:
    """Cache reference relations while deriving current fleet compatibility."""

    def __init__(
        self, world: WorldCatalogue, catalogue: VehicleCatalogue
    ) -> None:
        """Keep reference ports and initially empty revision indexes."""
        self.world = world
        self.catalogue = catalogue
        self._snapshot: WorldSnapshot | None = None
        self._network: TradeNetwork | None = None
        self._profiles: dict[int, NhmMarketProfile] = {}

    def reference(self) -> WorldSnapshot:
        """Refresh derived reference indexes only for a changed revision."""
        snapshot = self.world.read()
        if snapshot != self._snapshot:
            self._network = TradeNetwork(snapshot.facilities)
            self._profiles = {
                p.nhm_row_id: p for p in snapshot.market_profiles
            }
            self._snapshot = snapshot
        return snapshot

    def resolve_fleet(
        self, vehicles: Sequence[OwnedVehicle]
    ) -> tuple[MarketVehicle, ...]:
        """Resolve idle models explicitly, preserving purchased capacities."""
        models = {model.id: model for model in self.catalogue.list_models()}
        snapshot = self.reference()
        result = []
        for vehicle in vehicles:
            if vehicle.status != "idle":
                continue
            model = models.get(vehicle.model_id or "")
            if model is None:
                raise ValueError(
                    "Fahrzeugmodell ist nicht auflösbar; Bestand prüfen."
                )
            location = (
                vehicle.location
                or WorldScope(snapshot)
                .facility(vehicle.facility_uid)
                .location_snapshot()
            )
            result.append(market_vehicle(vehicle, model, location))
        return tuple(result)

    def build(
        self,
        cities: tuple[str, ...],
        vehicles: tuple[MarketVehicle, ...],
    ) -> tuple[MarketCandidate, ...]:
        """Generate active origins against the complete destination index."""
        snapshot = self.reference()
        assert self._network is not None
        candidates = []
        for facility in snapshot.facilities:
            if (
                facility.address.city.city_uid not in cities
                or not facility.is_routable()
            ):
                continue
            fleet = tuple(
                v
                for v in vehicles
                if v.city_uid == facility.address.city.city_uid
            )
            for trade in self._network.options_for(facility.facility_uid):
                candidate = self._candidate(trade, fleet)
                if candidate is not None:
                    candidates.append(candidate)
        return tuple(candidates)

    def _candidate(
        self,
        trade: TradeOption,
        fleet: tuple[MarketVehicle, ...],
    ) -> MarketCandidate | None:
        """Combine a trade profile, distance and compatible vehicle weights."""
        profile = self._profiles[trade.cargo.nhm_row_id]
        compatible = tuple(
            CompatibleVehicle(vehicle, weight)
            for vehicle in fleet
            if (weight := vehicle_suitability(vehicle, profile)) > 0
        )
        if not compatible:
            return None
        assert trade.origin.coordinates is not None
        assert trade.destination.coordinates is not None
        distance = great_circle_km(
            trade.origin.coordinates, trade.destination.coordinates
        )
        load = next(
            p
            for p in profile.distance_profiles
            if p.distance_band == distance_band(distance)
        )
        weight = (
            evidence_weight(trade)
            * load.selection_weight
            * max(v.suitability for v in compatible)
        )
        if weight <= 0:
            return None
        return MarketCandidate(
            trade, profile, load, distance, compatible, weight
        )

    def eligible_ids(
        self,
        offer: ContractOffer,
        fleet: tuple[MarketVehicle, ...],
    ) -> tuple[str, ...]:
        """Return compatible owned IDs without reserving a vehicle."""
        profile = self._profiles.get(offer.cargo.nhm_row_id)
        context = offer.market_context
        if (
            profile is None
            or context is None
            or context.transport_class != profile.transport_class
        ):
            return ()
        return tuple(
            v.vehicle_id for v in fleet if can_carry_offer(v, offer, profile)
        )

    def structurally_current(self, offer: ContractOffer) -> bool:
        """Require a live routable relation and a selectable distance band."""
        assert self._snapshot is not None
        assert self._network is not None
        facilities = {f.facility_uid: f for f in self._snapshot.facilities}
        origin = facilities.get(offer.origin.facility_uid)
        destination = facilities.get(offer.destination.facility_uid)
        if (
            origin is None
            or destination is None
            or not origin.is_routable()
            or not destination.is_routable()
        ):
            return False
        profile = self._profiles.get(offer.cargo.nhm_row_id)
        context = offer.market_context
        if profile is None or context is None:
            return False
        if not any(
            p.distance_band == context.distance_band and p.selection_weight > 0
            for p in profile.distance_profiles
        ):
            return False
        return any(
            t.destination.facility_uid == offer.destination.facility_uid
            and t.cargo == offer.cargo
            and t.origin_cargo == offer.origin_cargo_evidence
            and t.destination_cargo == offer.destination_cargo_evidence
            for t in self._network.options_for(origin.facility_uid)
        )
