"""Orchestrate candidates, coverage planning and offer materialization."""

from dataclasses import dataclass
from typing import ClassVar

from app.domain.contracts import ContractOffer
from app.domain.market import (
    CoverageDiagnostic,
    MarketCandidate,
    MarketVehicle,
)
from app.services.contract_factory import ContractFactory
from app.services.market_candidates import MarketCandidateService
from app.services.market_coverage import MarketCoverageService
from app.services.vehicle_coverage import VehicleCoverageService


@dataclass(slots=True)
class MarketGenerator:
    """Coordinate injected steps without implementing their market rules."""

    model_id: ClassVar[str] = ContractFactory.model_id
    cargo_system: ClassVar[str] = ContractFactory.cargo_system
    candidates: MarketCandidateService
    coverage: MarketCoverageService
    factory: ContractFactory
    vehicle_coverage: VehicleCoverageService

    def generate(
        self,
        now: float,
        cities: tuple[str, ...],
        vehicles: tuple[MarketVehicle, ...],
        retained: tuple[ContractOffer, ...] = (),
        prepared: tuple[MarketCandidate, ...] | None = None,
    ) -> tuple[tuple[ContractOffer, ...], tuple[CoverageDiagnostic, ...]]:
        """Return retained and newly materialized offers with diagnostics."""
        candidates = (
            self.candidates.build(cities, vehicles)
            if prepared is None
            else prepared
        )
        plan = self.coverage.plan(cities, candidates, retained)
        plan = self.vehicle_coverage.extend(
            plan, candidates, retained, vehicles, candidates
        )
        created = tuple(
            ContractOffer.from_snapshot(self.factory.build(candidate, now))
            for candidate in plan.selected
        )
        return retained + created, plan.diagnostics
