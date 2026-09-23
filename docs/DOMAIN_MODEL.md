# Domänenmodell

Stand: 21.09.2026.

Dieses Dokument beschreibt das fachliche Zielmodell von World Freight Idle.
Es ist die verbindliche Begriffs- und Objektgrenze für neue Core-Entwicklung.
Bestehende JSON-/KV-Strukturen werden schrittweise migriert; dieses Dokument
behauptet nicht, dass alle Zielobjekte bereits implementiert sind.

## Grundsätze

- Domainobjekte bilden fachliche Konzepte ab, keine Tabellen oder API-JSON.
- Entities besitzen eine stabile Identität und einen eigenen Lebenszyklus.
- Value Objects besitzen keine eigene Identität und schützen ihre Invarianten.
- Beziehungen werden bevorzugt durch Komposition modelliert.
- Vererbung wird nur bei einem echten `is-a`-Verhältnis mit gemeinsamem
  Verhalten eingesetzt.
- Persistenz- und API-Snapshots sind eigene immutable Projektionen.
- Services orchestrieren Use Cases; fachliche Invarianten gehören in die
  zuständigen Domainobjekte.
- SQL, KV-Schlüssel und konkrete Repositoryklassen sind keine Domainkonzepte.

## Referenzwelt

Die reale Referenzwelt ist immutable und unabhängig vom Spielerzustand.

```text
WorldSnapshot
├── Country
├── City
├── Company
├── Facility
├── NhmProduct
└── FacilityNhmProfile
```

### Country

Entity/Referenzobjekt für ein Land.

Zielattribute:

- `code`
- `name`
- optional `iso3`

Ein Land enthält keine Spielerlogik. Länderregeln wie Maut, Währung oder
Grenzlogik können später über separate Regelobjekte angebunden werden.

### City

Entity/Referenzobjekt für eine Stadt.

Zielattribute:

- `city_uid`
- `name`
- `country`
- optional administrative Region
- optional Referenzkoordinaten

Eine Stadt gehört genau zu einem Land. Companies gehören nicht exklusiv zu
einer Stadt; sie werden über ihre Facilities einer oder mehreren Städten
zugeordnet.

### Company

Immutable Referenzunternehmen, niemals Spielerunternehmen.

Aktuell existiert `Company` bereits mit stabiler `company_uid`, Namen,
Land, Website und Quellen.

Die Company besitzt Facilities. Für Runtime-Snapshots wird nicht das komplette
Company-Objekt eingebettet, sondern `CompanyIdentity`.

### Facility

Öffentlicher realer Frachtstandort mit stabiler `facility_uid`.

Zielbeziehungen:

```text
Facility
├── company: Company | None
├── address: Address
├── coordinates: Coordinates
├── nhm_profiles: FacilityNhmProfile[]
├── documented_goods: DocumentedGood[]
└── evidence: SourceReference[]
```

Eine Facility ist kein Depot und kein Spielerbesitz.

### NhmProduct

Immutable Referenzobjekt für einen Eintrag aus der NHM-Systematik.

Zielattribute:

- `nhm_row_id`
- `code`
- `name`
- Hierarchiebeziehung

`NhmProduct` beschreibt die Warenidentität selbst. Es enthält keine
Facility-spezifische Rolle, Confidence oder Priorität.

### FacilityNhmProfile

Beziehung zwischen einer Facility und einem `NhmProduct`.

Zielattribute:

- `product`
- `role`
- `evidence_type`
- `confidence`
- `priority_score`
- optionale Quelle

Damit werden NHM-Produktidentität und standortspezifische operative Fähigkeit
als zwei getrennte Konzepte modelliert.

### DocumentedGood

Konkreter belegter Warenhinweis aus einer Quelle.

`DocumentedGood` bleibt bewusst getrennt von `FacilityNhmProfile`:
belegte Realität und abgeleitete Simulationsfähigkeit dürfen nicht
stillschweigend vermischt werden.

Eine Facility kann daher beispielsweise gleichzeitig besitzen:

```python
facility.documented_goods
facility.nhm_profiles
```

