"""High-level game orchestration."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.domain.contracts import ContractOffer
from app.domain.errors import CatalogueError
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.ports import TruckRouter, VehicleCatalogue, WorldCatalogue
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.domain.world import FacilityLocationSnapshot, FacilityQuery
from app.repositories.sqlite_store import SqliteStore
from app.repositories.transport_mapping import dump_transport, load_transport
from app.services.fleet import (
    create_starter_vehicle,
    resolve_delivery_facility,
)
from app.services.market import MarketGenerator
from app.services.market_scope import MarketScopeResolver
from app.services.pricing import PricingService

LOGGER = logging.getLogger(__name__)

_STATE_KEYS = ("player", "vehicles", "active_trips", "contracts")


class GameService:
    """Orchestrate market, routing, dispatch and idle-time reconciliation."""

    def __init__(
        self,
        store: SqliteStore,
        world: WorldCatalogue,
        router: TruckRouter,
        market: MarketGenerator,
        pricing: PricingService,
        catalogue: VehicleCatalogue,
        market_scope: MarketScopeResolver,
        time_scale: float = 1.0,
    ) -> None:
        self.store = store
        self.world = world
        self.router = router
        self.market = market
        self.pricing = pricing
        self.time_scale = max(0.001, time_scale)
        self.catalogue = catalogue
        self.market_scope = market_scope

    def now(self) -> float:
        """Return the current wall-clock timestamp."""
        return time.time()

    def ensure_initial_state(self) -> None:
        """Atomically create missing state, including for direct callers."""
        with self.store.transaction():
            self._ensure_initial_state()

    def _ensure_initial_state(self) -> None:
        """Initialize missing values inside the caller-owned transaction."""
        if self.store.get_json("player") is None:
            self.store.set_json(
                "player",
                PlayerState(
                    cash=175000,
                    completed=0,
                    reputation=0,
                ).to_dict(),
            )
        if self.store.get_json("vehicles") is None:
            self.store.set_json(
                "vehicles",
                [
                    create_starter_vehicle(
                        self.catalogue,
                        resolve_delivery_facility(self.world),
                    ).to_dict()
                ],
            )
        if self.store.get_json("active_trips") is None:
            legacy = self.store.get_json("active_trip")
            self.store.set_json("active_trips", [legacy] if legacy else [])
            self.store.delete_state_keys(("active_trip",))
        if not self.store.has_json("contracts"):
            self.store.set_json("contracts", [])

    def refresh_market(self, force: bool = False) -> list[dict[str, Any]]:
        """Synchronize the always-available idle-truck market."""
        vehicles = [
            OwnedVehicle.from_dict(item)
            for item in self.store.get_json("vehicles", [])
        ]
        origins = self.market_scope.resolve(vehicles)
        with self.store.transaction():
            retained = [] if force else self._current_market_for_scope(origins)
            try:
                contracts = self._generate_scoped_market(
                    origins,
                    vehicles,
                    retained,
                )
            except CatalogueError:
                if force:
                    raise
                LOGGER.warning(
                    "World market unavailable",
                    extra={"event": "market.catalogue_unavailable"},
                )
                contracts = retained
            self._store_market(contracts, len(origins))
            return contracts

    def _current_market_for_scope(
        self,
        origin_ids: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        """Keep only fresh NHM contracts inside one explicit origin scope."""
        now = self.now()
        scope = set(origin_ids)
        return [
            item
            for item in self.store.get_json("contracts", [])
            if item["expires_at"] > now + 60
            and item.get("market_model") == self.market.model_id
            and item.get("origin_hub_id") in scope
        ]

    def _generate_scoped_market(
        self,
        origin_ids: tuple[str, ...],
        vehicles: list[OwnedVehicle],
        retained: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate and persist one already-resolved market scope."""
        return self.market.generate(
            self.now(),
            list(origin_ids),
            existing_contracts=retained,
            owned_capacities=[v.capacity_tons for v in vehicles],
        )

    def _store_market(
        self,
        contracts: list[dict[str, Any]],
        origin_count: int,
    ) -> None:
        """Persist one complete scoped market only when it changed."""
        current = self.store.get_json("contracts", [])
        if contracts == current:
            return
        self.store.set_json("contracts", contracts)
        LOGGER.info(
            "Contract market refreshed",
            extra={
                "event": "market.refresh",
                "data": {
                    "contract_count": len(contracts),
                    "scope_origin_count": origin_count,
                },
            },
        )

    async def quote_contract(
        self, contract_id: str, vehicle_id: str | None = None
    ) -> dict[str, Any]:
        """Route snapshot coordinates and calculate simulated economics."""
        self.reconcile_arrival()
        contract = self._find_contract(contract_id)
        cost_per_km = 0.62
        if vehicle_id is not None:
            vehicle = self._find_vehicle(
                [
                    OwnedVehicle.from_dict(item)
                    for item in self.store.get_json("vehicles", [])
                ],
                vehicle_id,
            )
            self._validate_dispatch(vehicle, contract)
            cost_per_km = (
                0.62
                if vehicle.operating_cost_eur_per_km is None
                else vehicle.operating_cost_eur_per_km
            )
        expanded = self._expand_contract(contract)
        origin_geo = expanded["origin"]
        destination_geo = expanded["destination"]
        route = await self.router.route(
            origin_geo["lat"],
            origin_geo["lon"],
            destination_geo["lat"],
            destination_geo["lon"],
        )
        economics = self.pricing.quote(
            contract.cargo.name,
            contract.tons,
            route.distance_km,
            cost_per_km,
            contract.rate_eur_per_km_ton,
        )
        LOGGER.info(
            "Contract quoted",
            extra={
                "event": "contract.quote",
                "data": {
                    "contract_id": contract_id,
                    "distance_km": route.distance_km,
                    "duration_seconds": route.duration_seconds,
                    "origin_facility_uid": origin_geo.get("facility_uid"),
                    "destination_facility_uid": destination_geo.get(
                        "facility_uid"
                    ),
                },
            },
        )
        return {
            **route.to_dict(),
            **economics.to_dict(),
            "vehicle_id": vehicle_id,
            "operating_cost_eur_per_km": cost_per_km,
            "origin": origin_geo,
            "destination": destination_geo,
            "contract": contract.to_dict(),
        }

    async def dispatch(
        self,
        contract_id: str,
        vehicle_id: str,
    ) -> dict[str, Any]:
        """Validate and start one real-time delivery."""
        self.reconcile_arrival()
        contract = self._find_contract(contract_id)
        vehicles = [
            OwnedVehicle.from_dict(item)
            for item in self.store.get_json("vehicles", [])
        ]
        vehicle = self._find_vehicle(vehicles, vehicle_id)
        self._validate_dispatch(vehicle, contract)
        quote = await self.quote_contract(contract_id, vehicle_id)
        # Never hold a write transaction across an external API await.
        with self.store.transaction():
            return self._commit_dispatch(contract_id, vehicle_id, quote)

    def _commit_dispatch(
        self,
        contract_id: str,
        vehicle_id: str,
        quote: dict[str, Any],
    ) -> dict[str, Any]:
        """Revalidate and atomically reserve the truck and funds."""
        contract = self._find_contract(contract_id)
        vehicles = [
            OwnedVehicle.from_dict(item)
            for item in self.store.get_json("vehicles", [])
        ]
        vehicle = self._find_vehicle(vehicles, vehicle_id)
        self._validate_dispatch(vehicle, contract)
        # Maintenance may have changed the vehicle during provider awaits.
        economics = self.pricing.quote(
            contract.cargo.name,
            contract.tons,
            quote["distance_km"],
            (
                0.62
                if vehicle.operating_cost_eur_per_km is None
                else vehicle.operating_cost_eur_per_km
            ),
            contract.rate_eur_per_km_ton,
        )
        quote = {**quote, **economics.to_dict()}
        player = PlayerState.from_dict(self.store.get_json("player"))
        player.debit(quote["operating_cost_eur"])

        now = self.now()
        duration_real_seconds = quote["duration_seconds"] / self.time_scale
        trip = self._build_trip(
            contract,
            vehicle_id,
            quote,
            now,
            duration_real_seconds,
        )
        vehicle.start_trip()
        self.store.set_json("player", player.to_dict())
        self.store.set_json(
            "vehicles",
            [item.to_dict() for item in vehicles],
        )
        trips = self.store.get_json("active_trips", [])
        self.store.set_json("active_trips", [*trips, trip])
        self.store.set_json(
            "contracts",
            [
                item
                for item in self.store.get_json("contracts", [])
                if item["id"] != contract_id
            ],
        )
        LOGGER.info(
            "Trip dispatched",
            extra={
                "event": "trip.dispatch",
                "data": {
                    "trip_id": trip["id"],
                    "contract_id": contract_id,
                    "vehicle_id": vehicle_id,
                    "origin_facility_uid": quote["origin"].get("facility_uid"),
                    "destination_facility_uid": quote["destination"].get(
                        "facility_uid"
                    ),
                },
            },
        )
        return trip

    def reconcile_arrival(self) -> bool:
        """Settle arrivals exactly once, including concurrent reads."""
        with self.store.transaction():
            trips = self.store.get_json("active_trips", [])
            now = self.now()
            arrived = [trip for trip in trips if trip["arrives_at"] <= now]
            if not arrived:
                return False
            for trip in arrived:
                self._complete_trip(trip)
            self.store.set_json(
                "active_trips",
                [trip for trip in trips if trip["arrives_at"] > now],
            )
        self.refresh_market()
        return True

    def _complete_trip(self, trip: dict[str, Any]) -> None:
        """Apply one arrival inside the caller's settlement transaction."""
        vehicles = [
            OwnedVehicle.from_dict(item)
            for item in self.store.get_json("vehicles", [])
        ]
        vehicle = self._find_vehicle(vehicles, trip["vehicle_id"])
        if trip["contract"].get("market_model") == self.market.model_id:
            transport = load_transport(trip).settle(self.now())
            destination = transport.destination
            payout = transport.payout_eur
        else:
            # Removed from runtime when the isolated offline importer lands.
            destination = self._legacy_trip_destination(trip)
            payout = int(trip["payout_eur"])
        vehicle.arrive(destination)
        player = PlayerState.from_dict(self.store.get_json("player"))
        player.complete_delivery(payout)
        self.store.set_json("vehicles", [item.to_dict() for item in vehicles])
        self.store.set_json("player", player.to_dict())
        LOGGER.info(
            "Trip completed",
            extra={
                "event": "trip.complete",
                "data": {"trip_id": trip["id"]},
            },
        )

    def _legacy_trip_destination(
        self, trip: dict[str, Any]
    ) -> FacilityLocationSnapshot:
        """Keep the old trip path isolated until the offline import step."""
        raw_destination = (
            trip.get("destination_snapshot")
            or trip.get("destination")
            or self.world.read()
            .get_facility(trip["contract"]["destination_hub_id"])
            .location_snapshot()
            .to_dict()
        )
        return FacilityLocationSnapshot.from_dict(raw_destination)

    def state(self) -> dict[str, Any]:
        """Return the complete client-facing game state."""
        arrived = self.reconcile_arrival()
        if not arrived:
            self.refresh_market(force=False)
        vehicles = [
            self._expand_vehicle(OwnedVehicle.from_dict(vehicle))
            for vehicle in self.store.get_json("vehicles", [])
        ]
        contracts = [
            self._expand_contract(contract)
            for contract in self.store.get_json("contracts", [])
        ]
        return {
            "server_time": self.now(),
            "time_scale": self.time_scale,
            "player": self.store.get_json("player"),
            "vehicles": vehicles,
            "active_trips": self.store.get_json("active_trips"),
            "contracts": contracts,
            "hubs": [vehicle["hub"] for vehicle in vehicles],
        }

    def dashboard(self) -> dict[str, Any]:
        """Return startup state without materializing the contract market."""
        self.reconcile_arrival()
        vehicles = [
            self._expand_vehicle(OwnedVehicle.from_dict(vehicle))
            for vehicle in self.store.get_json("vehicles", [])
        ]
        transports = self.store.get_json("active_trips", [])
        return {
            "server_time": self.now(),
            "time_scale": self.time_scale,
            "player": self.store.get_json("player"),
            "available_contracts": 0,
            "idle_vehicles": sum(
                1 for vehicle in vehicles if vehicle["status"] == "idle"
            ),
            "active_transports": len(transports),
            "featured_contracts": [],
            "vehicles": vehicles,
            "transports": transports,
        }

    def list_contracts(
        self,
        query: FacilityQuery | None = None,
        zoom: float | None = None,
    ) -> list[dict[str, Any]]:
        """Synchronize and return the current lazy market scope."""
        self.reconcile_arrival()
        vehicles = [
            OwnedVehicle.from_dict(item)
            for item in self.store.get_json("vehicles", [])
        ]
        origins = self.market_scope.resolve(vehicles, query, zoom)
        with self.store.transaction():
            retained = self._current_market_for_scope(origins)
            try:
                contracts = self._generate_scoped_market(
                    origins,
                    vehicles,
                    retained,
                )
            except CatalogueError:
                LOGGER.warning(
                    "World market unavailable",
                    extra={"event": "market.catalogue_unavailable"},
                )
                contracts = retained
            self._store_market(contracts, len(origins))
        return [self._expand_contract(item) for item in contracts]

    def refresh_contracts(
        self,
        query: FacilityQuery | None = None,
        zoom: float | None = None,
    ) -> list[dict[str, Any]]:
        """Regenerate the current lazy market scope."""
        self.reconcile_arrival()
        vehicles = [
            OwnedVehicle.from_dict(item)
            for item in self.store.get_json("vehicles", [])
        ]
        origins = self.market_scope.resolve(vehicles, query, zoom)
        with self.store.transaction():
            contracts = self._generate_scoped_market(
                origins,
                vehicles,
                [],
            )
            self._store_market(contracts, len(origins))
        return [self._expand_contract(item) for item in contracts]

    def get_contract(self, contract_id: str) -> dict[str, Any]:
        """Return one enriched market contract."""
        return self._expand_contract(self._find_contract(contract_id))

    def list_vehicles(self) -> list[dict[str, Any]]:
        """Return vehicles enriched with their current real freight hub."""
        self.reconcile_arrival()
        return [
            self._expand_vehicle(OwnedVehicle.from_dict(vehicle))
            for vehicle in self.store.get_json("vehicles", [])
        ]

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any]:
        """Return one enriched vehicle or raise a not-found error."""
        vehicles = [
            OwnedVehicle.from_dict(item)
            for item in self.store.get_json("vehicles", [])
        ]
        vehicle = next(
            (item for item in vehicles if item.id == vehicle_id),
            None,
        )
        if vehicle is None:
            raise KeyError("Fahrzeug nicht gefunden")
        return self._expand_vehicle(vehicle)

    def list_transports(self) -> list[dict[str, Any]]:
        """Return currently active real-time transports."""
        self.reconcile_arrival()
        return self.store.get_json("active_trips", [])

    def get_transport(self, transport_id: str) -> dict[str, Any]:
        """Return one active transport by its stable trip ID."""
        self.reconcile_arrival()
        trip = next(
            (
                item
                for item in self.store.get_json("active_trips", [])
                if item["id"] == transport_id
            ),
            None,
        )
        if trip is None:
            raise KeyError("Transport nicht gefunden")
        return trip

    def reset(self) -> dict[str, Any]:
        """Reset game progress while retaining external-provider caches."""
        with self.store.transaction():
            self.store.delete_state_keys(_STATE_KEYS)
            self.ensure_initial_state()
            return self.state()

    def _find_contract(self, contract_id: str) -> ContractOffer:
        """Find and hydrate one current, non-expired market offer."""
        payload = next(
            (
                item
                for item in self.store.get_json("contracts", [])
                if item["id"] == contract_id
                and item.get("market_model") == self.market.model_id
                and item["expires_at"] > self.now()
            ),
            None,
        )
        if payload is None:
            raise KeyError("Auftrag nicht gefunden")
        contract = ContractOffer.from_dict(payload)
        if not contract.is_available(self.now(), self.market.model_id):
            raise KeyError("Auftrag nicht gefunden")
        return contract

    def _find_vehicle(
        self,
        vehicles: list[OwnedVehicle],
        vehicle_id: str,
    ) -> OwnedVehicle:
        """Find a vehicle by ID or raise a stable validation error."""
        vehicle = next(
            (item for item in vehicles if item.id == vehicle_id),
            None,
        )
        if vehicle is None:
            raise ValueError("Fahrzeug existiert nicht.")
        return vehicle

    def _validate_dispatch(
        self,
        vehicle: OwnedVehicle,
        contract: ContractOffer,
    ) -> None:
        """Delegate vehicle-specific dispatch invariants to the entity."""
        vehicle.validate_dispatch(
            contract.mode,
            contract.origin.facility_uid,
            contract.tons,
        )

    def _build_trip(
        self,
        contract: ContractOffer,
        vehicle_id: str,
        quote: dict[str, Any],
        departed_at: float,
        duration_real_seconds: float,
    ) -> dict[str, Any]:
        """Create the immutable persisted trip snapshot used for tracking."""
        geometry = quote["route_geojson"]
        geometry = geometry.get("geometry", geometry)
        trip = ActiveTransport(
            id=str(uuid.uuid4()),
            vehicle_id=vehicle_id,
            contract=contract,
            origin=contract.origin,
            destination=contract.destination,
            route=RouteSnapshot(
                coordinates=tuple(
                    (point[0], point[1]) for point in geometry["coordinates"]
                ),
                distance_km=quote["distance_km"],
                duration_seconds=quote["duration_seconds"],
                provider=quote["provider"],
            ),
            departed_at=departed_at,
            arrives_at=departed_at + duration_real_seconds,
            payout_eur=quote["payout_eur"],
            operating_cost_eur=quote["operating_cost_eur"],
        )
        return dump_transport(trip)

    def _expand_vehicle(
        self,
        vehicle: OwnedVehicle,
    ) -> dict[str, Any]:
        """Serialize a vehicle with its current real freight hub."""
        snapshot = vehicle.location
        if snapshot is None:
            snapshot = (
                self.world.read()
                .get_facility(vehicle.hub_id)
                .location_snapshot()
            )
        return {**vehicle.to_dict(), "hub": snapshot.to_dict()}

    def _expand_contract(
        self,
        contract: ContractOffer | dict[str, Any],
    ) -> dict[str, Any]:
        """Serialize current offers or explicitly project a legacy alias."""
        if isinstance(contract, ContractOffer):
            return contract.to_dict()
        if "origin" in contract and "destination" in contract:
            return contract
        world = self.world.read()
        return {
            **contract,
            "origin": world.get_facility(contract["origin_hub_id"])
            .location_snapshot()
            .to_dict(),
            "destination": world.get_facility(contract["destination_hub_id"])
            .location_snapshot()
            .to_dict(),
        }
