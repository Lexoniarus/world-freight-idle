# Teststrategie

## Verbindliche Prüfungen

`python scripts/quality.py` beziehungsweise `make quality` führt Ruff/Format,
mypy, Pyright, pytest mit 100 % app-Statement-Coverage, Function-Test-Manifest,
Architekturtests, Frontend-Verhaltenstests, ESLint, Stylelint, Prettier, checkJs,
Vite-Produktionsbuild und compileall aus. Node 24, requirements-dev.txt und
npm ci sind Voraussetzung. Die Offline-CLIs gehören zu Lint und Typprüfung.

Vor Arbeitscommits müssen die betroffenen Tests samt direkten Aufrufern grün
sein. Das vollständige Gate und E2E sind vor der abschließenden Integration
verbindlich. Tests werden nicht übersprungen oder abgeschwächt. Jeder konkrete
Core-Callable inklusive Konstruktor und verschachtelter Funktion erhält einen
expliziten Gegentest in tests/function_test_manifest.py. Protokolldeklarationen
werden strukturell ausgenommen.

## Verhalten und Grenzen

- Domain: Invarianten, immutable Werte, unzulässige Zustandswechsel, Mengen,
  WGS84, Zeitreihenfolge, kompakte öffentliche Projektionen.
- Persistenz: getrennte Besitzer mit gleicher lokaler Fahrzeug-ID, atomare
  Käufe/Disposition/Settlement, parallele Schreibabläufe, Rollback, kaputte
  Snapshots, Cleanup und Ablehnung alter oder unbekannter Schemata.
- Historie: unveränderte Endpunkte/Quellen/Konditionen bei Katalogänderung oder
  Ausfall, genau einmalige Auszahlung und keine erfundene Transporthistorie.
- Referenzwelt: Schema 4, readonly/FKs, stabile UUIDs, überprüftes Stadtmanifest,
  wiederholbare Normalisierung und mehrdeutige Scope-Namen.
- Provider/API: malformed/nonfinite Antworten, Cacheersatz, HTTP-Fehler,
  Authentifizierung, Sessionablauf, CSRF, Traces und private Datentrennung.
- Frontend: DOM-Text statt HTML, Cleanup, verspätete Antworten, unsichere
  Schreibantworten, Fokus, Karten-Wrapping, Fahrzeugbilder und Panel-Lebenszyklen.

Architekturtests prüfen direkte und indirekte Imports einschließlich relativer
Imports, Re-Exports und statisch erkennbarer dynamischer Imports. Domain und
Services kennen kein SQL, konkrete Speicheradapter oder Serialisierung.
Frontend-Views importieren weder API noch Controller/State. Negativbeispiele
belegen die Scanner. Grüne Tools ersetzen kein manuelles Zuständigkeitsreview.

## Offline-Import

`python scripts/import_legacy_game.py --source OLD --check` inventarisiert nur
lesend. Ausführung benötigt --backup BACKUP und --output NEW; alle drei Pfade
müssen verschieden sein. Bestehende Ausgaben werden nie überschrieben. Ohne
Backup gibt es keinen Import. Aktivierung erfolgt separat nach Abgleich.

Fixtures prüfen alle gespeicherten Werte, Passwort-Hash-Erhalt ohne Ausgabe,
unterschiedliche historische Auftragsformate, drei isolierte Konten, WAL-Backup,
Backup-/Schreib-/Abgleichfehler, Cleanup und wiederholten Ausführungsversuch.
Sessions/Caches werden nicht übernommen. Intakte unspielbare Angebote werden
berichtet, beschädigte/ungeklärte Daten brechen ab. --exclude-global-demo ist
nur für den ausdrücklich freigegebenen kontolosen Demostand vorgesehen.

## Browser und tatsächliche Geräte

