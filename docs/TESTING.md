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
