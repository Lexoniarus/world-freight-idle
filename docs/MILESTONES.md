# Meilensteine

Nummerierung und Zielumfang folgen GOAL.md, Abschnitt 37.
Einzelne vorgezogene Funktionen bedeuten nicht, dass ein Meilenstein fertig ist.

## M0 – Foundation

Vorhanden: Modulstruktur, OOP, PEP 8/Ruff, Tests, Function-Test-Manifest,
Logging/Tracing, dokumentierte Provider-Ports, main.py und Quality Gate.
CI und PR-Workflow sind eingerichtet; konkrete Prüfläufe stehen im Qualitätsbericht.

## M1 – European Road Freight MVP (in Arbeit)

Aktuelle Reihenfolge: **UI First**, danach Backend-Ausbau. Die Kartenphase
verwendet den bestehenden spielbaren Kern. Spielerunternehmen-/Depot-Domänenmodelle
werden anschließend umgesetzt; die Gesamt-M1-Abnahme bleibt bis dahin offen.

Vorhanden: Accounts und Sessions, getrennte Spielstände, Startkapital,
Fahrzeuge und Kauf, reale Facilities, gespeicherte Koordinaten und Valhalla-Truck-Routing,
Aufträge, parallele Transporte, Tracking, Offline-Fortschritt und Reputation.

Für vollständige Abnahme nach GOAL.md, Abschnitt 35, fehlen:

- Eigenständiges Spielerunternehmen mit Besitzzuordnung.
- Persistentes eigenes Startdepot, Standort, Kapazität und Fahrzeugzuordnung.
- Durchgehende Abnahme des gesamten Loops mit Unternehmen und Depot.

UI-Phase implementiert: MapLibre GL JS, OSM-Standardkarte, Pan/Zoom,
World Wrapping, Kontextpanels, Fahrzeugshop, mehrere Transportmarker,
mobile Sheets und Provider-Abstraktion. Satellitenbilder sind aus M1
ausgenommen und folgen später als SatelliteTileProvider. Karten-POIs
sind zunächst Basiskarteninhalt. Spielerunternehmen und eigene Depots brauchen
weiterhin echte Spielzustände und werden nicht als vorhanden simuliert.

Der aktuelle Hub ist ein öffentlicher Frachtstandort, kein gekauftes Depot.

## M2 – Real Economy Data

Vorgezogen: reale Referenzunternehmen, 559 spielbare Facilities und ein
NHM-basiertes IN/OUT/BOTH-Verhaltensmodell aus dem WorldCatalogue. Geplant
bleiben Branchen-/Eurostat-Warenströme und
regionale Wirtschaftsprofile. Geschäftsbeziehungen und Einzelaufträge bleiben
simuliert. Später FAF und UN Comtrade für weitere Regionen.

## M3 – Fleet Management

Vorgezogen: 14 reale Modellprofile, DB-Kauf, Reputationsfreigaben und
fahrzeugbezogene Spiel-Kilometerkosten. Konstanter Verbrauch, 10 % Reserve,
Geschwindigkeitsgrenze und automatische Energiehalte sind als erste Simulation
umgesetzt. Geplant bleiben Last-/Wettereinflüsse, Stationssuche, Ladekurven,
Alter, Wartung, zusätzliche Depots, Leerfahrten und Rückfracht.

## M4 – Multiplayer Economy

Lieferungsrangliste und gemeinsamer Live-Verkehr vorhanden.
Geplant: gemeinsamer knapper Auftragsmarkt,
regionale Märkte, dynamische Frachtraten und Marktanteile.

## M5 – Rail Freight

Geplant: Schienennetz, Güterterminals, Zugflotten und Rail-Routing-Adapter.

## M6 – Sea Freight

Geplant: Häfen, Schiffe, maritime Routen und Containerlogistik.

## M7 – Air Cargo

Geplant: Cargo-Airports, Flugzeuge und Luftfrachtnetz.

## M8 – Multimodal Logistics