`npm run test:e2e` startet den FastAPI-Kern mit separater temporärer Datenbank,
Mock-Routing und lokalen Tiles auf Port 8011. Öffentliche OSM-Tiles werden nicht
automatisiert vorgeladen. Der Lauf umfasst Registrierung, Anmeldung, Kauf,
parallele Transporte, Offline-Ankunft, Rangliste, Mehrspielerkarte, Bildstabilität,
Deep Links, Fehlerfälle und Tastaturbedienung.

Desktop 1440 × 900, Mobilansicht 390 × 844 und Reduced Motion werden geprüft.
PLAYWRIGHT_CHANNEL wählt den Browser; PYTHON_EXECUTABLE den Interpreter.
CI installiert Chromium. Lokale Screenshots werden zusätzlich visuell geprüft.
Automatisierte Mobilansicht ist keine reale iPad-Abnahme. Provider-Mocks beweisen
keine öffentliche Dienstverfügbarkeit. Tatsächlich ausgeführte Ergebnisse stehen
in QUALITY_REPORT.md; historische Läufe sind keine aktuelle Freigabe.

## Regressionen des Persistenzreviews

Ein Dashboard mit 100 abgeschlossenen Transporten darf keinen historischen
Transport deserialisieren. Gemischte Bestandsfixtures sichern aktive/fällige
SQL-Abfragen, Spielertrennung und die inklusive Fälligkeitsgrenze.
Manipulierte Testschemata prüfen gleichnamige unwirksame Indizes/Trigger und
fehlende Schlüsselbeziehungen; Formatierung darf gültige Guards nicht ändern.

Der Offline-Importer validiert auch verschachtelte Firmen, Waren, NHM-Profile,
Quellen und GeoJSON-Objekte vor dem Mapping. Unbekannte Felder oder falsche
Container brechen beide Modi mit einem Feldpfad ohne Feldwerte ab. Vorhandene
Stadt-UUIDs und doppelte Standortprojektionen müssen uebereinstimmen.
Leere/fehlende Feature-Properties bleiben erlaubt; nichtleere Properties werden
abgewiesen, weil der Routensnapshot sie nicht speichert. Bei fehlendem
location_snapshot wird eine vorhandene historische hub-Projektion verwendet.
Diese Tests verwenden ausschließlich temporäre Datenbanken; die bereits
migrierten Profile werden nicht erneut importiert.

## Asset-Bestandsaufnahme

`assets/inventory.json` sichert vor der Ordnerumstellung alle 134 SVGs mit
Modellzuordnung, bisheriger Verwendung, Alt-/Zielpfad und SHA-256. Die 42 aktiven
Zuordnungen wurden aus dem bestehenden Karten-/Fahrzeugbild-Code erfasst und
werden unabhängig vom neuen Resolver geprüft. Das feste Browser-Testprofil
AssetReference liefert Flotten-/Shopansichten auf Desktop und Mobil.
ASSET_VISUAL_PHASE benennt den lokalen Screenshot-Ordner unter artifacts.
Der Dateitest prüft jetzt alle Zielpfade gegen die vorab gespeicherten Hashes;
unbekannte/fehlende Modelle und unveränderliche Zuordnungen sind Gegenfälle.
`tests/test_assets.py` prüft für alle 42 verwendeten SVGs HTTP-Status, MIME und
Dateihash sowie 404 für alte oder fehlende Pfade, mit temporärem Spielstand.
Kartenverhalten (Farbmaske, Orientierung, Rasterisierung, Cache und Cleanup)
und Bildstabilität bleiben durch die vorhandenen Regressionen abgesichert.


Energietests verwenden `tests/fixtures/energy-timeline.json` gemeinsam in Python
und JavaScript: Bewegung, Pausenanfang/-ende und Ankunft stimmen an denselben
Grenzen überein. Browserregression prüft Desktop und Mobil mit einem ausdrücklich
synthetischen Kurzstrecken-Energieprofil im isolierten Testserver. Dessen
Fixture-Endpoint existiert ausschließlich in `tests.browser_server`, niemals
im Produktions-Einstieg. Echte Katalogwerte werden separat für alle 14 Modelle
geprüft. Tank-/Ladepausen, Logout/Offline-Ankunft, verbleibende Energie sowie
stabile Bildknoten werden im Browser beobachtet.

