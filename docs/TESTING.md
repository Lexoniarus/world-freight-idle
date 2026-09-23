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
