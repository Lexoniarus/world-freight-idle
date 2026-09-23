# WorldCatalogue: Referenzen und Spielzustand

Stand: 23.09.2026. UI First, FastAPI, native ES-Module, OSM und
`python main.py` bleiben Grundlage. Reale Referenzunternehmen sind keine
Spielerunternehmen; öffentliche Facilities sind keine eigenen Depots.

## Referenzdaten

`data/world_freight_company_facility_mvp.sqlite3` wird mit Schema **4.0.0**
versioniert ausgeliefert: 109 Companies, 352 Facilities, 25 Länder und
304 dauerhaft identifizierte Städte. Der Reader prüft Schema, Referenzen und
Provenienz einschließlich NHM-Tabellen.

`WORLD_CATALOGUE_PATH` kann die Datei ersetzen. Laufzeitverbindungen verwenden
`mode=ro`, `query_only`, Fremdschlüsselprüfung und eine konsistente
Lesetransaktion. Es gibt keinen Seed-Fallback.

Der aktuelle Stand enthält 352 Facilities. Alle 352 besitzen gespeicherte
Koordinaten und Geocoding-Evidence und sind für die Spielsimulation routbar.
79 Standorte tragen `verified_coordinates`; 273 tragen ausdrücklich
`estimated_for_simulation`. Geschätzte Positionen bleiben in API-Snapshots als
solche erkennbar und werden nicht als verifiziert ausgegeben. Für ältere
Simulationseinträge ist `internal://simulation-*` eine zulässige Provenienz;
`verified_coordinates` verlangt weiterhin HTTP(S)-Evidence.

## Warenklassifikation

Die operative Warenlogik basiert auf NHM 2026:

```text
facility_nhm_profiles
        │
        ▼
nhm_codes
        │
        └── parent_row_id → NHM-Hierarchie
```

`nhm_codes` enthält 15.099 NHM-Datensätze. `facility_nhm_profiles` enthält
Facility-spezifische Rollen `input`, `output` und `both` mit Priorität,
Confidence und Evidence-Typ. `official` bezeichnet belegte Standortinformation;
`derived` bezeichnet transparent simuliertes Facility-Verhalten. Eine
`derived`-Beziehung behauptet keine beobachtete Lieferbeziehung.

NST bleibt davon getrennt. `cargo_types` enthält ausschließlich die 20
NST-2007-Kategorien, `facility_cargo_profiles` ausschließlich deren grobe
Legacy-/Statistikprofile. Es gibt keine `NHM:*`-Pseudozeilen in der NST-Tabelle.
Der Game-Core verwendet NST nicht zur Auftragserzeugung.

Konkrete recherchierte Waren bleiben zusätzlich über
`facility_handled_goods -> facility_handled_goods_nhm -> nhm_codes`
nachvollziehbar.

## NHM-Netzwerk und Auftragserzeugung

Alle 352 Facilities besitzen mindestens ein NHM-Profil für `input/both` und
mindestens eines für `output/both`. Für jede Facility existiert mindestens ein
kompatibles anderes Ziel. Matching verwendet die gespeicherte
`parent_row_id`-Hierarchie: identische NHM-Knoten sowie Vorfahr-/Nachfahr-
Beziehungen sind kompatibel. Bei einem hierarchischen Match verwendet der
Auftrag die spezifischere vorhandene NHM-Ware.

Intermodal- und Multimodalterminals besitzen bewusst breitere `derived both`-
Profile. Diese bedeuten Umschlagfähigkeit, nicht Produktion oder real belegten
Warenein-/ausgang. Produktionsstandorte verwenden dagegen möglichst konkrete
Warenfamilien. Vollständige Schiffe werden im Road-Freight-Markt nicht als
Truck-Fracht erzeugt; Werften verwenden dafür plausible Module/Strukturen.

Neue Aufträge tragen:

```text
market_model = nhm_v1
cargo_system = NHM2026
```

`Standardfracht (Simulation)` und `simulated_standard` werden nicht mehr neu
erzeugt. `cargo_basis=documented` bedeutet belegtes Origin-Profil,
`cargo_basis=derived` ein simuliertes Origin-Verhalten. Die konkrete
Geschäftsbeziehung, Tonnage, Vergütung und der Einzelauftrag bleiben immer
Simulation; `relationship_simulated=true` bleibt deshalb erhalten.

