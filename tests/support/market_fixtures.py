"""Reusable market fixtures composed outside executable test modules."""

import random
import time
from dataclasses import replace
from unittest.mock import Mock
from uuid import UUID

import pytest

from app.bootstrap import build_market_components
from app.domain.cargo import FacilityNhmProfile, NhmProduct
from app.domain.game import PlayerState
from app.domain.geography import Coordinates
from app.domain.market_profiles import (
    VEHICLE_SCALES,
    DistanceLoadProfile,
    NhmMarketProfile,
    VehicleScaleProfile,
)
from app.domain.world_scopes import WorldScope
from app.services.gameplay.fleet import build_owned_vehicle
from tests.support.game_service import build_fixture_game
from tests.support.market import build_prepared_game


def _build_city_market(
    synthetic_world_catalogue,
    synthetic_vehicle_catalogue,
    cargo_count: int,
):
    """Build one compact market with an explicit cargo variety."""
    snapshot = synthetic_world_catalogue.read()
    base = WorldScope(snapshot).facility("berlin_westhafen")
    products = tuple(
        NhmProduct(
            index,
            f"730{index}",
            f"Structural modules {index}",
            (index,),
        )
        for index in range(1, cargo_count + 1)
    )
    outputs = tuple(
        FacilityNhmProfile(
            product,
            "output",
            "derived",
            0.8,
            0.7,
            None,
        )
        for product in products
    )
    inputs = tuple(replace(output, role="input") for output in outputs)
    origin = replace(base, facility_uid="origin-a", nhm_profiles=outputs)
    other = replace(origin, facility_uid="origin-b")
    destinations = tuple(
        replace(
            base,
            facility_uid="destination-" + str(index),
            address=replace(
                base.address,
                city=replace(
                    base.address.city,
                    city_uid=str(UUID(int=index + 1)),
                ),
            ),
            coordinates=point,
            nhm_profiles=inputs,
        )
        for index, point in enumerate(
            (
                Coordinates(52.5, 13.4),
                Coordinates(50, 13),
                Coordinates(40, 2),
            )
        )
    )
    inactive = replace(
        origin,
        facility_uid="inbound-only",
        nhm_profiles=inputs,
    )
    profiles = tuple(
        NhmMarketProfile(
            product.nhm_row_id,
            "general",
            499 + product.nhm_row_id,
            1.4,
            tuple(
                DistanceLoadProfile(band, 1, 0.5, 0.8)
                for band in ("short", "medium", "long")
            ),
            tuple(VehicleScaleProfile(scale, 1) for scale in VEHICLE_SCALES),
        )
        for product in products
    )
    world = Mock(
        read=Mock(
            return_value=replace(
                snapshot,
                facilities=(origin, other, inactive, *destinations),
                market_profiles=profiles,
            )
        )
    )
    model = next(
        item
        for item in synthetic_vehicle_catalogue.list_models()
        if item.id == "iveco_sway_500"
    )
    models = Mock(list_models=Mock(return_value=(model,)))
    owned = build_owned_vehicle(model, "truck", origin.location_snapshot())
    market = build_market_components(world, random.Random(3), models)
    fleet = market.candidates.resolve_fleet((owned,))
    return market, owned, fleet, world, model


@pytest.fixture
def city_market(synthetic_world_catalogue, synthetic_vehicle_catalogue):
    """Build a compact three-band city market for behavior tests."""
    return _build_city_market(
        synthetic_world_catalogue,
        synthetic_vehicle_catalogue,
        1,
    )


@pytest.fixture
def diverse_city_market(
    synthetic_world_catalogue,
    synthetic_vehicle_catalogue,
):
    """Build a compact market with three compatible cargo categories."""
    return _build_city_market(
        synthetic_world_catalogue,
        synthetic_vehicle_catalogue,
        3,
    )


@pytest.fixture
def vehicle_game(city_market, database, synthetic_vehicle_catalogue):
    """Compose a compact city game with real preparation collaborators."""
    market, owned, _, world, _ = city_market
    context = build_fixture_game(
        database,
        "test-owner",
        world,
        synthetic_vehicle_catalogue,
        market,
        time.time,
    )
    with database.transaction(), database.connect() as connection:
        connection.execute("DELETE FROM contract_offers")
        connection.execute("DELETE FROM owned_vehicles")
        context.service.state_repository.save_player(PlayerState(175000, 0, 0))
        context.service.state_repository.save_vehicle(owned)
    return build_prepared_game(context, database)


@pytest.fixture
def diverse_vehicle_game(
    diverse_city_market,
    database,
    synthetic_vehicle_catalogue,
):
    """Compose the diverse city market with production collaborators."""
    market, owned, _, world, _ = diverse_city_market
    context = build_fixture_game(
        database,
        "test-owner",
        world,
        synthetic_vehicle_catalogue,
        market,
        time.time,
    )
    with database.transaction(), database.connect() as connection:
        connection.execute("DELETE FROM contract_offers")
        connection.execute("DELETE FROM owned_vehicles")
        context.service.state_repository.save_player(PlayerState(175000, 0, 0))
        context.service.state_repository.save_vehicle(owned)
    return build_prepared_game(context, database)
