"""Typed player persistence and atomic-use-case contracts."""

from contextlib import AbstractContextManager
from typing import Protocol

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.transports import ActiveTransport


class GameStateRepository(Protocol):
    """Persist entities for one explicitly bound player identity."""

    def get_player(self) -> PlayerState | None: ...

    def save_player(self, player: PlayerState) -> None: ...

    def list_vehicles(self) -> tuple[OwnedVehicle, ...]: ...

    def save_vehicle(self, vehicle: OwnedVehicle) -> None: ...

    def list_offers(self) -> tuple[ContractOffer, ...]: ...

    def replace_offers(self, offers: tuple[ContractOffer, ...]) -> None: ...

    def remove_offer(self, offer_id: str) -> None: ...

    def list_transports(self) -> tuple[ActiveTransport, ...]: ...

    def save_transport(self, transport: ActiveTransport) -> None: ...

    def reset(self) -> None: ...


class GameUnitOfWork(Protocol):
    """Bind one repository to a shared synchronous write transaction."""

    repository: GameStateRepository

    def transaction(self) -> AbstractContextManager[None]: ...
