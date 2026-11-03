"""Name the cohesive market collaborators wired by the composition root."""

from dataclasses import dataclass
from typing import ClassVar

from app.services.market.candidates import MarketCandidateService
from app.services.market.contract_factory import ContractFactory
from app.services.market.vehicle_coverage import VehicleCoverageService


@dataclass(slots=True)
class MarketGenerationServices:
    """Expose the services that generate and assess market supply."""

    cargo_system: ClassVar[str] = ContractFactory.cargo_system
    candidates: MarketCandidateService
    contract_factory: ContractFactory
    coverage: VehicleCoverageService
