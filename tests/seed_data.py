"""Small deterministic data set for the MVP contract generator."""

from __future__ import annotations

from app.domain.models import CargoType, Hub

HUBS: tuple[Hub, ...] = (
    Hub(
        id="berlin_westhafen",
        city="Berlin",
        label="Berlin Westhafen",
        address="Westhafenstraße 1, 13353 Berlin, Germany",
        country="DE",
    ),
    Hub(
        id="hamburg_cta",
        city="Hamburg",
        label="Container Terminal Altenwerder",
        address="Am Ballinkai 1, 21129 Hamburg, Germany",
        country="DE",
    ),
    Hub(
        id="duisburg_d3t",
        city="Duisburg",
        label="D3T Duisburg Trimodal Terminal",
        address="Rotterdamer Straße 30, 47229 Duisburg, Germany",
        country="DE",
    ),
    Hub(
        id="rotterdam_maasvlakte",
        city="Rotterdam",
        label="Maasvlakte logistics area",
        address="Europaweg 910, 3199 LC Maasvlakte Rotterdam, Netherlands",
        country="NL",
    ),
)

HUB_BY_ID = {hub.id: hub for hub in HUBS}

CARGO_TYPES: tuple[CargoType, ...] = (
    CargoType("Automotive-Komponenten", 8.0, 24.0, 0.21),
    CargoType("Maschinenbauteile", 8.0, 22.0, 0.19),
    CargoType("Elektronik", 4.0, 16.0, 0.25),
    CargoType("Verpackte Lebensmittel", 8.0, 24.0, 0.16),
    CargoType("Konsumgüter", 7.0, 23.0, 0.17),
)

FICTIONAL_SHIPPERS: tuple[str, ...] = (
    "Nordwerk Components GmbH",
    "Rheinland Industrial Supply GmbH",
    "Delta Trade Logistics B.V.",
    "Spree Technikhandel GmbH",
    "Hanse Cargo Systems GmbH",
)

FICTIONAL_CONSIGNEES: tuple[str, ...] = (
    "Westline Distribution GmbH",
    "Continental Assembly Services B.V.",
    "Metropol Warenlogistik GmbH",
    "EuroHub Fulfilment B.V.",
    "Central Parts Network GmbH",
)
