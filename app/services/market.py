"""Orchestrate candidates, coverage planning and offer materialization."""

from dataclasses import dataclass
from typing import ClassVar

from app.domain.contracts import ContractOffer
from app.domain.market import CoverageDiagnostic, MarketVehicle
from app.services.contract_factory import ContractFactory
from app.services.market_candidates import MarketCandidateService
from app.services.market_coverage import MarketCoverageService


@dataclass(slots=True)
class MarketGenerator:
    """Coordinate injected steps without implementing their market rules."""

    model_id: ClassVar[str] = ContractFactory.model_id
    cargo_system: ClassVar[str] = ContractFactory.cargo_system
    candidates: MarketCandidateService
    coverage: MarketCoverageService
    factory: ContractFactory

    def generate(
        self,
        now: float,
        cities: tuple[str, ...],
        vehicles: tuple[MarketVehicle, ...],
        retained: tuple[ContractOffer, ...] = (),
    ) -> tuple[tuple[ContractOffer, ...], tuple[CoverageDiagnostic, ...]]:
        """Return retained and newly materialized offers with diagnostics."""
        candidates = self.candidates.build(cities, vehicles)
        plan = self.coverage.plan(cities, candidates, retained)
        created = tuple(
            ContractOffer.from_snapshot(self.factory.build(candidate, now))
            for candidate in plan.selected
        )
        return retained + created, plan.diagnostics
