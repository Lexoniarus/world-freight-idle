"""High-level game orchestration."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.domain.errors import CatalogueError
from app.domain.ports import TruckRouter, VehicleCatalogue, WorldCatalogue
from app.repositories.sqlite_store import SqliteStore
from app.services.fleet import (
    create_starter_vehicle,
    resolve_delivery_facility,
)
from app.services.market import MarketGenerator
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
        time_scale: float = 1.0,
    ) -> None:
        self.store = store
        self.world = world
        self.router = router
        self.market = market
        self.pricing = pricing
        self.time_scale = max(0.001, time_scale)
        self.catalogue = catalogue

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
                {"cash": 175000, "completed": 0, "reputation": 0},
            )
        if self.store.get_json("vehicles") is None:
            self.store.set_json(
                "vehicles",
                [
                    create_starter_vehicle(
                        self.catalogue,
                        resolve_delivery_facility(self.world),
                    )
                ],
            )
        if self.store.get_json("active_trips") is None:
            legacy = self.store.get_json("active_trip")
            self.store.set_json("active_trips", [legacy] if legacy else [])
            self.store.delete_state_keys(("active_trip",))
        if self.store.get_json("contracts") is None:
            self.refresh_market(force=True)

    def refresh_market(self, force: bool = False) -> list[dict[str, Any]]:
        """Refresh expired market contracts or explicitly regenerate them."""
        with self.store.transaction():
            return self._refresh_market(force)

    def _refresh_market(self, force: bool) -> list[dict[str, Any]]:
        """Replace a market inside the caller's write transaction."""
        now = self.now()
        current = self.store.get_json("contracts", [])
        retained = (
            []
            if force
            else [
                item
                for item in current
                if item["expires_at"] > now + 60
                and item.get("market_model") == self.market.model_id
            ]
        )

        vehicles = self.store.get_json("vehicles", [])
        idle_hubs = [
            vehicle["hub_id"]
            for vehicle in vehicles
            if vehicle["status"] == "idle"
        ]
        if not idle_hubs:
            idle_hubs = ["berlin_westhafen"]
        try:
            contracts = self.market.generate(
                now,
                idle_hubs,
                existing_contracts=retained,
                owned_capacities=[v["capacity_tons"] for v in vehicles],
            )
        except CatalogueError:
            if force:
                raise
            LOGGER.warning(
                "World market unavailable",
                extra={
                    "event": "market.catalogue_unavailable",
                },
            )
            surviving = [
                item
                for item in current
                if item["expires_at"] > now
                and item.get("market_model") == self.market.model_id
            ]
            if surviving != current:
                self.store.set_json("contracts", surviving)
            return surviving
        if contracts == current:
            return current
        self.store.set_json("contracts", contracts)
        LOGGER.info(
            "Contract market refreshed",
            extra={
                "event": "market.refresh",
                "data": {
                    "contract_count": len(contracts),
                    "origin_facility_uids": [
                        c["origin_facility_uid"] for c in contracts
                    ],
                },
            },
        )
        return contracts

    async def quote_contract(
        self, contract_id: str, vehicle_id: str | None = None
    ) -> dict[str, Any]:
        """Route snapshot coordinates and calculate simulated economics."""
        self.reconcile_arrival()
        contract = self._find_contract(contract_id)
        cost_per_km = 0.62
        if vehicle_id is not None:
            vehicle = self._find_vehicle(
                self.store.get_json("vehicles", []), vehicle_id
            )
            self._validate_dispatch(vehicle, contract)
            cost_per_km = vehicle.get("operating_cost_eur_per_km", 0.62)
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
            contract["cargo"],
            float(contract["tons"]),
            route.distance_km,
            cost_per_km,
            contract.get("rate_eur_per_km_ton"),
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
            "contract": contract,
        }

    async def dispatch(
        self,
        contract_id: str,
        vehicle_id: str,
    ) -> dict[str, Any]:
        """Validate and start one real-time delivery."""
        self.reconcile_arrival()
        contract = self._find_contract(contract_id)
        vehicles = self.store.get_json("vehicles", [])
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
        vehicles = self.store.get_json("vehicles", [])
        vehicle = self._find_vehicle(vehicles, vehicle_id)
        self._validate_dispatch(vehicle, contract)
        # Maintenance may have changed the vehicle during provider awaits.
        economics = self.pricing.quote(
            contract["cargo"],
            float(contract["tons"]),
            quote["distance_km"],
            vehicle.get("operating_cost_eur_per_km", 0.62),
            contract.get("rate_eur_per_km_ton"),
        )
        quote = {**quote, **economics.to_dict()}
        player = self.store.get_json("player")
        if player["cash"] < quote["operating_cost_eur"]:
            raise ValueError("Nicht genug Geld für die Betriebskosten.")

        now = self.now()
        duration_real_seconds = quote["duration_seconds"] / self.time_scale
        trip = self._build_trip(
            contract,
            vehicle_id,
            quote,
            now,
            duration_real_seconds,
        )
        player["cash"] -= quote["operating_cost_eur"]
        vehicle["status"] = "enroute"
        self.store.set_json("player", player)
        self.store.set_json("vehicles", vehicles)
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
        vehicles = self.store.get_json("vehicles", [])
        vehicle = self._find_vehicle(vehicles, trip["vehicle_id"])
        destination = (
            trip.get("destination_snapshot")
            or trip.get("destination")
            or self.world.read()
            .get_facility(trip["contract"]["destination_hub_id"])
            .to_dict()
        )
        vehicle["hub_id"] = (
            destination.get("facility_uid") or destination["id"]
        )
        vehicle["facility_uid"] = vehicle["hub_id"]
        vehicle["location_snapshot"] = destination
        vehicle["status"] = "idle"
        player = self.store.get_json("player")
        player["cash"] += trip["payout_eur"]
        player["completed"] += 1
        player["reputation"] += 1
        self.store.set_json("vehicles", vehicles)
        self.store.set_json("player", player)
        LOGGER.info(
            "Trip completed",
            extra={
                "event": "trip.complete",
                "data": {"trip_id": trip["id"]},
            },
        )

    def state(self) -> dict[str, Any]:
        """Return the complete client-facing game state."""
        self.reconcile_arrival()
        self.refresh_market(force=False)
        return {
            "server_time": self.now(),
            "time_scale": self.time_scale,
            "player": self.store.get_json("player"),
            "vehicles": self.store.get_json("vehicles"),
            "active_trips": self.store.get_json("active_trips"),
            "contracts": [
                self._expand_contract(contract)
                for contract in self.store.get_json("contracts", [])
            ],
            "hubs": [v["hub"] for v in self.list_vehicles()],
        }

    def dashboard(self) -> dict[str, Any]:
        """Return the product dashboard projection for the browser client."""
        self.reconcile_arrival()
        contracts = self.list_contracts()
        vehicles = self.list_vehicles()
        transports = self.list_transports()
        return {
            "server_time": self.now(),
            "time_scale": self.time_scale,
            "player": self.store.get_json("player"),
            "available_contracts": len(contracts),
            "idle_vehicles": sum(
                1 for vehicle in vehicles if vehicle["status"] == "idle"
            ),
            "active_transports": len(transports),
            "featured_contracts": contracts[:3],
            "transports": transports,
        }

    def list_contracts(self) -> list[dict[str, Any]]:
        """Return market contracts enriched with their real addresses."""
        self.reconcile_arrival()
        self.refresh_market(force=False)
        return [
            self._expand_contract(contract)
            for contract in self.store.get_json("contracts", [])
        ]

    def get_contract(self, contract_id: str) -> dict[str, Any]:
        """Return one enriched market contract."""
        return self._expand_contract(self._find_contract(contract_id))

    def list_vehicles(self) -> list[dict[str, Any]]:
        """Return vehicles enriched with their current real freight hub."""
        self.reconcile_arrival()
        return [
            self._expand_vehicle(vehicle)
            for vehicle in self.store.get_json("vehicles", [])
        ]

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any]:
        """Return one enriched vehicle or raise a not-found error."""
        vehicles = self.store.get_json("vehicles", [])
        vehicle = next(
            (item for item in vehicles if item["id"] == vehicle_id),
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

    def _find_contract(self, contract_id: str) -> dict[str, Any]:
        """Find an active market contract or raise a stable not-found error."""
        contract = next(
            (
                item
                for item in self.store.get_json("contracts", [])
                if item["id"] == contract_id
                and item["expires_at"] > self.now()
                and item.get("market_model") == self.market.model_id
            ),
            None,
        )
        if contract is None:
            raise KeyError("Auftrag nicht gefunden")
        return contract

    def _find_vehicle(
        self,
        vehicles: list[dict[str, Any]],
        vehicle_id: str,
    ) -> dict[str, Any]:
        """Find a vehicle by ID or raise a stable validation error."""
        vehicle = next(
            (item for item in vehicles if item["id"] == vehicle_id),
            None,
        )
        if vehicle is None:
            raise ValueError("Fahrzeug existiert nicht.")
        return vehicle

    def _validate_dispatch(
        self,
        vehicle: dict[str, Any],
        contract: dict[str, Any],
    ) -> None:
        """Validate mode, location, status and payload constraints."""
        if vehicle["status"] != "idle":
            raise ValueError("Fahrzeug ist nicht verfügbar.")
        if vehicle["mode"] != contract["mode"]:
            raise ValueError("Fahrzeugtyp passt nicht zum Auftrag.")
        if vehicle["hub_id"] != contract["origin_hub_id"]:
            raise ValueError("Fahrzeug steht nicht an der Abholadresse.")
        if float(vehicle["capacity_tons"]) < float(contract["tons"]):
            raise ValueError("Fahrzeugkapazität reicht nicht aus.")

    def _build_trip(
        self,
        contract: dict[str, Any],
        vehicle_id: str,
        quote: dict[str, Any],
        departed_at: float,
        duration_real_seconds: float,
    ) -> dict[str, Any]:
        """Create the immutable persisted trip snapshot used for tracking."""
        return {
            "id": str(uuid.uuid4()),
            "contract": contract,
            "vehicle_id": vehicle_id,
            "origin": quote["origin"],
            "destination": quote["destination"],
            "origin_snapshot": contract.get("origin", quote["origin"]),
            "destination_snapshot": contract.get(
                "destination", quote["destination"]
            ),
            "route_geojson": quote["route_geojson"],
            "distance_km": quote["distance_km"],
            "routing_duration_seconds": quote["duration_seconds"],
            "provider": quote["provider"],
            "departed_at": departed_at,
            "arrives_at": departed_at + duration_real_seconds,
            "payout_eur": quote["payout_eur"],
            "operating_cost_eur": quote["operating_cost_eur"],
            "profit_eur": quote["profit_eur"],
        }

    def _expand_vehicle(self, vehicle: dict[str, Any]) -> dict[str, Any]:
        """Attach the vehicle's current real freight hub."""
        snapshot = vehicle.get("location_snapshot")
        if snapshot is None:
            snapshot = (
                self.world.read().get_facility(vehicle["hub_id"]).to_dict()
            )
        return {**vehicle, "hub": snapshot}

    def _expand_contract(self, contract: dict[str, Any]) -> dict[str, Any]:
        """Attach real endpoint addresses to a generated contract payload."""
        if "origin" in contract and "destination" in contract:
            return contract
        world = self.world.read()
        return {
            **contract,
            "origin": world.get_facility(contract["origin_hub_id"]).to_dict(),
            "destination": world.get_facility(
                contract["destination_hub_id"]
            ).to_dict(),
        }
