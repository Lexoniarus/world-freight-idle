"""Name the cohesive market collaborators wired by the composition root."""

from dataclasses import dataclass
from typing import ClassVar

from app.services.contract_factory import ContractFactory
from app.services.market_candidates import MarketCandidateService
from app.services.vehicle_coverage import VehicleCoverageService


@dataclass(slots=True)
class MarketComponents:
    """Bundle market collaborators without hiding generation side effects."""

    model_id: ClassVar[str] = ContractFactory.model_id
    cargo_system: ClassVar[str] = ContractFactory.cargo_system
    candidates: MarketCandidateService
    factory: ContractFactory
    vehicle_coverage: VehicleCoverageService
