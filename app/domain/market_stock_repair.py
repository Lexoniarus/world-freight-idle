"""Typed boundaries for explicit offline market-stock correction."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.domain.contracts import ContractOffer
from app.domain.market_stock import PreparedTemplate


@dataclass(frozen=True, slots=True)
class RepairableMarketOffer:
    """Describe one private offer without exposing it in reports."""

    user_id: str
    contract_id: str
    template_id: str
    offer: ContractOffer
    removable: bool


@dataclass(frozen=True, slots=True)
class MarketStockRepairContext:
    """Bind one stored city, model and distance band to alternatives."""

    user_id: str
    city_uid: str
    model_id: str
    distance_band: str
    offers: tuple[RepairableMarketOffer, ...]
    alternatives: tuple[PreparedTemplate, ...]


@dataclass(frozen=True, slots=True)
class MarketStockRemoval:
    """Identify one approved private offer deletion."""

    user_id: str
    contract_id: str
    template_id: str


@dataclass(frozen=True, slots=True)
class MarketStockRepairPlan:
    """Keep private repair identities separate from public counts."""

    checked_contexts: int
    affected_contexts: int
    removals: tuple[MarketStockRemoval, ...]


@dataclass(frozen=True, slots=True)
class MarketStockRepairReport:
    """Report only aggregate maintenance facts."""

    checked_contexts: int
    affected_contexts: int
    offers_to_remove: int
    players_to_requeue: int


class MarketStockRepairReader(Protocol):
    """Read persisted repair inputs without deciding market quality."""

    def load_contexts(self) -> tuple[MarketStockRepairContext, ...]: ...


class MarketStockRepairExecutor(Protocol):
    """Create one verified repaired copy from an approved plan."""

    def create_repaired_copy(
        self,
        plan: MarketStockRepairPlan,
        target: Path,
        archive: Path,
        now: float,
    ) -> None: ...