## Markt und Bestandskompatibilität

Je routbarer Facility und belegter Nutzlastklasse entsteht weiterhin mindestens
ein Auftrag. Mengen werden wie bisher aus den Payload-Bands erzeugt und liegen
bei 60–100 % der kleinsten Nutzlast der jeweiligen Klasse. `STANDARD_RATE`
bleibt 0,18 €/km/t. Der NHM-Umbau verändert weder Routing, Pricing noch den
Transport-Lifecycle.

Alte noch nicht angenommene Marktangebote ohne `market_model=nhm_v1` werden
beim expliziten Offline-Import berichtet und ausgeschlossen. Sie können nicht
mehr gequotet oder angenommen werden. Bereits gestartete Transporte bleiben
unverändert, fahren mit ihren
gespeicherten Snapshots zu Ende und werden normal ausgezahlt. Auch bei einem
temporären Katalogausfall werden Legacy-Angebote nicht wieder sichtbar.

## Identitäten und Snapshots

`company_uid` und `facility_uid` sind dauerhafte UUIDs. Numerische SQLite-PKs
werden nur intern für Joins verwendet. Aufträge speichern vollständige
Endpunktprojektionen; Transporte besitzen zusätzlich `origin_snapshot` und
`destination_snapshot`. Änderungen am späteren Referenzkatalog verändern
historische Transporte nicht.

`Facility.is_routable()` beantwortet ausschließlich die Frage, ob eine
Position im Spiel verwendet werden darf. `Facility.has_verified_location()`
kennzeichnet separat, ob die Position unabhängig verifiziert ist. Dadurch
bleiben die 273 Simulationsschätzungen spielbar, ohne ihre Datenqualität zu
verschleiern.

## API und Fehler

`GET /api/v1/map/facilities?bbox=west,south,east,north` liefert spielbare
Facilities, `catalogue_version` und `unavailable_count`. Der aktuelle Katalog
hat `unavailable_count=0`. `GET /api/v1/map/hubs` bleibt die kompatible
Envelope-Projektion. Beide Pfade verwenden gespeicherte Koordinaten und rufen
keinen Runtime-Geocoder auf.

Fehlende oder strukturell alte Kataloge ohne `nhm_codes` und
`facility_nhm_profiles` werden als inkompatibel abgewiesen. Gleiches gilt für
gebrochene FKs, NHM-Pseudocodes in `cargo_types` oder Facilities ohne
vollständiges NHM-IN/OUT-Verhalten.

Strukturierte Ereignisse wie `world.catalogue_read`,
`world.catalogue_error`, `market.refresh`, `market.catalogue_unavailable`,
`contract.quote`, `trip.dispatch` und `trip.complete` bleiben erhalten.

## Verantwortlichkeiten und Abnahme

Der Domain-Port liefert unveränderliche Referenzmodelle. SQL liegt
 ausschließlich im Repository. `MarketGenerator` kennt weder SQLite noch
 konkrete Katalogadapter. `NhmProduct` kapselt Warenidentität und NHM-Kompatibilität;
 `FacilityNhmProfile` komponiert das Produkt mit Rolle und Evidenz;
 `Facility` kapselt IN-/OUT-Rollen und Routability; der MarketGenerator
 orchestriert TradeOptions und Contract-Snapshots.

Tests sichern insbesondere:

- 352/352 spielbare Facilities im ausgelieferten Katalog,
- 79 verifizierte und 273 ausdrücklich geschätzte Positionen,
- NHM- statt NST-basierte Runtime-Waren,
- ausschließlich `nhm_v1` für neue Angebote,
- keine neue generische Standardfracht,
- kompatible Origin-/Destination-NHM-Profile,
- Erhalt alter aktiver Transporte,
- Verwerfen alter offener Angebote,
- Read-only/Cleanup, UIDs und Fremdschlüssel,
- Function-Test-Manifest und 100 % Core-Statement-Coverage.

