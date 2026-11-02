"""Vehicle and ownership eligibility at the dispatch boundary."""

from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle
from app.services.market.candidates import MarketCandidateService


@dataclass(frozen=True, slots=True)
class DispatchEligibilityService:
    """Check dispatch eligibility without mutating vehicle state."""

    candidates: MarketCandidateService

    def require_eligible(
        self,
        vehicle: OwnedVehicle,
        offer: ContractOffer,
    ) -> None:
        """Require operating state, location and freight compatibility."""
        vehicle.validate_dispatch(
            offer.mode,
            offer.origin.city.city_uid,
            offer.tons,
        )
        fleet = self.candidates.resolve_fleet((vehicle,))
        if not self.candidates.eligible_ids(offer, fleet):
            raise ValueError("Transportklasse oder Fahrzeuggröße passt nicht.")
