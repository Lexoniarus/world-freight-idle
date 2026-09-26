from typing import cast

import pytest
from fastapi import HTTPException

from app.api.v1.contracts import accept_contract, quote_contract
from app.api.v1.schemas import DispatchRequest, QuoteRequest
from app.domain.errors import RoutingError
from app.services.game import GameService


class FailingRoutingGame:
    async def quote_contract(self, contract_id: str, vehicle_id: str):
        error = RoutingError("private Valhalla HTTP detail")
        error.category = "endpoint_unreachable"
        error.provider_code = 171
        error.provider_message = "No suitable edges near location"
        error.retryable = False
        raise error

    async def dispatch(self, contract_id: str, vehicle_id: str):
        error = RoutingError("private Valhalla HTTP detail")
        error.category = "no_path"
        error.provider_code = 442
        error.provider_message = "No path could be found for input"
        error.retryable = False
        raise error


@pytest.mark.asyncio
async def test_contract_api_hides_routing_provider_details():
    game = cast(GameService, FailingRoutingGame())

    with pytest.raises(HTTPException) as quote_failure:
        await quote_contract(
            "contract-1",
            QuoteRequest(vehicle_id="truck-1"),
            game,
        )
    with pytest.raises(HTTPException) as dispatch_failure:
        await accept_contract(
            "contract-1",
            DispatchRequest(vehicle_id="truck-1"),
            game,
        )

    for failure in (quote_failure.value, dispatch_failure.value):
        assert failure.status_code == 502
        assert failure.detail == "Straßenroute konnte nicht berechnet werden."
        assert "Valhalla" not in str(failure.detail)
        assert "No path" not in str(failure.detail)
