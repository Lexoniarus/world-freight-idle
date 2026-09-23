# Qualitätsbericht: Domain-/Persistenz-Refactor

Stand: 23.09.2026. Geprüfter Code: c6bf759; die anschließende Konsolidierung
ändert ausschließlich Dokumentation. Umgebung: Windows, Python 3.11.9,
Node 24, Microsoft Edge. Dieser Bericht ersetzt frühere Werkzeugzählungen.

## Ausgeführte Werkzeugprüfungen

| Prüfung | Tatsächliches Ergebnis |
| --- | --- |
| `python scripts/quality.py` | Vollständig bestanden, Exit 0 |
| Ruff / Format | Bestanden, 127 Dateien |
| mypy einschließlich aller drei Pflege-/Import-CLIs | 84 Quelldateien, keine Fehler |
| Pyright, dokumentierter Standardmodus | 0 Fehler, 0 Warnungen |
| Python-Verhalten, API, Architektur, Function-Test-Manifest | 252 Tests bestanden |
| Python-Core-Statement-Coverage | 100 %, 2.990 Statements, 0 fehlend |
| ESLint, Stylelint, Prettier, checkJs | Bestanden |
| Frontend-Verhalten und Architektur | 54 Tests bestanden |
| Vite-Produktionsbuild / compileall | Bestanden |
| `npm run test:e2e` | Alle 10 Szenarien bestanden, Edge, 1,9 Minuten |
| `python main.py`, aktivierte relationale DB | Start erfolgreich, Login/Health HTTP 200, Port 8000 |
| Aktive DB: integrity_check / foreign_key_check | ok / keine Fehler |
| Interne Dokumentationslinks / Git-Diff-Whitespace | Keine offenen Fehler |

Lokale Nachweise: artifacts/domain-final-quality.log und artifacts/domain-e2e.log.
Zwei Deprecation-Warnungen stammen aus dem Starlette/httpx-/AnyIO-Testclient;
sie wurden nicht unterdrückt. Die Coverage-Aussage gilt für Statements,
nicht für vollständige Pfad- oder Branch-Coverage.

## Manuelles Architektur- und Cleanup-Review

Geprüft wurden Zuständigkeiten und Aufrufer in Domain, Services, Repositories,
Composition Roots und API sowie die aktiven Frontend-Grenzen für State, Aktionen,
Views, Marktanfragen, Karte, Animation und Bildknoten.

- Eine relationale Laufzeit: keine KV-Kompatibilität, keine Runtime-Hydrierung
  alter Spielstände. SQL und Speicher-Mapping liegen in Repositories.
- Entities besitzen fachliche Invarianten und benannte Zustandswechsel.
  GameService erhält seine Zeitquelle injiziert; reine Preisberechnung hat
  keine Service- oder Speicherabhängigkeit.
- BEGIN IMMEDIATE schützt Kauf, Disposition und Settlement. Routing bleibt
  außerhalb der Transaktion; veränderliche Voraussetzungen werden danach
  geprüft. Auszahlungen werden vor nachfolgender Markterzeugung committet.
- Historische Aufträge, Standorte, Quellen, Waren und Routen bleiben erhalten.
  Relationale Ports trennen Accounts, Cache, Rangliste und Verkehr.
- Unveränderliche World-Scopes filtern normalisierte Geografie. Companies
  bleiben unabhängig von einer Stadt; Mehrdeutigkeiten werden abgewiesen.
- Öffentliche Standort-/Spiel-/Traffic-Projektionen liegen im API-Bereich.
  Der zuletzt gefundene JSON-/Zeitdurchgriff des Mehrspieler-Services wurde
  beseitigt; der überflüssige Service ist entfernt.
- AsyncExitStack und Repository-Kontexte besitzen Ressourcen. Browsercontroller
  beenden Requests/Timer/Listener; überholte Antworten werden verworfen.
  Views erzeugen sichere DOM-Texte; unveränderte Bilder behalten ihre DOM-Knoten.
- Alte Modelle, Stores, Migrationspfade, verwaiste Manifest-Einträge und eigene
  temporäre Umbau-Skripte sind entfernt. Docker schließt auch Backups außerhalb
  von data aus; nur die zwei Referenzkataloge sind gezielte Ausnahmen.

