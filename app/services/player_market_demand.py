"""Schedule and report one player's durable market demand."""

from collections.abc import Callable
from dataclasses import dataclass

from app.domain.market import VehicleCoverageDiagnostic
from app.domain.market_preparation import PreparationStatus, PreparationStore
from app.domain.state_ports import TransactionBoundary


@dataclass(slots=True)
class PlayerMarketDemandService:
    """Own player demand generations and published coverage diagnostics."""

    user_id: str
    jobs: PreparationStore
    clock: Callable[[], float]
    transactions: TransactionBoundary

    def request(self, *, changed: bool = False) -> None:
        """Schedule durable demand without building candidate structures."""
        if changed:
            with self.transactions.transaction():
                self.jobs.invalidate(self.user_id, self.clock())
            return
        self.jobs.ensure(self.user_id, self.clock())

    def status(self) -> PreparationStatus | None:
        """Return the public progress for this player's current generation."""
        return self.jobs.status(self.user_id)

    def diagnostics(self) -> tuple[VehicleCoverageDiagnostic, ...]:
        """Return the last atomically published vehicle coverage."""
        return self.jobs.diagnostics(self.user_id)

    def publish_diagnostics(
        self,
        generation: str,
        values: tuple[VehicleCoverageDiagnostic, ...],
    ) -> None:
        """Publish coverage only for the matching demand generation."""
        self.jobs.publish_diagnostics(self.user_id, generation, values)