Die allgemeinen Coding-, Architektur- und Quality-Gate-Regeln bleiben in
`CODING_STANDARDS.md`, `ARCHITECTURE.md` und `TESTING.md` verbindlich.

## Runtime-Performancegrenze

Die ausgelieferte Referenzdatei bleibt read-only und die vollständige
Schema-/Provenienzvalidierung bleibt im SQLite-Loader. Im Spielprozess wird die
daraus erzeugte unveränderliche `WorldSnapshot`-Revision anschließend gecacht.
Runtime-Reads sind dadurch Speicherzugriffe und keine wiederholten
15.099-NHM-/352-Facility-Rekonstruktionen.

Map- und Contract-Payloads projizieren FacilityLocationSnapshot kompakt.
Historische Persistenz bewahrt zusätzlich aufgezeichnete Quellen, Waren und
Handling-Evidence. Neue Snapshots expandieren keine gesamten NHM-Profile.
Domainobjekte besitzen keine to_dict/from_dict-Methoden. API- und Repository-
Mapping bleiben getrennt; die HTTP-Ansicht verrät kein Speicherformat.

## Lazy Market Scope und Kartenlebenszyklus

Der Contract-Markt wird nicht mehr global beim Browserstart materialisiert.
`MarketScopeResolver` ist eine injizierte Backend-Abhängigkeit und bestimmt
ausschließlich relevante Origin-Facilities: eigene idle Lkw sind immer im Scope;
zusätzliche Facilities werden erst ab Zoomstufe 7 aus der übergebenen
`FacilityQuery` aufgenommen. `MarketGenerator` erhält nur diese expliziten
Origins und kennt weder Viewport noch HTTP.

Im Frontend besitzt `ContractMarketController` den vollständigen Lebenszyklus
der Contract-Slice-Requests. `WorldMap.marketViewport()` liefert ausschließlich
neutrale Kartenwerte (`zoom`, `bbox`) und kennt keine Contracts-API. `GameSync`
synchronisiert weiterhin nur globalen Spielzustand. Die Composition Roots
injizieren alle zustandsbehafteten Abhängigkeiten.

Facility-Marker entstehen ausschließlich aus eigener Flotte, aktiven
Transport-Snapshots und der aktuell geladenen Contract-Slice. Die vorherige
globale `/map/facilities`-Abfrage gehört nicht mehr zum Browserstart.
Facility-Texte werden nicht dauerhaft als Canvas-Labels erzeugt, sondern nur
bei Hover als textContent-basierte DOM-Popups angezeigt.



## Normalisierte Geografie

Schema 4.0.0 enthält 25 Länder und 304 Städte. Facilities referenzieren eine
verpflichtende Stadt-UUID; redundante Stadt-/Region-/Landspalten entfallen.
Companies referenzieren Länder, ohne einer einzelnen Stadt untergeordnet zu
werden. Company-/Facility-UUIDs bleiben unverändert. Der Runtime-Reader
akzeptiert ausschließlich das normalisierte Schema und öffnet es read-only.

`docs/data/world-geography-v4.json` ordnet alle 352 Facility-UUIDs ausdrücklich
festen Stadt-UUIDs zu. Die Identitäten wurden einmalig erzeugt und werden nicht
bei Migration oder Lookup aus Namen abgeleitet. Neun Gruppen mit fehlenden
Regionsangaben wurden anhand der vorhandenen Standortkoordinaten abgeglichen.
Namen, Koordinatenqualität und Quellen bleiben erhalten; Normalisierung ist
keine neue geografische Verifizierung.

Offline-Aufbereitung: `scripts/normalize_world_catalogue.py --catalogue SOURCE
--backup BACKUP --output TARGET --mapping docs/data/world-geography-v4.json`.
Quelle, Backup und Ziel müssen getrennte Dateien sein. Nach erfolgreichem
SQLite-Backup entsteht ein transaktional normalisiertes Ziel; Identitäten,
Stadtzuordnungen, Fremdschlüssel und Integrität werden abgeglichen. Ein bereits
passendes Ziel wird ohne Neuschreiben akzeptiert, fremde Ziele werden abgewiesen.
Die frühere In-place-Aufbereitung von Schema 2 auf 3 wurde entfernt.
