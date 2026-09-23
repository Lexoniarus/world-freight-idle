"""Generate NHM contracts only for explicitly requested origins."""

import random
from dataclasses import dataclass
from typing import ClassVar

from app.domain.contracts import ContractOffer
from app.domain.ports import VehicleCatalogue, WorldCatalogue
from app.domain.world import Facility
from app.services.contract_factory import ContractFactory
from app.services.trade_network import TradeNetwork, TradeOption
from app.simulation import build_payload_bands


@dataclass(slots=True)
class MarketGenerator:
    """Orchestrate contract coverage from cached NHM trade options."""

    model_id: ClassVar[str] = ContractFactory.model_id
    cargo_system: ClassVar[str] = ContractFactory.cargo_system

    world: WorldCatalogue
    rng: random.Random
    vehicles: VehicleCatalogue
    trade_network: TradeNetwork | None = None
    contract_factory: ContractFactory | None = None

    def generate(
        self,
        now: float,
        origin_facility_uids: list[str],
        contract_count: int = 6,
        existing_contracts: list[ContractOffer] | None = None,
        owned_capacities: list[float] | None = None,
    ) -> list[ContractOffer]:
        """Guarantee payload-band work only for requested valid origins."""
        snapshot = self.world.read()
        candidates = tuple(
            facility
            for facility in snapshot.facilities
            if facility.is_routable()
        )
        candidate_uids = tuple(
            facility.facility_uid for facility in candidates
        )
        if (
            self.trade_network is None
            or self.trade_network.facility_uids != candidate_uids
        ):
            self.trade_network = TradeNetwork(candidates)
        if self.contract_factory is None:
            self.contract_factory = ContractFactory(self.rng)

        retained = list(existing_contracts or [])
        bands = build_payload_bands(
            [model.capacity_tons for model in self.vehicles.list_models()]
            + list(owned_capacities or [])
        )
        band_by_name = {band.name: band for band in bands}
        covered = {
            (item.origin.facility_uid, item.payload_band)
            for item in retained
            if item.payload_band in band_by_name
            and 0 < item.tons <= band_by_name[item.payload_band].maximum_tons
        }

        available = {
            facility.facility_uid: facility for facility in candidates
        }
        origins: list[Facility] = []
        planned: set[str] = set()
        for identifier in origin_facility_uids:
            try:
                facility = snapshot.get_facility(identifier)
            except KeyError:
                continue
            if (
                facility.facility_uid in available
                and facility.facility_uid not in planned
            ):
                origins.append(facility)
                planned.add(facility.facility_uid)

        if not origins:
            return retained

        contracts = list(retained)
        assert self.trade_network is not None
        assert self.contract_factory is not None
        for origin in origins:
            for band in bands:
                coverage_key = (origin.facility_uid, band.name)
                if coverage_key in covered:
                    continue
                option = self._select_trade_option(
                    self.trade_network.options_for(origin.facility_uid)
                )
                contracts.append(
                    ContractOffer.from_snapshot(
                        self.contract_factory.build(option, now, band)
                    )
                )
                covered.add(coverage_key)

        scoped_count = sum(
            item.origin.facility_uid in planned for item in contracts
        )
        while scoped_count < contract_count:
            origin = self.rng.choice(origins)
            option = self._select_trade_option(
                self.trade_network.options_for(origin.facility_uid)
            )
            contracts.append(
                ContractOffer.from_snapshot(
                    self.contract_factory.build(
                        option, now, self.rng.choice(bands)
                    )
                )
            )
            scoped_count += 1
        return contracts

    def _select_trade_option(
        self,
        options: tuple[TradeOption, ...],
    ) -> TradeOption:
        """Prefer sourced, confident and exact NHM relations."""
        weights = []
        for option in options:
            origin_source = (
                1.45 if option.origin_cargo.evidence_type != "derived" else 1.0
            )
            destination_source = (
                1.25
                if option.destination_cargo.evidence_type != "derived"
                else 1.0
            )
            exact = 1.25 if option.match_type == "exact" else 1.0
            confidence = (
                0.5
                + option.origin_cargo.confidence
                + option.destination_cargo.confidence
            )
            priority = (
                0.5
                + option.origin_cargo.priority_score
                + option.destination_cargo.priority_score
            )
            weights.append(
                origin_source
                * destination_source
                * exact
                * confidence
                * priority
            )
        return self.rng.choices(options, weights=weights, k=1)[0]