Geplant: Transportketten mit mehreren Teilstrecken, Umladung,
Terminalaufenthalten und globaler Netzwerkoptimierung.

## Freigabe für öffentlichen Betrieb (querschnittlich)

HTTPS, kontrollierter Reverse Proxy, geeignete Provider-Endpunkte,
Account-Recovery, Backups/Restore, Moderation und Lasttests.
PostgreSQL mit Migrationen und verteilte Limiter vor größerer Skalierung.
Diese Arbeit ist noch offen; lokale Tests sind keine Produktionsfreigabe.

## Standards-Bereinigung der vorhandenen UI-Basis

Vor weiterem M1-Backend-Ausbau: Einstieg und Zuständigkeiten aufgeteilt,
Lifecycle/DI ergänzt, DOM-Ausgabe vereinheitlicht, D3-/Mehrseiten-Altbestand
entfernt und Frontend-Gates eingeführt. Bestehende Core-Regeln, Konten und
Spielstände bleiben kompatibel; es gibt keine automatische Datenmigration.
Prüfbelege und Grenzen: [QUALITY_REPORT.md](../QUALITY_REPORT.md).
Dies ersetzt keine Produktabnahme durch den Nutzer.


### Nachbesserung: Fotos, WLAN und Startfahrzeug

Verifizierte Katalogfotos einschließlich Lizenzhinweisen, WLAN-Bindung sowie
DB-IVECO als kostenlose Startausstattung sind integriert. Bestehende Profile
werden nur ausdrücklich und nach Backup gepflegt. Zwei getrennte Sitzungen
werden im Browsertest geprüft; die iPad-Anmeldeseite im WLAN wurde vom Nutzer
bestätigt. Die vollständige reale iPad-Spielrunde ist noch nicht abgenommen.
M1 insgesamt bleibt in Arbeit; Prüfzahlen stehen im Qualitätsbericht.


### Standards-Reparatur der vorhandenen Basis

Die drei nachträglich gefundenen Standards-Lücken sind adressiert: öffentliche
Initialisierung atomar, Routing-HTTP-Client über den gesamten Lifespan
geschützt und
Profilpflege in injizierten Services/Repositories. Die zusätzliche Race-Condition
zwischen Profilpflege und Transportstart besitzt eine Regression. Dies ist
Basisstabilisierung; es werden keine neuen Wirtschaftsmechaniken freigegeben.

## WorldCatalogue-Integration

Referenzdaten werden read-only ausgeliefert; UUIDs, Snapshots, explizite
Bestandsmigration und Facility-API ersetzen Produktions-Seeds. Dies schließt
M1 nicht ab. Details und verbleibende Datenlücken: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md).

Aufträge werden je routbarer Facility und belegter Nutzlastklasse aus dem
Fahrzeugkatalog ergänzt. Auch kleine Transporter und bestehende Fahrzeuge
erhalten geeignete Mengen; `payload_band` ist simuliert, reale Warenbelege
bleiben getrennt. Mengenregeln und Kompatibilität: [WorldCatalogue](WORLD_CATALOGUE.md).

### Gemeinsamer Live-Verkehr

Für M4 vorgezogen ist nun eine geteilte, read-only Verkehrssicht auf aktive
Straßentransporte vorhanden. Die eigentlichen Spielstände bleiben pro Account
isoliert. Spielerfarben werden deterministisch aus der Account-ID erzeugt; eine
spätere frei wählbare Unternehmensfarbe kann dieselbe Darstellungsgrenze nutzen.
Ein gemeinsamer knapper Auftragsmarkt und Marktanteilsmechaniken bleiben offen.

Der relationale TrafficReader filtert aktive Transporte und validiert ihre
gespeicherten Snapshots, bevor er öffentliche Trackingwerte weitergibt.
Fehlerzustände bleiben sichtbar; Sprite-Farbe und Farbring kennzeichnen den
Halter. Alle 14 Modelle besitzen lokale Karten-, Front- und Seitenansichten.
Die gemeinsame Asset-Zuordnung und Modellordner ändern keine Spielmechanik.