`documented_goods` bezeichnet recherchierte reale Warenhinweise.
`nhm_profiles` beschreibt das operative NHM-Verhalten der Facility.

## Value Objects

### Coordinates

Immutable WGS84-Koordinaten.

```text
Coordinates
├── latitude
└── longitude
```

Das Objekt validiert selbst endliche Werte und gültige Wertebereiche.

### Address

Strukturierte Adresse.

```text
Address
├── street
├── house_number
├── postal_code
└── city: City
```

Das Land ergibt sich über `Address.city.country`. Convenience-Zugriffe dürfen
diese Beziehung delegieren, aber keine widersprüchliche Kopie erzeugen.

### CompanyIdentity

Kompakte Firmenidentität für Runtime-Projektionen:

- `company_uid`
- `legal_name`
- `display_name`
- `country`

Quellen, Website und weitere Referenzdetails gehören nicht in diesen Snapshot.

### FacilityLocationSnapshot

Immutable Standortprojektion für Contracts, Vehicles, Map und Transporte.

Sie enthält ausschließlich die für Identität, Anzeige und Routing nötigen
Daten, insbesondere:

- `facility_uid`
- `company: CompanyIdentity | None`
- `address`
- `coordinates`
- `facility_type`
- Koordinatenstatus/-evidence
- Katalog-/Snapshotversion

Vollständige NHM-Profile, documented goods und Company-Quellen werden nicht
eingebettet.

### RouteResult und PriceQuote

`RouteResult` und `PriceQuote` bleiben Value Objects.

Routing beschreibt eine Providerroute. `PriceQuote` beschreibt eine
serverseitige Kalkulation; beide besitzen keine eigene fachliche Identität.

## Spiel-Domain

```text
PlayerState
├── OwnedVehicle[]
├── ContractOffer[]
└── ActiveTransport[]
```

### PlayerState

Zielobjekt für:

- Guthaben
- abgeschlossene Lieferungen
- Reputation

Später kann daraus ein eigenständiges `PlayerCompany`-Aggregat entstehen.

### OwnedVehicle

Spiel-Entity mit stabiler Fahrzeug-ID.

```text
OwnedVehicle
├── vehicle_id
├── model_id
├── gameplay snapshot values
├── location: FacilityLocationSnapshot
└── status
```

Ein `OwnedVehicle` ist kein `VehicleModel`. Es referenziert beziehungsweise
snapshottet freigegebene Modellwerte.

### VehicleModel

Immutable Referenz-/Katalogobjekt für ein kaufbares Fahrzeugmodell.

Es besitzt keine Spieleridentität und keinen Standort.

### ContractOffer

Spiel-Entity für ein noch verfügbares Frachtangebot.

Zielbeziehungen:

```text
ContractOffer
├── contract_id
├── origin: FacilityLocationSnapshot
├── destination: FacilityLocationSnapshot
├── product: NhmProduct
├── NHM evidence
├── quantity
├── commercial terms
├── created_at
└── expires_at
```

`ContractOffer` ersetzt langfristig das veraltete Minimalmodell `Contract`
aus `app/domain/models.py` und die heutigen untypisierten Contract-Dicts.

### ActiveTransport

Spiel-Entity, die aus einem angenommenen ContractOffer entsteht.

```text
ActiveTransport
├── transport_id
├── vehicle_id
├── contract snapshot
├── route snapshot
├── cost/payout snapshot
├── departed_at
└── arrives_at
```

Ein `ActiveTransport` erbt nicht von `ContractOffer`; er enthält dessen
historischen Snapshot.

## Query- und Navigationsmodell

Der normalisierte Objektgraph wird durch navigierbare Scope-Objekte ergänzt.

Zielbeispiele:

```python
world.country("DE")
world.country("DE").city("Berlin")
world.country("DE").city("Berlin").company("BEHALA")
world.country("DE").city("Berlin").company("BEHALA").facilities
```

Gemeinsame Scope-Abfragen:

```text
WorldScope
├── CountryScope
├── CityScope
└── CompanyScope
```

Scopes dürfen gemeinsames Query-Verhalten kapseln, beispielsweise:

- `facilities`
- `companies`
- `documented_goods`
- `nhm_products`