Energie-Upgrade-Gegenfälle prüfen unbekannte Modelle, falsche Snapshotformen,
Boolesche Versionswerte, beschädigte Besitzbeziehungen und Integritätsfehler.
Fehlgeschlagene Abgleiche entfernen die Ausgabe, bewahren die Quelle und melden
ein strukturiertes Rollback-Ereignis. Runtime-Snapshots weisen unbekannte
Fahrtplanfelder zurück. Konkurrierende Dispositionen prüfen das Angebot nach
Routing erneut; ein veränderter Energiecheckpoint verhindert Teilabrechnungen.


## Stadtmarkt-Abnahme

- Referenzversionen 4.2.0/2.2.0, Pflichtprofile, FKs, Read-only, Segmentmapping,
  endliche Werte, positive Preise, Unit-Weights und Load-Factor-Grenzen.
- City-UID-Scope, Same-City-Relationen, fehlender Standort-Snapshot, explizite
  Modellauflösung, lazy Origin-Indizes und Generierung ohne Router.
- Exakte Distanzgrenzen, Facility-/Band-Coverage, geplante Angebote mitzählen,
  Vielfalt und Wiederholungen, Tonnage und gespeicherte Konditionen.
- Maximalwert für Candidate-Gewicht und getrennte gewichtete Fahrzeugwahl.
- Retention nach Flottenänderung, V1-Verwerfen, Ankunft, historische Snapshots.
- Same-City-Reposition, konkurrierender Dispatch und vollständiger Rollback.
- Refill erst nach Dispatch-Commit; separate SQLite-Verbindung beobachtet den
  gestarteten Transport, Refill-Schreibfehler rollt ausschließlich neue Offers
  zurück. Späterer Refresh führt keinen zweiten Dispatch aus.
- Pflichtfahrzeug HTTP 422, serverseitige eligible_vehicle_ids, Auswahlwechsel,
  entfernte Angebote und verspätete Antworten. Browser-Pan/Zoom ohne Marktread.

Das manuelle Review jeder geänderten Core-Funktion steht im Qualitätsbericht
und im zugehörigen [SRP-Review](MARKET_V2_REVIEW.md). Die dortigen Befunde sind
zusätzlich zum expliziten Function-Test-Manifest erforderlich.


## Frontend v2 – Regressionen

`tests/test_analytics.py` prüft Authentifizierung, Nutzertrennung, alle Zeiträume
und Scopes, UTC-Grenzen, leere/negative/V1-Historie, beschädigte Hüllen, laufende
Fahrten, Importlücken und idempotente Offline-Ankunft. Monkeypatch-Gegenproben
verbieten load_transport_record, load_transport, RouteSnapshot und ActiveTransport
im Reader. Große Koordinatenarrays bleiben in SQLite; Python erhält nur Skalare.
Zusätzlich erzwingt PRAGMA query_only die rein lesende Aggregation.
Neue Core-Callables stehen im Function-Test-Manifest.

`frontend/frontend-v2.test.mjs` ergänzt UUID-Stadtauswahl, bekannte inaktive
Städte, Deep Links/Legacy-Auflösung, verspätete Antworten, accountgebundene
Layer-Presets/Overrides, Gruppierung ohne Koordinatenänderungen, serverseitige
Eligibility, getrennte Listen-/Detailzustände, Assetrollen und Charttabellen.
Vorhandene Quote-/Dispatch-/Cleanup-/Bildstabilitätsprüfungen bleiben erhalten.

