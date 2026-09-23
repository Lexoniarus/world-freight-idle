# Domänenmodell

Stand: 23.09.2026. Dieses Dokument beschreibt die implementierte Struktur.
Entscheidungsgründe stehen in ADR 0005/0006, Fortschrittshistorie in
REFACTOR_EXECUTION.md. Domainobjekte kennen keine Persistenzformate.

## Spielerzustand

| Objekt | Verantwortung |
| --- | --- |
| PlayerState | Validierte ganzzahlige Geld-/Fortschrittswerte; debit, complete_delivery, replace_cash |
| OwnedVehicle | Stabile lokale ID, Kaufwerte, Status und Facility-UID; validate_dispatch, start_trip, arrive, apply_model |
| ContractOffer | Angebot mit validierten Mengen, Konditionen, Endpunkten und Verfügbarkeit |
| ActiveTransport | Historischer Auftrag, Fahrzeug, Route, Kosten, Auszahlung und genau einmaliges Settlement |

Identitäten sind innerhalb eines Spielers eindeutig. Ein Fahrzeug besitzt genau
eine facility_uid und einen historischen Standort; `hub_id` existiert nur in
öffentlichen API-Projektionen. Modellkennung und Kilometerkostensatz bleiben
bei älteren gekauften Fahrzeugen optional, damit keine Werte erfunden werden.

Entities schützen fachliche Invarianten und besitzen benannte Zustandswechsel.
Zeitabhängige Regeln erhalten Zeitpunkte vom Aufrufer. Guthaben ist ganzzahlig;
Mengen, Strecken und Zeiten müssen endlich und zulässig sein. ActiveTransport
wechselt nur von active nach settled und bewahrt den Settlement-Zeitpunkt.

## Werte und Snapshots

- ContractOfferSnapshot enthält die unveränderlichen erzeugten Angebotswerte.
  ContractOffer.from_snapshot übernimmt sie unter Prüfung der Angebotsregeln.
- HistoricalContractSnapshot enthält die vereinbarten Transportwerte. Er ist
  kein verfügbares Angebot und erbt nicht von ContractOffer. Aktuelle Angebote
  werden bei Disposition explizit in diesen Snapshot überführt.
- RouteSnapshot enthält validierte Koordinaten, Strecke, Fahrzeit und Provider.
- FacilityLocationSnapshot hält damalige Facility-/Stadtidentitäten, Namen,
  Adresse, Koordinaten und Evidenz unabhängig vom späteren Katalog. Historische
  Quellen, Warenbelege und Handling-Evidence werden mitbewahrt. Die HTTP-
  Darstellung bleibt kompakt und expandiert diese Referenzaggregate nicht.
- CompanyIdentity enthält bekannte historische Firmenangaben. Bei früher nur
  gespeicherter company_uid bleiben nicht aufgezeichnete Namen unbekannt.
- DocumentedCargo bewahrt eine historische Warenbeschreibung ohne nachträglich
  eine NHM-Identität zu behaupten. Neue Angebote verwenden NhmProduct.
- PriceQuote und calculate_price sind reine Wirtschaftswerte/-berechnung.
  VehicleModel und VehicleImage beschreiben Referenzangebote und Bildprovenienz.

## Referenzwelt

Country besitzt Code und Namen. City besitzt dauerhaft gespeicherte city_uid,
Namen, Country und optionale Region. Address komponiert City mit Straße,
Hausnummer und Postleitzahl. Coordinates validiert endliche WGS84-Werte.
Facility komponiert Address/Coordinates, Company-Bezug, Quellen und Warenprofile.
Eine Company kann Facilities in mehreren Städten und Ländern besitzen.

NhmProduct beschreibt Warenidentität und die gespeicherte NHM-Hierarchie.
FacilityNhmProfile komponiert ein Produkt mit input/output/both, Confidence,
Priorität und Evidenz. DocumentedGood enthält den unabhängigen recherchierten
Warenhinweis samt Quelle. Reale Fakten behaupten keine simulierte Lieferbeziehung.

WorldSnapshot ist eine konsistente unveränderliche Katalogrevision. WorldScope,
CountryScope, CityScope und CompanyScope sind immutable Filteransichten:

```python
world = WorldScope(snapshot)
berlin = world.country("DE").city("Berlin")
facilities = berlin.company(company_uid).facilities
```

UIDs sind eindeutig; Namensabfragen benötigen einen eindeutigen Treffer im
gewählten Scope. Sonst entsteht AmbiguousWorldReference. Firmen werden über
Facilities gefiltert und nicht als Kinder einer einzelnen Stadt gespeichert.

## Ports und entfernte Strukturen

GameStateRepository liefert typisierte Spieler, Fahrzeuge, Angebote und
Transporte; GameUnitOfWork besitzt die Transaktion. Accounts, Cache, Kataloge,
Routing und öffentliche Leseprojektionen besitzen explizite Ports.

Hub, Minimal-Contract, CargoType, CargoProfile und RouteResult sind entfernt.
Es gibt keine KV-Spielstandzugriffe, Domain-to_dict/from_dict-Methoden oder
parallele Alt-/Neulaufzeit. Nur das isolierte Offline-Importwerkzeug kennt die
alten Dokumente. Konkrete Persistenz und Serialisierung liegen im Repository,
öffentliche JSON-Projektionen im API-Bereich.