Die Scopes verändern die normalisierten Beziehungen nicht. Eine Company wird
nicht fachlich Kind einer City; der Scope filtert lediglich ihre Facilities.

## Vererbung und Komposition

Bevorzugte Komposition:

```text
Company ──owns/reference──► Facility
Facility ────────────────► Address
Address ─────────────────► City
City ────────────────────► Country
Facility ────────────────► FacilityNhmProfile
FacilityNhmProfile ──────► NhmProduct
OwnedVehicle ────────────► FacilityLocationSnapshot
ActiveTransport ─────────► Contract snapshot
```

Vererbung ist nur vorgesehen, wenn mehrere Typen wirklich dasselbe Basiskonzept
mit gemeinsamem Verhalten darstellen. Query-Scopes sind ein möglicher
Anwendungsfall. Reine Datenähnlichkeit reicht nicht als Begründung.

## Persistenzgrenze

Zielrichtung:

```text
GameService
    │
    ▼
GameStateRepository
    │
    ▼
SqliteGameStateRepository
    │
    ▼
SqliteStore
```

Services sollen langfristig weder konkrete SQLite-Klassen noch KV-Schlüssel
wie `player`, `vehicles`, `contracts` oder `active_trips` kennen.

Repositories serialisieren Domainobjekte und Snapshots. Domainobjekte kennen
keine SQL- oder JSON-Persistenzdetails.

## Aktueller Migrationsstand

Bereits als echte immutable Domainobjekte vorhanden:

- `Company`
- `Facility`
- `CargoProfile`
- `DocumentedGood`
- `SourceReference`
- `WorldSnapshot`
- `FacilityQuery`
- `RouteResult`
- `PriceQuote`
- `VehicleImage`
- `VehicleModel`

`CargoProfile` ist dabei ein Übergangsmodell. Es wird schrittweise in
`NhmProduct` und `FacilityNhmProfile` aufgeteilt.

Bereits typisierte Runtime-Snapshots:

- `CompanyIdentity`
- `FacilityLocationSnapshot`
- `ContractOfferSnapshot`

`Facility.location_snapshot()` und `ContractFactory.build()` liefern damit
immutable Objekte. An den bestehenden API-/Persistenzgrenzen wird weiterhin
explizit in das kompatible JSON-Format serialisiert.

Bereits als Runtime-Spielentities umgesetzt:

- `PlayerState`
- `OwnedVehicle`
- `ContractOffer`

Ihre Persistenz- und API-Projektionen bleiben in dieser Stufe
JSON-kompatibel; die Repository- und explizite API-DTO-Grenze folgen später.

Noch überwiegend dynamisches JSON/dict:

- Active Transports

Legacy-/Übergangskonzepte:

- `Hub`
- `CargoType`
- das alte Minimalmodell `Contract`
- `CargoProfile`

Diese werden erst entfernt, wenn alle produktiven Referenzen migriert und die
Quality Gates grün sind.

## Migrationsreihenfolge

1. Ziel-Domainmodell und ADR verbindlich dokumentieren.
2. Runtime-Snapshots typisieren: `CompanyIdentity`,
   `FacilityLocationSnapshot` und `ContractOfferSnapshot`.
3. `PlayerState`, `OwnedVehicle`, `ContractOffer` und `ActiveTransport`
   als echte Spiel-Domainobjekte einführen.
4. `GameStateRepository` als Port einziehen und konkrete SQLite-Persistenz
   aus Services entfernen.
5. Referenzwelt normalisieren und navigierbar machen: `Country`, `City`,
   `Address`, `Coordinates`, `NhmProduct`, `FacilityNhmProfile` sowie
   World-/Country-/City-/Company-Scopes.
6. `Hub`, altes `Contract`, `CargoProfile` und nicht mehr benötigte
   Legacy-Modelle entfernen.
7. Architekturtests verschärfen und Architektur-/API-Dokumentation auf die
   endgültige Ist-Struktur konsolidieren.

Jeder Schritt hält das bestehende Verhalten kompatibel, erhält vollständige
Tests und aktualisiert das Function-Test-Manifest für neue konkrete Core-
Callables.
