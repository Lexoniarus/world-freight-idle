"""Shared game-state factories for tests."""

import time
from dataclasses import replace

from app.api.v1.game_projection import project_contract
from app.services.gameplay.game import GameService
from tests.support.api import FakeGame
from tests.support.catalogues import BERLIN_UID


def first_berlin_contract(synthetic_game: GameService) -> dict:
    """Return the first prepared Berlin offer projection."""
    return next(
        contract
        for contract in [
            project_contract(item)
            for item in synthetic_game.state_repository.list_offers()
        ]
        if contract["origin_hub_id"] == BERLIN_UID
    )


def other_facility_offer(synthetic_game: GameService):
    """Return an offer whose pickup differs from the starter facility."""
    vehicle = synthetic_game.get_vehicle("truck_01")
    return next(
        offer
        for offer in synthetic_game.list_contracts()
        if offer.origin.facility_uid != vehicle.facility_uid
    )


def create_active_trip(synthetic_game: GameService):
    """Persist one active trip through the player's unit of work."""
    now = time.time()
    trip = replace(
        FakeGame(synthetic_game).trip,
        departed_at=now,
        arrives_at=now + 20,
    )
    with synthetic_game.unit_of_work.transaction():
        vehicle = synthetic_game.get_vehicle(trip.vehicle_id)
        vehicle.start_trip()
        synthetic_game.state_repository.save_vehicle(vehicle)
        synthetic_game.state_repository.save_transport(trip)
    return trip
