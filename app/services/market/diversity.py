"""Count reusable market diversity without selecting or materializing work."""

from collections import Counter
from dataclasses import dataclass, field

from app.domain.contracts import ContractOffer
from app.domain.market import MarketCandidate


@dataclass(slots=True)
class MarketDiversity:
    """Track represented relations, cargo groups and destinations."""

    relations: Counter[tuple[str, str]] = field(default_factory=Counter)
    cargo: Counter[int] = field(default_factory=Counter)
    destinations: Counter[str] = field(default_factory=Counter)
    tonnages: Counter[float] = field(default_factory=Counter)

    def record(
        self,
        origin: str,
        destination: str,
        cargo: int,
        destination_city: str,
    ) -> None:
        """Count one reusable offer across all diversity dimensions."""
        self.relations[origin, destination] += 1
        self.cargo[cargo] += 1
        self.destinations[destination_city] += 1

    def rank(self, candidate: MarketCandidate) -> tuple[int, int, int]:
        """Prefer unused relations, cargo groups, then destination cities."""
        trade = candidate.trade
        return (
            self.relations[
                trade.origin.facility_uid,
                trade.destination.facility_uid,
            ],
            self.cargo[trade.cargo.nhm_row_id],
            self.destinations[trade.destination.address.city.city_uid],
        )

    def record_offer(self, offer: ContractOffer) -> None:
        """Count one visible offer including its generated tonnage."""
        self.record(
            offer.origin.facility_uid,
            offer.destination.facility_uid,
            offer.cargo.nhm_row_id,
            offer.destination.city.city_uid,
        )
        self.tonnages[offer.tons] += 1

    def rank_offer(self, offer: ContractOffer) -> tuple[int, int, int, int]:
        """Prefer a new trade, cargo, destination and finally tonnage."""
        return (
            self.relations[
                offer.origin.facility_uid,
                offer.destination.facility_uid,
            ],
            self.cargo[offer.cargo.nhm_row_id],
            self.destinations[offer.destination.city.city_uid],
            self.tonnages[offer.tons],
        )