## Aktuelle technische Grundlage

Typisierte Entities, relationale SQLite-Spielpersistenz (Schema 1.1.0) und
WorldCatalogue 4.2.0 bilden die einzige Laufzeit. Historische Snapshots bleiben
bei Katalogupdates erhalten. Details beschreiben [Architektur](ARCHITECTURE.md),
[Domainmodell](DOMAIN_MODEL.md) und [Persistenz](RELATIONAL_STATE.md).
Die abgeschlossene Umbauchronik liegt im [Archiv](archive/REFACTOR_EXECUTION.md).
Aktuelle Prüfungen und Grenzen stehen im [Qualitätsbericht](../QUALITY_REPORT.md).
Dieser technische Stand ersetzt weder die vollständige MVP- noch reale iPad-Abnahme.


## Market v2 – implementierter Stand vom 25.09.2026

Stadtmärkte eigener idle Fahrzeuge ersetzen Nutzlastklassen und Viewport-Scope.
V2 bewahrt gültige fahrbare Angebote und ergänzt Facility-/Distanz-Coverage.
Explizite Fahrzeugwahl steuert Quote, Betriebskosten und Energie. Die tatsächliche
Anfahrt wird mitgeplant; Dispatch und anschließender Markt-Refill besitzen
getrennte Transaktionen. Historische Transporte und gespeicherte Konditionen
bleiben erhalten. Trailer, Versicherungen und weitere Simulationen sind nicht
Bestandteil dieser Änderung. World 4.2.0 und Vehicle 2.2.0 sind die einzigen
Referenzschemata. Frühere Bestandszahlen in der Fortschrittschronik beschreiben
den damaligen Katalog; OwnedVehicle-Zahlen sind kein Architekturvertrag.
Details und Abnahme: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md),
[Qualitätsbericht](../QUALITY_REPORT.md).


## Frontend v2 – lokaler Implementierungsstand

Ausgangspunkt ist der geprüfte Market-v2-main `614ec730fc09a43151f9751d644190ace17a14be`.
Branch: `feature/frontend-v2`. Phasen: City Context/Design/Panel Modes und Layer-
State; Kartenlesbarkeit und Gruppen; Flotten-/Assetrollen; Stadtmarkt und
Fahrzeugwahl; Analytics Read Model/API; Unternehmen/Charts; Responsive/A11y;
Regression und Dokumentation. Veröffentlichung und Merge sind nicht umfasst.

Market v2, World 4.2.0 und Catalogue 2.2.0 bleiben fachlich erhalten. Der einzige
Markt-Cleanup entfernt die irreführende initiale TradeOptions-Gesamtzahl im Log.
Transaktionsoptimierung, neue Modelle/Assets und zusätzliche Gameplay-Systeme
bleiben außerhalb dieses Meilensteins. Prüfstatus: [Qualitätsbericht](../QUALITY_REPORT.md).


## Abholanfahrt – Umsetzung auf feature/frontend-v2

Separater DispatchPlanningService und immutable Routenplan, kontinuierliche
Energieplanung über zwei Strecken, unveränderter Abfahrtscheckpoint, additive
API-/Snapshotfelder sowie Abschnittstracking sind umgesetzt. Abnahme umfasst
Rollback/Konkurrenz, Historie, Desktop/Mobil/Reduced Motion und individuelles
SRP-Review; die ausgeführten Ergebnisse stehen im aktuellen Qualitätsbericht.

## Frontend-v2: Wirtschaft und Darstellung

Ergänzt: Beta(3,1)-Beladung, gespeicherter NHM-Tarif, getrennte Wartung und
Energieeinkäufe, global atomarer Marktneuaufbau, persistente Firmenfarben,
Asset-Gruppen und Analyticsnamen. Lokale Umsetzung auf dem erhaltenen
Anfahrtsfix. Aktuelle Gates und Review: [Qualitätsbericht](../QUALITY_REPORT.md).
