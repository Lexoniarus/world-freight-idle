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

Vorgezogen: reale Referenzunternehmen, Facilities und dokumentierte Waren
aus dem WorldCatalogue. Geplant bleiben Branchen-/Eurostat-Warenströme und
regionale Wirtschaftsprofile. Geschäftsbeziehungen und Einzelaufträge bleiben
simuliert. Später FAF und UN Comtrade für weitere Regionen.

## M3 – Fleet Management

Vorgezogen: acht reale Modellprofile, DB-Kauf, Reputationsfreigaben und
fahrzeugbezogene Spiel-Kilometerkosten. Geplant bleiben Verbrauchssimulation,
Alter, Wartung, Energiehalte, zusätzliche Depots, Leerfahrten und Rückfracht.

## M4 – Multiplayer Economy

Lieferungsrangliste vorhanden. Geplant: gemeinsamer knapper Auftragsmarkt,
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
Initialisierung atomar, HTTP-Clients über den gesamten Lifespan geschützt und
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
