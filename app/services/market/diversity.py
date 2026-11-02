"""Count reusable market diversity without selecting or materializing work."""

from collections import Counter
from dataclasses import dataclass, field

from app.domain.market import MarketCandidate


@dataclass(slots=True)
class MarketDiversity:
    """Track represented relations, cargo groups and destinations."""

    relations: Counter[tuple[str, str, int]] = field(default_factory=Counter)
    cargo: Counter[int] = field(default_factory=Counter)
    destinations: Counter[str] = field(default_factory=Counter)

    def record(
        self,
        origin: str,
        destination: str,
        cargo: int,
        destination_city: str,
    ) -> None:
        """Count one reusable offer across all diversity dimensions."""
        self.relations[origin, destination, cargo] += 1
        self.cargo[cargo] += 1
        self.destinations[destination_city] += 1

    def rank(self, candidate: MarketCandidate) -> tuple[int, int, int]:
        """Prefer unused relations, cargo groups, then destination cities."""
        trade = candidate.trade
        return (
            self.relations[
                trade.origin.facility_uid,
                trade.destination.facility_uid,
                trade.cargo.nhm_row_id,
            ],
            self.cargo[trade.cargo.nhm_row_id],
            self.destinations[trade.destination.address.city.city_uid],
        )
