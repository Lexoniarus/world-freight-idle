"""Read-only retention and refresh behavior of one city market."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.errors import CatalogueError


def test_retention_filters_without_writing_during_market_reads(
    synthetic_game_context,
    synthetic_game,
):
    offers = synthetic_game.list_contracts()
    first = offers[0]
    legacy = replace(
        first, id="legacy", market_model="nhm_v1", market_context=None
    )
    expired = replace(
        first, id="expiring", expires_at=synthetic_game.now() + 30
    )
    synthetic_game.state_repository.replace_offers((*offers, legacy, expired))
    synthetic_game.player_market.routes.bind((*offers, legacy, expired))
    assert synthetic_game.list_contracts() == offers
    assert synthetic_game.contract_choices(offers)[0].eligible_vehicle_ids == (
        "truck_01",
    )
    vehicle = synthetic_game.get_vehicle("truck_01")
    vehicle._capacity_tons = 0.1
    synthetic_game.state_repository.save_vehicle(vehicle)
    assert synthetic_game.list_contracts() == []
    with patch.object(
        synthetic_game_context.catalogue,
        "list_models",
        side_effect=CatalogueError("offline"),
    ):
        with pytest.raises(CatalogueError):
            synthetic_game.list_contracts()
    assert synthetic_game.state_repository.list_offers() == (
        *offers,
        legacy,
        expired,
    )


def test_market_reads_and_refresh_never_call_providers_or_generate(
    synthetic_game,
):
    readiness = synthetic_game.player_market.routes.readiness
    with patch.object(
        readiness,
        "load",
        side_effect=AssertionError,
    ):
        retained = synthetic_game.list_contracts()
        assert synthetic_game.list_contracts() == retained
        regenerated = synthetic_game.refresh_contracts()
        assert regenerated == retained
        assert {o.origin.city.city_uid for o in regenerated} == {
            synthetic_game.get_vehicle("truck_01").location.city.city_uid
        }