Playwright prüft den kompletten Dispositionsablauf sowie mobile Sheets,
Browserhistorie, Kamera-/Canvas-Kontinuität und keine Marktrequests bei Pan/Zoom.
Frontend-v2-Prüfungen ergänzen Unternehmens-Scopes, Auswahl-/Layerkontinuität,
Gruppenbedienung und Desktop 1440×900, Tablet 1024×768, Mobile 390×844.
Automatisierte OSM-Tiles werden durch lokale Testbilder ersetzt; reale
Kartenlesbarkeit wird separat manuell geprüft, ohne automatisierte Tile-Downloads.

Pflichtgates bleiben `python scripts/quality.py` und `npm run test:e2e`.
100 % App-Statement-Coverage, Asset-Hashes und Manifest sind unverändert bindend.
Tatsächlich ausgeführte Ergebnisse stehen im [Qualitätsbericht](../QUALITY_REPORT.md).


## Anfahrt zur Abholung

`tests/test_dispatch_approach.py` prüft Abschnitts- und Snapshot-Invarianten,
A ≠ B, A = B, gleiche Koordinaten, fehlende Koordinaten, Routingausfall,
Provider-/Geschwindigkeitsgrenzen, Energiehalte vor, auf und nach B,
kontinuierlichen Füllstand, getrennte Kosten/Erlöse und einfache Grundbeträge.
Separate SQLite-Verbindungen belegen Routing außerhalb der Schreibtransaktion.
Standortänderung während Routing und vor Commit, parallele Annahme, Rollback
nach Transportanlage/Offer-Verbrauch sowie Reload/Offline-Settlement sind
explizite Gegenfälle. Markt-Lifecycle-Tests sichern weiterhin Refill-Isolation.

`frontend/approach.test.mjs` nutzt bewusst gegensätzliche Geometrie-/Straßenlängen:
B muss exakt am Kilometer-/Zeitwechsel erreicht werden, auch mit Energiehalten
auf beiden Seiten. Eigene und öffentliche Fahrzeuge teilen diese Grenzen;
Alttransporte behalten ihre Einzelfahrt. Browserfälle prüfen Start A, automatische
Abholung, getrennte Kilometer, Reload in beiden Phasen und Reduced Motion auf
Desktop/Mobil. Die bestehenden Auswahl-, Quote-, Pan-/Zoom- und Offline-Tests
bleiben Teil des vollständigen Regressionslaufs.

## Frontend-v2: Wirtschaft, Start und Assets

Zusätzliche Tests prüfen deterministische statistische Beladungen, konkrete
Wartungsprojektion, kaufmännische Rundung, null/einen/mehrere Energieeinkäufe,
Fahrzeugwechsel ohne Tarifänderung, globalen Startup-Rollback, unveränderte
Historie, isolierte Farben und öffentliche Projektion. Frontendtests prüfen
aktive Städte, URL-Aufräumen nach Dispatch, verspätete Assetantworten,
Lease-Übergabe und erhaltene Bildknoten. Browserregressionen prüfen Desktop,
Tablet, Mobil, Reduced Motion, Firmenfarben und regionale Fahrzeuggruppen.
`python scripts/audit_economy.py` erstellt die lokale Wirtschaftsmatrix.
Verbindliche Gates: `python scripts/quality.py`, `npm run test:e2e`; konkrete
Ergebnisse und Funktionsreview stehen im [Qualitätsbericht](../QUALITY_REPORT.md).


Den Frontend-Build vor dem Browserlauf abschließen. Vite ersetzt `static/dist`;
ein gleichzeitig ausgeführter Build kann Anmeldeseiten/Assets kurzzeitig
entfernen und erzeugt ungültige Browser-Testbedingungen. Empfohlene Reihenfolge:
Quality-Gate einschließlich Build abschließen, danach `npm run test:e2e`.

## Karten-, Paint- und Fokusregressionen

