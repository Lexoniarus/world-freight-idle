"""Stock target selection, fairness and fleet-demand planning."""

from dataclasses import replace
from unittest.mock import patch

import pytest

from app.domain.contracts import ContractOffer
from app.domain.errors import PersistenceError
from app.domain.market_stock import PreparedTemplate, StockPolicy
from app.domain.results import AvailableContract
from app.repositories.market_stock import SqlitePlayerMarketStockStore
from app.services.market_selection import MarketSelectionService


def test_structural_candidates_are_reused_until_fleet_context_changes(
    stock_game,
):
    """Reuse expensive trade projections without freezing changed demand."""
    game, _, batch = stock_game
    candidates = game.market.candidates
    snapshot = batch.snapshots.read()
    cities = tuple(sorted({d.vehicle.city_uid for d in snapshot.demands}))
    fleet = tuple(d.vehicle for d in snapshot.demands)
    first = candidates.build(cities, fleet)
    assert candidates.build(cities, fleet) is first
    changed = replace(fleet[0], capacity_tons=fleet[0].capacity_tons + 1)
    rebuilt = candidates.build(cities, (changed, *fleet[1:]))
    assert rebuilt is not first


def test_stock_policy_selection_and_corrupt_storage_are_rejected(
    stock_game, database
):
    game, prep, batch = stock_game
    for policy in ((0, 10), (4, 3)):
        with pytest.raises(ValueError):
            StockPolicy(*policy)
    for invalid in (True, 3.5, float("inf")):
        with pytest.raises(ValueError):
            replace(StockPolicy(), reserve_per_band=invalid)
    snapshot = batch.snapshots.read()
    offer = ContractOffer.from_snapshot(
        game.market.factory.build(snapshot.candidates[0], 1)
    )
    template = PreparedTemplate(
        "template", "model", offer.origin.city.city_uid, offer
    )
    for invalid in (
        replace(offer, expires_at=2),
        replace(offer, market_model="old", market_context=None),
    ):
        with pytest.raises(ValueError):
            PreparedTemplate(
                "bad", "model", offer.origin.city.city_uid, invalid
            )
    with pytest.raises(ValueError):
        PreparedTemplate("bad", "model", "wrong", offer)
    prep.stock.templates.add(template)
    with pytest.raises(PersistenceError):
        prep.stock.templates.add(template)
    SqlitePlayerMarketStockStore.initialize(database)
    assert prep.stock.templates.templates((template.city_uid,)) == (template,)
    assert prep.stock.templates.scoped_templates(
        ((template.city_uid, template.model_id),)
    ) == (template,)
    assert prep.stock.templates.scoped_templates(()) == ()
    assert (
        prep.stock.templates.scoped_templates(((template.city_uid, "other"),))
        == ()
    )
    assert prep.stock.templates.templates(()) == ()
    assert prep.stock.stock.cursor() == ""
    assert prep.stock.stock.pending("context") is None
    prep.stock.stock.checkpoint("context", ("a", "b", 1))
    assert prep.stock.stock.cursor() == "context"
    assert prep.stock.stock.pending("context") == ("a", "b", 1)
    prep.stock.stock.checkpoint("context", None)
    assert prep.stock.stock.pending("context") is None
    prep.stock.stock.consume("unbound-legacy", 1)
    selected = MarketSelectionService(StockPolicy()).select(
        tuple(
            AvailableContract(replace(offer, id=str(i)), ("truck", "other"))
            for i in range(12)
        ),
        "truck",
    )
    assert len(selected) == 3
    assert all(o.eligible_vehicle_ids == ("truck",) for o in selected)
    assert (
        MarketSelectionService(StockPolicy()).select(
            (
                AvailableContract(
                    replace(offer, market_model="legacy", market_context=None),
                    ("truck",),
                ),
            ),
            None,
        )
        == ()
    )
    with database.connect() as db:
        db.execute("UPDATE market_templates SET model_id=''")
    with pytest.raises(PersistenceError):
        prep.stock.templates.templates((template.city_uid,))
    with pytest.raises(PersistenceError):
        prep.stock.templates.scoped_templates(((template.city_uid, ""),))


def test_complete_stock_target_does_not_materialize_another_offer(stock_game):
    """Keep a satisfied band from creating redundant templates."""
    _, _, batch = stock_game
    snapshot = batch.snapshots.read()
    target = batch.planning.targets(
        snapshot.demands,
        snapshot.candidates,
        snapshot.ready,
        snapshot.usable_offers,
    )[0]
    limit = (
        batch.templates.policy.visible_per_band
        if target.priority < 2
        else batch.templates.policy.reserve_per_band
    )
    assert batch.templates.materialize(
        (),
        frozenset(),
        {},
        replace(target, count=limit),
        target.choices[0],
    ) == ((), ())


def test_stock_rotation_prioritizes_unserved_vehicles_and_resumes_work(
    stock_game,
):
    from app.domain.market_stock import MarketDemand
    from app.services.market.stock.planning import StockTarget
    from app.services.vehicle_coverage import trade_key

    game, prep, batch = stock_game
    snapshot = batch.snapshots.read()
    candidate = snapshot.candidates[0]
    demand = snapshot.demands[0]
    supplied = StockTarget(demand, "short", 1, 0, (candidate,), 7)
    missing = replace(
        supplied,
        demand=MarketDemand(replace(demand.vehicle, vehicle_id="z-truck"), 0),
        count=0,
        total_available=0,
    )
    assert batch.planning.order((supplied, missing), "")[0] == missing
    other = replace(missing, band="long")
    first, second = batch.planning.order((missing, other), "")
    assert batch.planning.order((missing, other), first.key)[0] == second
    assert batch.planning.choose(first, trade_key(candidate), ()) == candidate
    assert batch.planning.targets((), (), (), ()) == ()


def test_demand_models_and_owned_capacity_remain_separate(stock_game):
    from app.domain.market_compatibility import planning_vehicle

    game, prep, batch = stock_game
    vehicle = game.get_vehicle("truck")
    catalogue = game.market.candidates.catalogue
    model = catalogue.list_models()[0]
    with pytest.raises(ValueError, match="Fahrzeugmodell"):
        planning_vehicle(
            vehicle, replace(model, id="different"), vehicle.location
        )
    models = (
        model,
        replace(model, id="second-model", capacity_tons=1),
        replace(model, id="train", mode="rail"),
    )
    with patch.object(catalogue, "list_models", return_value=models):
        demands = batch.snapshots.demand.resolve((vehicle,), (), 1)
    assert {d.vehicle.model_id for d in demands} == {model.id}
    assert demands[0].vehicle.capacity_tons == vehicle.capacity_tons
