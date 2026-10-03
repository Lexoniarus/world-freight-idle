"""Shared immutable supply and private, once-per-account consumption ports."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.domain.contracts import ContractOffer
from app.domain.market import MarketVehicle
from app.domain.validation import require_identity, require_integer
from app.domain.world import FacilityLocationSnapshot

TradeKey = tuple[str, str, int]
StockScope = tuple[str, str, str]


@dataclass(frozen=True, slots=True)
class MarketStockRepairPlan:
    """Describe only rows that a guarded maintenance run may change."""

    scopes: tuple[StockScope, ...]
    offers: tuple[tuple[str, str], ...]
    templates: tuple[str, ...]
    users: tuple[str, ...]

    def report(self) -> dict[str, int]:
        """Expose aggregate counts without account or market identities."""
        return {
            "duplicate_scopes": len(self.scopes),
            "offers_to_remove": len(self.offers),
            "templates_to_remove": len(self.templates),
            "affected_accounts": len(self.users),
        }


@dataclass(frozen=True, slots=True)
class StockPolicy:
    """Share one policy between preparation, diagnostics and selection."""

    visible_per_band: int = 3
    reserve_per_band: int = 10

    def __post_init__(self) -> None:
        """Reject policies that cannot retain the visible selection."""
        require_integer(self.visible_per_band, "Visible stock")
        require_integer(self.reserve_per_band, "Reserve stock")
        if not 0 < self.visible_per_band <= self.reserve_per_band:
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


@dataclass(frozen=True, slots=True)
class TemplateStockLevel:
    """Count reusable templates for one global city/model/distance band."""

    city_uid: str
    model_id: str
    distance_band: str
    count: int


class MarketTemplateStore(Protocol):
    """Persist player-independent market templates."""

    def templates(
        self, cities: tuple[str, ...]
    ) -> tuple[PreparedTemplate, ...]: ...

    def scoped_templates(
        self, scopes: tuple[tuple[str, str], ...]
    ) -> tuple[PreparedTemplate, ...]: ...

    def levels(self) -> tuple[TemplateStockLevel, ...]: ...

    def add(self, template: PreparedTemplate) -> None: ...


class MarketStockStore(MarketTemplateStore, Protocol):
    """Persist a bound account's durable market stock state."""

    def used(self) -> frozenset[str]: ...

    def bindings(self) -> dict[str, str]: ...

    def issue(self, template_id: str, offer: ContractOffer) -> None: ...

    def consume(self, offer_id: str, now: float) -> None: ...

    def arrivals(self) -> tuple[MarketArrival, ...]: ...

    def cursor(self) -> str: ...

    def pending(self, context: str) -> TradeKey | None: ...

    def checkpoint(self, context: str, trade: TradeKey | None) -> None: ...

    def reconcile_pending(
        self,
        active_contexts: tuple[str, ...],
        completed_context: str | None,
    ) -> None: ...


class MarketStockMaintenancePort(Protocol):
    """Plan and apply an explicitly archived stock repair."""

    def duplicate_scopes(self) -> tuple[StockScope, ...]: ...

    def inspect(
        self, repairable_scopes: frozenset[StockScope]
    ) -> MarketStockRepairPlan: ...

    def apply(
        self,
        plan: MarketStockRepairPlan,
        archive: Path,
        now: float,
    ) -> dict[str, int | str]: ...