`map-regressions.test.mjs` prüft Überschneidung statt Mittelpunkt-Radius,
Status-/Eigentümerpartitionen, Pose-Aktualisierung, Maskenmathematik,
Fokusverbrauch und schnelle/fehlgeschlagene Farbwechsel.
`tests/browser/map-regressions.spec.js` verwendet echte MapLibre-Layer
mit den Produktionsmodulen in einer ausschließlich im Test abgefangenen
Modulumgebung. Richtungen werden an gerenderten Pixeln und Screenshots
geprüft; alle 42 Rollen erhalten Alpha-/Bauteil-/Farb-Gegenproben.
Die normalen Browserfälle ergänzen sichtbare Palette, Retry, Navigation
sowie einen und mehrere tatsächliche Energieeinkäufe. Keine OSM-Downloads.

Vollständiges Quality-Gate und E2E nacheinander ausführen; ein Vite-Build
darf dem laufenden Browserregressionsserver nicht seine Assets entfernen.
Lokale Renderer-Belege: `artifacts/map-regressions/`, Lackierungs-Proofs:
`artifacts/masks/`, normale UI-Belege im konfigurierten Temp-Verzeichnis.


Die Ergänzung `market-context` prüft den scopefreien Kartenüberblick,
Fahrzeugpriorität vor widersprechender Stadt-URL, ausschließlich serverseitig
geeignete Angebote in Liste und Karte sowie das Leeren nach Abfahrt. Ein explizit ungeeignetes
Fahrzeug blockiert die Quote bis zur bewussten Neuwahl. Browserregression
verifiziert auch Back/Forward und die Rückkehr zur Weltkarte ohne Stadtparameter.
Die Rendererprüfung deckt zusätzlich gedrehte Karten, fremde Gruppen und
Facility-Wiederherstellung bei unveränderten Auftragsmarkern ab.


## Global Routing Readiness

Strukturelle MarketCandidateService-Generierung bleibt ohne Router.
Market Publication verlangt RoutingReadiness. Partial bedeutet fehlende Coverage,
niemals ungeprüfte Offers. Gezielte Tests prüfen Relations-Leases, historische
Snapshot-Kompatibilität, Offer-Referenz-Rollback, Worker und Providerlimits.
Automatisierte Providerprüfungen verwenden Mocks.

Vor Integration bleiben das vollständige Quality-Gate, die vollständige
Playwright-Suite und git diff --check erforderlich. Für diesen Korrekturauftrag
führt Codex ausdrücklich nur gezielte Prüfungen aus; die Gesamtsuiten übernimmt
der Nutzer anschließend. Fehler
werden ohne Abschwächung von Tests oder Coverage-Anforderungen behoben.
Vite Build muss vor dem Browserlauf vollständig abgeschlossen sein.

Einzelreview der Implementierung: [ROUTING_READINESS_REVIEW.md](ROUTING_READINESS_REVIEW.md).
Tatsächliche gezielte und vollständige Befehle sowie Ergebnisse stehen im aktuellen Abschnitt des
[Qualitätsberichts](../QUALITY_REPORT.md); frühere vollständige Gates in dessen
historischen Abschnitten gelten nicht als Abnahme dieser Implementierung.


## Gezielte Review- und Vehicle-Ready-Regressionen

`test_review_regressions.py` prüft negative/stale Generationen, eigenständigen
und äußeren Bind-Rollback, Scheduler-/Status-/Finish-Fehler, verschwundene Jobs,
Cancellation, Generationwechsel und die typisierte deterministische Auditmatrix.
`test_vehicle_market.py` prüft kleinere/größere Fahrzeuge, geteilte Offers,
Delivery plus individuelle Approaches, stale Eligibility, erschöpfte Pools,
Abfahrt während Await, API-Besitz/idle-Prüfung und priorisierte Approaches ohne
Delivery-Batch-Starvation. Stadt-Coverage allein beendet den Worker nicht.
Die expliziten Manifest-Gegentests bleiben verbindlich; kein Coverage-Limit
wird gesenkt. Gezielte Coverage ersetzt keinen Nachweis der gesamten Core-Suite.
Frontend-Cleanup versucht alle Freigaben und meldet danach AggregateError;
Destroy ist idempotent. Browsertests erwarten passende Offers auch in partial
Markets, statt globales `ready` vorauszusetzen. Provider bleiben gemockt.

