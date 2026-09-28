"""Shared immutable supply and private, once-per-account consumption ports."""

from dataclasses import dataclass
from typing import Protocol

from app.domain.contracts import ContractOffer
from app.domain.market import MarketVehicle
from app.domain.validation import require_identity, require_integer
from app.domain.world import FacilityLocationSnapshot

TradeKey = tuple[str, str, int]


@dataclass(frozen=True, slots=True)
class StockPolicy:
    """Share one policy between preparation, diagnostics and selection."""

    visible_per_band: int = 3
    reserve_per_band: int = 10
    arrival_horizon_seconds: int = 3600

    def __post_init__(self) -> None:
        """Reject policies that cannot retain the visible selection."""
        require_integer(self.visible_per_band, "Visible stock")
        require_integer(self.reserve_per_band, "Reserve stock")
        require_integer(self.arrival_horizon_seconds, "Arrival horizon")
        if not (
            0 < self.visible_per_band <= self.reserve_per_band
            and self.arrival_horizon_seconds > 0
        ):
            raise ValueError("Invalid market stock policy.")


@dataclass(frozen=True, slots=True)
class MarketArrival:
    """Read only the saved facts needed for advance market preparation."""

    transport_id: str
    vehicle_id: str
    destination: FacilityLocationSnapshot
    arrives_at: float


@dataclass(frozen=True, slots=True)
class MarketDemand:
    """Separate a planning location from the mutable owned vehicle."""

    vehicle: MarketVehicle
    available_at: float
    transport_id: str | None = None
    catalogue_only: bool = False


@dataclass(frozen=True, slots=True)
class PreparedTemplate:
    """Keep a reusable trade seed independent of private offer ownership."""

    template_id: str
    model_id: str
    city_uid: str
    offer: ContractOffer

    def __post_init__(self) -> None:
        """Require model identity and a non-expiring, located trade seed."""
        require_identity(self.template_id, "Template ID")
        require_identity(self.model_id, "Template model")
        if (
            self.city_uid != self.offer.origin.city.city_uid
            or self.offer.market_context is None
            or self.offer.expires_at is not None
        ):
            raise ValueError("Template context differs from its offer.")


class MarketStockStore(Protocol):
    """Persist global templates and a bound account's durable stock state."""

    def templates(
        self, cities: tuple[str, ...]
    ) -> tuple[PreparedTemplate, ...]: ...

    def used(self) -> frozenset[str]: ...

    def bindings(self) -> dict[str, str]: ...

    def add(self, template: PreparedTemplate) -> None: ...

    def issue(self, template_id: str, offer: ContractOffer) -> None: ...

    def consume(self, offer_id: str, now: float) -> None: ...

    def arrivals(self, until: float) -> tuple[MarketArrival, ...]: ...

    def cursor(self) -> str: ...

    def pending(self, context: str) -> TradeKey | None: ...

    def checkpoint(self, context: str, trade: TradeKey | None) -> None: ...
