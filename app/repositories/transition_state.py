"""Temporary port adapter while composition changes from KV to relational.

This adapter is removed at the relational runtime cutover. It is not an
importer and does not repair incomplete historical payloads.
"""

from contextlib import AbstractContextManager

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.state_ports import GameStateRepository
from app.domain.transports import ActiveTransport
from app.repositories.sqlite_store import SqliteStore
from app.repositories.transport_mapping import dump_transport, load_transport


class TransitionGameRepository:
    """Expose typed entities without leaking KV keys into services."""

    def __init__(self, store: SqliteStore) -> None:
        """Bind the existing adapter to one player namespace."""
        self._store = store

    def get_player(self) -> PlayerState | None:
        """Read initialized counters without inventing absent progress."""
        value = self._store.get_json("player")
        return PlayerState.from_dict(value) if value is not None else None

    def save_player(self, player: PlayerState) -> None:
        """Write validated counters inside the caller's transaction."""
        self._store.set_json("player", player.to_dict())

    def list_vehicles(self) -> tuple[OwnedVehicle, ...]:
        """Hydrate the purchased vehicles in their stored order."""
        return tuple(
            OwnedVehicle.from_dict(value)
            for value in self._store.get_json("vehicles", [])
        )

    def save_vehicle(self, vehicle: OwnedVehicle) -> None:
        """Replace a vehicle in place or append a newly purchased one."""
        values = self._store.get_json("vehicles", [])
        retained = [item for item in values if item["id"] != vehicle.id]
        positions = [item["id"] for item in values]
        index = (
            positions.index(vehicle.id)
            if vehicle.id in positions
            else len(retained)
        )
        retained.insert(index, vehicle.to_dict())
        self._store.set_json("vehicles", retained)

    def list_offers(self) -> tuple[ContractOffer, ...]:
        """Read complete current-format offers without catalogue lookups."""
        return tuple(
            ContractOffer.from_dict(value)
            for value in self._store.get_json("contracts", [])
        )

    def replace_offers(self, offers: tuple[ContractOffer, ...]) -> None:
        """Persist one complete market slice."""
        self._store.set_json(
            "contracts", [offer.to_dict() for offer in offers]
        )

    def remove_offer(self, offer_id: str) -> None:
        """Consume a selected offer without altering the others."""
        self._store.set_json(
            "contracts",
            [
                value
                for value in self._store.get_json("contracts", [])
                if value["id"] != offer_id
            ],
        )

    def list_transports(self) -> tuple[ActiveTransport, ...]:
        """Read active and settled transports through the same typed port."""
        return tuple(
            load_transport(value)
            for value in [
                *self._store.get_json("active_trips", []),
                *self._store.get_json("settled_transports", []),
            ]
        )

    def save_transport(self, transport: ActiveTransport) -> None:
        """Preserve settlement while maintaining the old public read slice."""
        active = [
            value
            for value in self._store.get_json("active_trips", [])
            if value["id"] != transport.id
        ]
        settled = [
            value
            for value in self._store.get_json("settled_transports", [])
            if value["id"] != transport.id
        ]
        payload = {
            **dump_transport(transport),
            "status": transport.status,
            "settled_at": transport.settled_at,
        }
        (active if transport.status == "active" else settled).append(payload)
        self._store.set_json("active_trips", active)
        self._store.set_json("settled_transports", settled)

    def reset(self) -> None:
        """Clear progress without touching accounts or provider caches."""
        self._store.delete_state_keys(
            (
                "player",
                "vehicles",
                "contracts",
                "active_trips",
                "settled_transports",
            )
        )


class TransitionGameUnitOfWork:
    """Share the existing transaction until all relational readers switch."""

    def __init__(self, store: SqliteStore) -> None:
        """Pair the namespace repository with its transaction owner."""
        self.store = store
        self.repository: GameStateRepository = TransitionGameRepository(store)

    def transaction(self) -> AbstractContextManager[None]:
        """Delegate atomicity to the existing SQLite connection owner."""
        return self.store.transaction()
