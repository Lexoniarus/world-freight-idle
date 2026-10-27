"""Vehicle and ownership eligibility at the dispatch boundary."""

from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle
from app.domain.ports import WorldCatalogue
from app.domain.world_scopes import WorldScope
from app.services.market_candidates import MarketCandidateService


@dataclass(frozen=True, slots=True)
class DispatchEligibilityService:
    """Validate a vehicle without coupling freight supply to future staff."""

    world: WorldCatalogue
    candidates: MarketCandidateService

    def validate(
        self,
        vehicle: OwnedVehicle,
        offer: ContractOffer,
    ) -> None:
        """Require location, operating state and freight compatibility."""
        if vehicle.location is None:
            vehicle.restore_location(
                WorldScope(self.world.read())
                .facility(vehicle.facility_uid)
                .location_snapshot()
            )
        vehicle.validate_dispatch(
            offer.mode,
            offer.origin.city.city_uid,
            offer.tons,
        )
        fleet = self.candidates.resolve_fleet((vehicle,))
        if not self.candidates.eligible_ids(offer, fleet):
            raise ValueError("Transportklasse oder Fahrzeuggröße passt nicht.")