Für den vereinbarten Refactor bestehen nach diesem Review keine offenen
wesentlichen Architektur-Befunde. Dies ist ein inhaltliches Review des
implementierenden Agenten, keine unabhängige externe Freigabe. Grüne Linter
allein waren ausdrücklich nicht das Abnahmekriterium.

## Datenübernahme und Referenzkatalog

Nach SQLite-Backup und ohne laufenden Spielserver wurden drei Konten,
21 Fahrzeuge und 21 Transporte in eine neue relationale Datei übernommen.
Ein unabhängiger feldweiser Vergleich bestätigte Konten-IDs, Namen,
Passwort-Hashes, Geld-/Fortschrittswerte, Fahrzeugdaten und historische
Transportendpunkte, Geometrien, Zeiten, Kosten und Auszahlungen.

25 abgelaufene Angebote wurden im privaten Importbericht ausgeschlossen.
Der zusätzliche kontolose Demostand bleibt auf ausdrücklichen Nutzerentscheid
nur im Backup. Sessions und wiederherstellbare Caches wurden nicht importiert.
Die Originaldateien und das SQLite-Backup bleiben lokal erhalten, außerhalb
von Git und Docker-Build-Kontext.

Auf einer Wegwerfkopie wurden alle 21 fälligen Transporte ohne Routing genau
einmal abgerechnet; ein zweiter Zugriff zahlte nichts erneut aus. Die aktivierte
game.db enthielt bei der abschließenden Leseprüfung alle 21 noch als active.
Ihre Abrechnung erfolgt beim nächsten normalen Spielerzugriff.

WorldCatalogue 4.0.0 wurde in einer neuen Datei nach Backup normalisiert:
109 Companies, 352 Facilities, 25 Länder, 304 dauerhaft gespeicherte Stadt-UUIDs.
Bestehende Company-/Facility-Identitäten, Koordinaten und Provenienz wurden
bewahrt. 79 Standorte sind verifiziert, 273 ausdrücklich für Simulation geschätzt.
Der Fahrzeugkatalog bleibt bei seinen vorhandenen 14 Modellen.

## Browserprüfung und Grenzen

Die zehn Szenarien prüfen Registrierung/Anmeldung, Kauf, fahrzeugbezogene
Quote/Disposition, parallele Transporte, Offline-Ankunft, Rangliste und
Mehrspielerkarte, zwei getrennte Profile, Deep Links, verzögerte Antworten,
Sessionablauf, Katalog-/Tilefehler, Fokus, mobile Panels und stabile Bilder.
Desktop 1440 × 900 und Mobil 390 × 844 einschließlich Reduced Motion wurden
getestet. Repräsentative Screenshots von Karte, Disposition, Flotte und Shop
wurden visuell geprüft; keine neue Layoutregression festgestellt.

Die Automation nutzt eine separate temporäre DB, Mock-Routing und lokale Tiles.
Sie beweist keine aktuelle Verfügbarkeit öffentlicher Kartendienste. Eine reale
iPad-Abnahme wurde in diesem Lauf nicht durchgeführt. Die Passwörter der drei
übernommenen Konten waren nicht bekannt: Ihre Hashes wurden unverändert
verglichen, tatsächliche erneute Passworteingabe bleibt beim Nutzer.
Wiederanmeldung und Hash-Verifikation wurden mit bekannten Testkonten geprüft.
Ein Docker-Build wurde mangels lokalem Docker nicht ausgeführt; Dockerfile,
Compose, Katalogauslieferung und Ausschlussmuster wurden geprüft.

## Integration

Kleine Arbeitscommits liegen auf refactor/game-state-persistence. Integration
bleibt an grüne GitHub-CI und den geprüften Squash-PR gebunden. Dessen Checks
und Merge-Status sind der maßgebliche Remote-Nachweis, keine vorweggenommene
Behauptung in diesem Bericht. Es gibt keine direkten main-Commits.

GitHub meldet das Repository inzwischen öffentlich. Diese Arbeit änderte seine
Sichtbarkeit nicht. Serverseitiger Branchschutz ist weiterhin nicht eingerichtet;
Hooks, CI und der eingehaltene PR-Ablauf ersetzen keine Zugriffsbeschränkung.
Der technische Refactor ist keine vollständige MVP- oder Produktionsfreigabe.
