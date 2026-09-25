"""Typed use-case results, independent of HTTP and persistence formats."""

from dataclasses import dataclass

from app.domain.contracts import ContractOffer
from app.domain.game import OwnedVehicle, PlayerState
from app.domain.journeys import JourneyPlan
from app.domain.pricing import PriceQuote
from app.domain.routes import DispatchRoutePlan
from app.domain.transports import ActiveTransport, RouteSnapshot
from app.domain.vehicles import VehicleModel
from app.domain.world import FacilityLocationSnapshot


@dataclass(frozen=True, slots=True)
class ContractQuote:
    """The selected offer, routed measurements and calculated economics."""

    contract: ContractOffer
    route: RouteSnapshot
    economics: PriceQuote
    vehicle_id: str
    maintenance_eur_per_km: float
    journey: JourneyPlan | None = None
    dispatch_route: DispatchRoutePlan | None = None


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    """A consistent read of player-owned entities at the service boundary."""

    server_time: float
    time_scale: float
    player: PlayerState
    vehicles: tuple[OwnedVehicle, ...]
    transports: tuple[ActiveTransport, ...]
    contracts: tuple[ContractOffer, ...] = ()


@dataclass(frozen=True, slots=True)
class FleetCatalogue:
    """Read-only purchase choices and their delivery location."""

    models: tuple[VehicleModel, ...]
    delivery_location: FacilityLocationSnapshot


@dataclass(frozen=True, slots=True)
class FacilityPage:
    """Filtered public facilities with catalogue availability metadata."""

    facilities: tuple[FacilityLocationSnapshot, ...]
    catalogue_version: str
    unavailable_count: int


@dataclass(frozen=True, slots=True)
class AvailableContract:
    """One offer with transient, server-calculated vehicle choices."""

    offer: ContractOffer
    eligible_vehicle_ids: tuple[str, ...]
