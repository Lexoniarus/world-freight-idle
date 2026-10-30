"""Fast in-memory market ports for non-persistence behavior tests."""

from app.domain.contracts import ContractOffer
from app.domain.market import VehicleCoverageDiagnostic
from app.domain.market_preparation import PreparationStatus
from app.domain.market_stock import MarketArrival, PreparedTemplate, TradeKey


class FixturePreparationStore:
    """Track demand transitions without creating relational worker tables."""

    def __init__(self) -> None:
        """Start without scheduled work or published diagnostics."""
        self.current: dict[str, PreparationStatus] = {}
        self.coverage: dict[str, tuple[VehicleCoverageDiagnostic, ...]] = {}
        self.sequence = 0

    def request(self, user_id: str, generation: str, now: float) -> None:
        """Store one explicit fixture generation."""
        del now
        self.current[user_id] = PreparationStatus(
            f"fixture-{generation}", generation, "partial", None
        )

    def ensure(self, user_id: str, now: float) -> None:
        """Schedule only when no fixture demand exists."""
        if user_id not in self.current:
            self.invalidate(user_id, now)

    def invalidate(self, user_id: str, now: float) -> None:
        """Advance the fixture generation after changed player state."""
        del now
        self.sequence += 1
        generation = f"generation-{self.sequence}"
        self.current[user_id] = PreparationStatus(
            f"fixture-{self.sequence}", generation, "partial", None
        )

    def diagnostics(
        self, user_id: str
    ) -> tuple[VehicleCoverageDiagnostic, ...]:
        """Return the last published fixture diagnostics."""
        return self.coverage.get(user_id, ())

    def publish_diagnostics(
        self,
        user_id: str,
        generation: str,
        values: tuple[VehicleCoverageDiagnostic, ...],
    ) -> None:
        """Publish diagnostics only for the current generation."""
        status = self.current.get(user_id)
        if status is not None and status.generation == generation:
            self.coverage[user_id] = values

    def status(self, user_id: str) -> PreparationStatus | None:
        """Return current fixture demand."""
        return self.current.get(user_id)

    def next_player(self, now: float) -> str | None:
        """Return the first partial fixture demand."""
        del now
        return next(iter(self.current), None)

    def finish(
        self,
        user_id: str,
        generation: str,
        status: str,
        retry_at: float | None,
        now: float,
    ) -> None:
        """Update a matching fixture generation."""
        del now
        current = self.current.get(user_id)
        if current is not None and current.generation == generation:
            self.current[user_id] = PreparationStatus(
                current.preparation_id,
                generation,
                status,
                retry_at,
            )


class MemoryPlayerMarketStockStore:
    """Provide empty private stock metadata for direct game tests."""

    def __init__(self) -> None:
        """Start without template use, bindings or cursors."""
        self.consumed: set[str] = set()

    def used(self) -> frozenset[str]:
        """Return consumed fixture identifiers."""
        return frozenset(self.consumed)

    def bindings(self) -> dict[str, str]:
        """Return no template bindings for directly seeded offers."""
        return {}

    def issue(self, template_id: str, offer: ContractOffer) -> None:
        """Reject accidental worker publication in this narrow fixture."""
        del template_id, offer
        raise AssertionError("Direct game fixture cannot issue templates.")

    def consume(self, offer_id: str, now: float) -> None:
        """Record consumption without treating offer IDs as templates."""
        del now
        self.consumed.add(offer_id)

    def arrivals(self) -> tuple[MarketArrival, ...]:
        """Return no projected arrival metadata."""
        return ()

    def cursor(self) -> str:
        """Return an empty rotation cursor."""
        return ""

    def pending(self, context: str) -> TradeKey | None:
        """Return no partial candidate."""
        del context
        return None

    def checkpoint(self, context: str, trade: TradeKey | None) -> None:
        """Reject worker checkpointing in this narrow fixture."""
        del context, trade
        raise AssertionError("Direct game fixture cannot checkpoint stock.")


class MemoryMarketTemplateStore:
    """Expose an empty shared template catalogue to direct game tests."""

    def templates(
        self, cities: tuple[str, ...]
    ) -> tuple[PreparedTemplate, ...]:
        """Return no templates for the requested cities."""
        del cities
        return ()

    def scoped_templates(
        self, scopes: tuple[tuple[str, str], ...]
    ) -> tuple[PreparedTemplate, ...]:
        """Return no templates for the requested scopes."""
        del scopes
        return ()

    def add(self, template: PreparedTemplate) -> None:
        """Reject worker publication in this narrow fixture."""
        del template
        raise AssertionError("Direct game fixture cannot store templates.")