Die vollständigen Befehle für die anschließende Nutzerabnahme, nacheinander:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/quality.py
npm run test:e2e
git diff --check
```

Kein Build während Playwright. Keine echten Provider-Bulk-Aufrufe.


## Gezielte Abnahme: befahrbare Standortverbindungen

Für den Fix auf `5d7ff77` wird auf Nutzerwunsch keine vollständige Suite
aufgerufen. Der gezielte Lauf umfasst `test_connected_routing`,
`test_routing_anchors`, `test_anchor_repair_history`,
`test_routing_anchor_provider`, `test_routing_readiness_store`,
`test_dispatch_routing_anchors`, `test_dispatch_approach`,
`test_market_preparation`, `test_review_regressions`, `test_vehicle_market`,
`test_routing_audit`, `test_function_contract` und `test_architecture`.
Coverage wird für die acht betroffenen Routing-/Dispatchmodule ausgewiesen,
nicht als Gesamt-Core-Abnahme. Ruff/Format, mypy und Pyright prüfen die
geänderten Pythondateien. Konfiguration wird separat gezielt geprüft.

Die Wolfsburg-Fixture enthält reale Providerantworten für den unverbundenen
und den rund 504 Meter entfernten funktionierenden Anker. Eine begrenzte
Live-Gegenprobe erfolgt ausschließlich auf einer SQLite-Backupkopie mit
normalem Markt, Dispatch, Ankunft und nächster Quote. Vorgehen, Resultate und
Restabnahme: [Verbindungsprüfung](CONNECTED_ROUTING_REVIEW.md).


## Aktuelle verbindliche Gesamtabnahme: Runtime-Isolation

Die vorherigen Hinweise auf ausschliesslich gezielte Tests sind historische
Abnahmen. Fuer den Runtime-Umbau sind `python scripts/quality.py`, 100 % app-
Statement-Coverage und `npm run test:e2e` vor Commit/Push vorgeschrieben.
Keine abgesenkten Coverage-Schwellen, keine uebersprungenen Pflichtpruefungen.
Neue Gegentests, Browserisolation und reproduzierbare Leistungsmessung stehen
im [Runtime-Review](RUNTIME_ISOLATION_REVIEW.md). Der Browserserver startet seinen
Fixture-Worker als eigenen Prozess. Testprofile frueherer unabhaengiger Faelle
werden im Scheduler gefencet; mehrere Profile desselben Falls bleiben aktiv.
Provider werden gemockt, Playwright prueft Desktop, Mobil und Tablet. Das ist
keine echte iPad-Abnahme. Live-Reparaturen sind kein Teil der Testsuite.

## Gemeinsame Vorlagen und stabile Dreier-Auswahl

`test_market_stock.py` prüft drei sichtbare Angebote, zehn vorbereitete
Alternativen, 14 Modellkontexte, gespeicherte abweichende Kapazität, zwei
unabhängige Spieler, einmalige Verwendung, parallele Dispatches, finanziellen
Rollback und sofortiges Nachrücken. Abfahrt, Zeitablauf, Route-TTL, Providerfehler,
Lease-/Flottenänderungen und Katalogänderungen dürfen keinen Bestand löschen
oder ungeprüfte Angebote veröffentlichen. Teilweise Verbindungsvorbereitung
wird nach neuem Repository-Kontext aus dem gespeicherten Checkpoint fortgesetzt.
Aktive Transporte aktivieren Zielstadtbedarf unmittelbar ab Dispatch, ohne
vorzeitiges Settlement oder eine Bewegung des echten Fahrzeugs.
Zusätzliche Gegenproben sichern kontextdeterministische gewichtete Auswahl bei
vertauschter Eingabereihenfolge, reproduzierbare Konditionen bei neuen UUIDs,
Diversität bis zur strukturellen Erschöpfung, den sichtbaren Übergang von null
auf ein, zwei und drei Angebote sowie atomisches Checkpoint-Aufräumen.

Die globale Vorratsregression prüft die feste Reihenfolge aus Idle sichtbar,
Zielstadt sichtbar, Idle-Reserve, Zielstadt-Reserve und globalem Vorrat. Sie
sichert außerdem, dass `partial` einschließlich Backoff den globalen Lauf
sperrt, globale Vorbereitung keine künstliche Anfahrt erzeugt und Stadt,
Modell, Nutzlast sowie Transportklasse getrennt bleiben. Bulk-Readiness-Tests
prüfen set-basierte Relationen, Anker, Proofs und Payloads statt einer SQL-
Abfrage je Relation. Frontendtests verlangen einen gültigen Idle-Fahrzeugscope
und unterscheiden Angebote, laufende Vorbereitung, erschöpfte Coverage und
einen vollständig vorbereiteten Leermarkt. Die Browserregression hält den Markt
bei `partial` und prüft, dass jedes bereits veröffentlichte Teilergebnis sofort
als echte Auftragskarte erscheint.

Die Wartungsregression erzeugt ausschließlich ungenutzte exakte Duplikate,
prüft den schreibfreien Bericht, das private SHA-256-Archiv, transaktionalen
Rollback, Idempotenz sowie unveränderte Spieler-, Fahrzeug-, Transport- und
Verwendungsdaten. Ein Cleanup ist niemals Teil von Startup oder Tests gegen
Produktivdaten.

`test_market_stock_upgrade.py` prüft vollständigen Quellen-/Zielabgleich,
unveränderte Quelle/Historie, gültige Altangebote ohne Ablauf und Ausschluss
abgelaufener Angebote. Fehlende Guards, fremde Versionen, kollidierende Tabellen,
Abgleichabweichungen und Integritätsfehler verhindern eine Ausgabe. CLI-Tests
verlangen neue getrennte Backup-/Ausgabepfade und bestätigen rein lesenden Check.
Alle neuen konkreten Core-Callables sind dem Function-Manifest zugeordnet.

Frontend-Verhaltenstests prüfen die serverseitige Fahrzeugabfrage, Zusammenfassung
gleicher Reads und Ausschluss verspäteter Antworten nach Auswahlwechseln.
`deferred-map.test.mjs` prüft nachgeladene Renderer, überholte Darstellungszustände,
Abbruch, Fehler und verspätete Erstellung. Der Browsertest hält das Kartenmodul
zurück und bedient währenddessen Flotte und Suchfilter. Die Bildgegenprobe
prüft verzögerten Bezug sichtbarer Farbbilder, entfernte Observer-Einträge und
Freigabe aller Bildbindungen. Der Routengegenvergleich prüft Distanz, Dauer,
Provider und jedes Geometrie-Ende, ohne Validierung neuer Snapshots zu umgehen.
Die vollständige Browser- und Leistungsabnahme verwendet isolierte Datenbanken
und Fixture-Provider. Reproduzierbar: `python -m tests.runtime_benchmark
UPGRADED_COPY.db NEW_RESULTS_DIR`; keine parallelen Builds oder Gesamtsuiten.
Logs und Screenshots bleiben privat. Ein Browser-Plugin ist in dieser Sitzung
nicht verfügbar; deshalb wird das vorhandene Playwright-Testsystem verwendet.

Akzeptierte Leistungsabweichung vom 28.09.2026: Der Nutzer hat den einmaligen
prozesskalten Start mit fälligem Settlement bei 3,39 Sekunden akzeptiert.
Dieser Wert bleibt im Bericht sichtbar; das Werkzeug prüft weitere Spielerstarts
weiterhin gegen zwei Sekunden. p95 <= 250 ms, höchstens 250 KiB pro normalem
Runtime-/Verkehrspoll und keine wiederholten unveränderten Geometrien bleiben
verbindlich. Diese Ausnahme verändert weder funktionale Tests noch Coverage.
