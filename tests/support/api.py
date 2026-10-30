"""Shared HTTP application doubles and local settings for tests."""

import shutil
from dataclasses import replace
from pathlib import Path

from app.config import Settings
from app.domain.contracts import HistoricalContractSnapshot
from app.domain.game import PlayerState
from app.domain.journeys import unmetered_journey
from app.domain.market_preparation import PreparationStatus
from app.domain.pricing import PriceQuote
from app.domain.results import ContractQuote, GameSnapshot
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.providers.routing import RoutingError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeGame:
    """Expose deterministic application responses behind the game facade."""

    def __init__(self, game) -> None:
        self.market_lifecycle = game.market_lifecycle
        self.offer = replace(game.state_repository.list_offers()[0], id="c1")
        self.vehicle = game.state_repository.list_vehicles()[0]
        self.route = RouteSnapshot(((1, 1), (2, 2)), 10, 20, "fixture")
        self.trip = ActiveTransport(
            "trip1",
            self.vehicle.id,
            HistoricalContractSnapshot.from_offer(self.offer),
            self.offer.origin,
            self.offer.destination,
            self.route,
            1,
            21,
            1000,
            100,
            journey=unmetered_journey(
                self.route.distance_km,
                20,
            ),
        )

    def now(self) -> float:
        """Return the stable API test time."""
        return 1

    def dashboard(self) -> GameSnapshot:
        """Return one stable dashboard projection."""
        return GameSnapshot(
            1, 1, PlayerState(1, 0, 0), (self.vehicle,), (self.trip,)
        )

    def contract_choices(self, offers, vehicle_id=None):
        """Project every supplied offer as eligible for the fixture truck."""
        from app.domain.results import AvailableContract

        return tuple(
            AvailableContract(offer, ("truck_01",)) for offer in offers
        )

    def market_presentation(self, offers, vehicle_id):
        """Project one deterministic market response."""
        from app.domain.results import MarketPresentation

        return MarketPresentation(
            self.contract_choices(offers, vehicle_id),
            self.vehicle_coverage(),
            self.preparation_status(),
        )

    def read_market(self, vehicle_id, *, refresh=False):
        """Return the stable or refreshed market response."""
        offers = self.refresh_contracts() if refresh else (self.offer,)
        return self.market_presentation(offers, vehicle_id)

    def vehicle_coverage(self):
        """Delegate coverage to the configured lifecycle."""
        return self.market_lifecycle.vehicle_diagnostics()

    def list_contracts(self):
        """Return the stable fixture offer."""
        return [self.offer]

    def preparation_status(self) -> PreparationStatus:
        """Return deterministic partial preparation progress."""
        return PreparationStatus(
            "preparation1", "generation1", "partial", 30
        )

    def get_contract(self, contract_id):
        """Return or reject the requested fixture offer."""
        if contract_id == "missing":
            raise KeyError("missing")
        return self.offer

    async def quote_contract(self, contract_id, vehicle_id) -> ContractQuote:
        """Return or reject one deterministic quote."""
        if contract_id == "routing-error":
            raise RoutingError("down")
        if contract_id == "missing":
            raise KeyError("missing")
        return ContractQuote(
            self.offer,
            self.route,
            PriceQuote(1000, 100, 900),
            vehicle_id,
            0.62,
        )

    async def dispatch(self, contract_id, vehicle_id) -> ActiveTransport:
        """Return or reject one deterministic transport."""
        if contract_id == "bad":
            raise ValueError("bad")
        if contract_id == "missing":
            raise KeyError("missing")
        if contract_id == "routing-error":
            raise RoutingError("down")
        return self.trip

    def refresh_contracts(self):
        """Return one visibly refreshed fixture offer."""
        return [replace(self.offer, id="fresh")]

    def list_vehicles(self):
        """Return the fixture vehicle."""
        return (self.vehicle,)

    def get_vehicle(self, vehicle_id):
        """Return or reject the fixture vehicle."""
        if vehicle_id == "missing":
            raise KeyError("missing")
        return self.vehicle

    def list_transports(self):
        """Return the fixture transport."""
        return (self.trip,)

    def get_transport(self, transport_id):
        """Return or reject the fixture transport."""
        if transport_id == "missing":
            raise KeyError("missing")
        return self.trip


def make_settings(tmp_path: Path) -> Settings:
    """Create isolated local application settings and catalogue copies."""
    catalogue = tmp_path / "vehicles.sqlite3"
    shutil.copyfile(
        REPOSITORY_ROOT / "data/world_freight_vehicle_catalog.sqlite3",
        catalogue,
    )
    world = tmp_path / "world.sqlite3"
    shutil.copyfile(
        REPOSITORY_ROOT
        / "data/world_freight_company_facility_mvp.sqlite3",
        world,
    )
    return Settings(
        world_catalogue_path=world,
        vehicle_catalogue_path=catalogue,
        base_dir=tmp_path,
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "game.db",
        nominatim_url="https://n.test",
        valhalla_url="https://v.test",
        http_user_agent="agent",
        valhalla_client_id="client",
        request_timeout_seconds=1,
        game_time_scale=1,
        log_level="CRITICAL",
    )


def make_static_files(tmp_path: Path) -> None:
    """Create the minimal built frontend tree required by API tests."""
    static = tmp_path / "static"
    static.mkdir(parents=True)
    (static / "dist").mkdir()
    (static / "dist" / "index.html").write_text(
        "<html>world-map-shell</html>"
    )
    for filename in (
        "login.html",
        "leaderboard.html",
        "index.html",
        "contracts.html",
        "contract-detail.html",
        "fleet.html",
        "transports.html",
        "transport-detail.html",
    ):
        (static / filename).write_text(f"<html>{filename}</html>")
