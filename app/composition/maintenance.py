"""Offline repair, migration and upgrade dependency assembly."""

from pathlib import Path

from app.composition.runtime import (
    build_vehicle_catalogue,
    build_world_catalogue,
)
from app.config import Settings
from app.domain.game_import import GameStateImporter
from app.domain.geography_migration import GeographyMigrationStore
from app.domain.market_stock import StockPolicy
from app.domain.world_scopes import WorldScope
from app.repositories.accounts import AccountRepository
from app.repositories.energy_upgrade import VehicleEnergyUpgradeRepository
from app.repositories.game_database import SqliteGameDatabase
from app.repositories.game_state import SqliteGameUnitOfWork
from app.repositories.legacy_game_import import LegacyGameImporter
from app.repositories.market_stock_repair import (
    SqliteMarketStockRepairExecutor,
    SqliteMarketStockRepairReader,
)
from app.repositories.market_stock_upgrade import MarketStockUpgradeRepository
from app.repositories.transport_repair import TransportRepairRepository
from app.repositories.world_geography import WorldGeographyRepository
from app.services.market.contract_factory import ContractFactory
from app.services.market.selection import MarketSelectionService
from app.services.market.stock.maintenance import (
    MarketStockRepairPlanner,
    MarketStockRepairService,
)
from app.services.profile_maintenance import ProfileMaintenanceService


def build_transport_repair(source: Path) -> TransportRepairRepository:
    """Wire explicit offline repair without opening the active game file."""
    return TransportRepairRepository(source)


def build_market_stock_upgrade(
    source: Path, now: float
) -> MarketStockUpgradeRepository:
    """Wire explicit offline schema adoption without opening active storage."""
    return MarketStockUpgradeRepository(source, now)


def build_market_stock_repair(source: Path) -> MarketStockRepairService:
    """Wire read-only historical stock inspection outside the runtime."""
    policy = StockPolicy()
    return MarketStockRepairService(
        SqliteMarketStockRepairReader(source),
        SqliteMarketStockRepairExecutor(source),
        MarketStockRepairPlanner(
            policy,
            MarketSelectionService(policy),
        ),
    )


def build_profile_maintenance_service(
    settings: Settings,
) -> ProfileMaintenanceService:
    """Wire local maintenance independently of the HTTP application."""
    database = SqliteGameDatabase(settings.db_path)
    database.initialize()
    AccountRepository.initialize(database)
    accounts = AccountRepository(database)

    def player_unit_of_work_factory(user_id: str) -> SqliteGameUnitOfWork:
        """Bind the repository-verified account to its relational state."""
        return SqliteGameUnitOfWork(database, user_id)

    return ProfileMaintenanceService(
        build_vehicle_catalogue(settings),
        accounts,
        player_unit_of_work_factory,
    )


def build_geography_migration(
    backup: Path, target: Path
) -> GeographyMigrationStore:
    """Bind offline normalization to its immutable backup and new output."""
    return WorldGeographyRepository(backup, target)


def build_game_importer(
    source: Path, settings: Settings, exclude_global_demo: bool = False
) -> GameStateImporter:
    """Assemble the explicit offline importer without opening runtime state."""
    return LegacyGameImporter(
        source,
        WorldScope(build_world_catalogue(settings).read()),
        ContractFactory.model_id,
        build_vehicle_catalogue(settings).list_models(),
        exclude_global_demo=exclude_global_demo,
    )


def build_energy_upgrade(
    source: Path, settings: Settings
) -> VehicleEnergyUpgradeRepository:
    """Inject catalogue snapshots into the explicit offline state upgrade."""
    return VehicleEnergyUpgradeRepository(
        source, build_vehicle_catalogue(settings).list_models()
    )
