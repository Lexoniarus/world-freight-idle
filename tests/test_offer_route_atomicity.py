"""Atomic offer-route reference replacement and rollback."""

from dataclasses import replace

import pytest

from app.domain.errors import PersistenceError
from tests.support.market import build_prepared_game, require_value


@pytest.mark.asyncio
async def test_reference_replacement_owns_rollback(
    synthetic_game_context,
    database,
):
    prepared_context, preparation = build_prepared_game(
        synthetic_game_context, database
    )
    synthetic_game = prepared_context.service
    offer = synthetic_game.state_repository.list_offers()[0]
    pair = offer.origin.facility_uid, offer.destination.facility_uid
    await preparation.route_preparation.preparation.prepare(*pair)
    preparation.routes.bind((offer,))
    reference = require_value(preparation.routes.references.get(offer.id))
    invalid = replace(offer, id="missing-offer")
    with pytest.raises(PersistenceError):
        preparation.routes.bind((offer, invalid))
    assert preparation.routes.references.get(offer.id) == reference
    with pytest.raises(PersistenceError):
        preparation.routes.references.replace((("missing-offer", reference),))
    assert preparation.routes.references.get(offer.id) == reference
    before = synthetic_game.state_repository.list_offers()
    with pytest.raises(PersistenceError), database.transaction():
        synthetic_game.state_repository.remove_offer(offer.id)
        preparation.routes.bind((invalid,))
    assert synthetic_game.state_repository.list_offers() == before
    assert preparation.routes.references.get(offer.id) == reference
