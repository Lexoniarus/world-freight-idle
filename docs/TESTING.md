# Teststrategie

## Mehrspieler-Quality-Gate

`./.venv/Scripts/python.exe scripts/quality.py` (Windows) oder `make quality` (Linux).
Installieren über `requirements-dev.txt` und `npm ci`. Node 24 für Build und Tests.

Ruff-Lint + Formatcheck, mypy für `app` und `main.py`,
pytest mit 100 % Statement-Coverage für `app`,
Function-Test-Manifest, Architekturtests, ESLint, Stylelint, Prettier,
JSDoc/checkJs, Node-/DOM-Verhaltenstests, Vite-Build und Python-Kompilierung.

Neue Verhaltenstests prüfen gesalzene Passworthashes, Sitzungslaufzeit und
Widerruf, case-insensitive Namen, CSRF, Login-Limit, Spielertrennung,
Besitzprüfung über die HTTP-API, persistente Käufe, Parallelverhalten
bei Käufen und Ankunft, Dispatch-Rennen nach dem Provider-Await,
mehrere Transporte, abgelaufene Aufträge und Offline-Ranking.

Provider-Unit-Tests verwenden kontrollierte HTTP-Antworten. Sie belegen keine
Verfügbarkeit öffentlicher Dienste. Browser-Smoke-Tests verwenden eine
separate Datenbank (`DB_PATH=artifacts/playtest.db`) und bei Bedarf
`GAME_TIME_SCALE=3600`.

Coverage ist Statement-Coverage, kein Beweis vollständiger Sicherheit.
Starlette/httpx melden aktuell zwei Deprecation-Warnungen im Testlauf.

## Grundregel

**Keine konkrete Python-Core-Funktion ohne expliziten Gegentest.**

`tests/test_function_contract.py` scannt den gesamten `app/`-Baum per AST. Jede konkrete Funktion/Methode muss in `tests/function_test_manifest.py` einem existierenden Test zugeordnet sein. Neue Funktion ohne Test lässt den Build fehlschlagen.

## Ebenen

1. Domain-/Unit-Tests
2. Service-/Use-Case-Tests
3. Repository-Tests
4. Provider-Contract-Tests mit `httpx.MockTransport`
5. API-v1-Tests über FastAPI `TestClient`
6. Produktseiten-Routing-Tests
7. Frontend-Tests für API-Client, DOM-Views, Zustand, Controller und Kartenprojektionen

## Quality Gate

```bash
make quality
```

führt dieselbe Befehlsliste wie `python scripts/quality.py` aus.
Frontend separat: `npm run quality:frontend`. Das gemeinsame Gate ist
plattformübergreifend und bricht beim ersten Fehler ab.

Provider-Netzverfügbarkeit ist kein Unit-Test. Provider-Adapter werden deterministisch gegen simulierte HTTP-Antworten getestet; ein separater Smoke-Test kann in einer Umgebung mit Internetzugang laufen.

## UI-First-Abnahme

Voraussetzung: Node 24, npm ci und npm run build. Anschließend:

- npm run test:frontend: API-Adapter, Formatierung, Weginterpolation,
  Datumsgrenzen, Providerwechsel, Dispatch-Voraussetzungen, Zeitoffset,
  Abfragekoordination, veraltete Antworten und sicheres Text-Rendering.
- npm run test:e2e: fünf Playwright-Szenarien mit echtem FastAPI-/SQLite-Kern
  auf http://127.0.0.1:8011, eigener temporärer Datenbank und simulierten
  Geocoding-/Routing-Providern. Öffentliche Tiles werden vollständig durch
  lokale PNGs ersetzt. Screenshots/Testartefakte liegen im System-Tempordner.
- Standardszenarien: Registrierung, Quote, Dispatch, Kauf, Auszahlung,
  erneute Anmeldung, parallele Transporte, Deep Links, Kartenzoom, Layer,
  erhaltene Karteninstanz, verspätete Antworten, Sessionablauf und Ausfälle.
- Viewports: Desktop 1440 × 900, mobil 390 × 844; Tastaturfokus,
  Escape, Panelhöhen, Attribution und Reduced Motion werden geprüft.

Für diese Refactoring-Abnahme wird der Skill `game-studio:game-playtest`
mit dem vorhandenen Playwright-Setup verwendet. Screenshots werden zusätzlich
visuell geprüft, weil DOM-Assertions die WebGL-Darstellung nicht abdecken.

Browserkonfiguration: PLAYWRIGHT_CHANNEL=chromium für installierte
Playwright-Browser; PYTHON_EXECUTABLE überschreibt den Python-Pfad.
CI installiert Chromium und verwendet den System-Python. Ein entfernter
CI-Lauf und der Docker-Build wurden lokal nicht ausgeführt.

Testgrenzen: Keine Zusage für andere Browser, reale Mobilgeräte, größere
Produktionslast oder die dauerhafte Verfügbarkeit öffentlicher Provider.
World-Wrapping/Datumsgrenzen werden zusätzlich durch Geometrie-Tests geprüft.

Begrenzte Live-Prüfung am 18.09.2026: isolierter Server auf Port 8012 mit
separater temporärer Datenbank, echter OSM-Basiskarte sowie Nominatim und
Valhalla. Berlin und die Route Berlin–Hamburg wurden im In-App-Browser
sichtbar geprüft: 316,1 km, 3 h 42 min, vollständige Kalkulation.
Die Browserkonsole meldete dabei keine Fehler oder Warnungen.
Dieser Einzelcheck ist keine Verfügbarkeitsgarantie für externe Provider.

## Refactoring-Regressionsschutz

Die Node-Tests unter `frontend/` verwenden jsdom für reale DOM-Knoten.
Sie prüfen sichere Text-/Attributbindung, Fokus und Auswahl bei Refresh,
veraltete Quotes und Panelantworten, Disposal trotz ignoriertem AbortSignal,
Schreibfehler mit nachfolgender Synchronisierung statt Wiederholung,
Timer/Listener-Freigabe, reduzierte Animation und GeoJSON-Projektionen.

AST-Architekturtests verbieten alte Static-Imports und Zugriffe von Views
auf API/Controller/State sowie von Kartenmodulen auf API/Views. Python-Tests
prüfen Domain-/Service-/API-Importgrenzen und Service-Erzeugung außerhalb
von Endpoints. Eine feste Zuordnung pro Funktion wird weiterhin im Python-
Core erzwungen; Frontend-Verhalten wird über Unit-/DOM- und Browserfälle
abgedeckt. Das ist keine Behauptung von 100 % JavaScript-Coverage.

## Regressionen: Stabilisierung und Fahrzeugkatalog

Der rekursive Manifest-Scanner erfasst auch explizite Konstruktoren und
verschachtelte benannte Funktionen. Nur reine Protokolldeklarationen werden
strukturell ausgenommen; generierte Methoden und anonyme Lambdas erhalten
keine eigene Manifest-ID. Konstruktor-Verhalten wird über passende
Initialisierungs-, Isolations-, Lebenszyklus- und Anwendungstests geprüft.
Frontend-Importtests lösen Modulpfade auf und prüfen Re-Exports sowie statisch
bestimmbare dynamische Imports; Negativfälle belegen die Controller-Grenze.

Katalogtests verwenden temporäre Referenzkopien und Spielstände. Sie prüfen
alle acht Angebote, fehlende/beschädigte Daten, Fremdschlüssel, Reputationsgrenzen,
Transaktions-Rollback, Kauf-Snapshots, individuelle Kosten und Altbestand.
Regressionsfälle decken ungültige Providerwerte und Cache-Reparatur, verlorene
Schreibantworten während eines laufenden Polls, Fahrzeugwechsel während Quotes
und Kameraführung über Weltkopien ab. Aktuelle Prüfzahlen: QUALITY_REPORT.md.


## Ergänzung: Medien, Startfahrzeug und WLAN (18.09.2026)

Die Regression prüft verifizierte Bildauswahl, Quellen-/Lizenzwerte, ungültige
Links, reine Textausgabe und entfernte Load/Error-Listener. Browserbilder werden
wie Tiles durch lokale Testdaten ersetzt; ein zweiter isolierter Browserkontext
simuliert Fotoausfall und prüft getrennte Flotten, Guthaben und Besitzgrenzen.
Neue Startflotten werden gegen die DB-Spielwerte geprüft, einschließlich
Snapshot-Erhalt und atomarem Abbruch/Wiederholung bei Katalogausfall.
Testprofilpflege prüft Fahrzeug-IDs, unveränderte Transport-Snapshots, fremde
Spielstände, Backup und Guthabenerhalt ohne explizites --cash.

Der Nutzer hat die reale iPad-Anmeldeseite über die LAN-IP bestätigt. Das ist
noch keine vollständige Safari-/iPad-Spielabnahme. Tatsächlich ausgeführte
Werkzeuge und die begrenzte reale Fotoprüfung: QUALITY_REPORT.md.

Ein DOM-Regressionstest prüft die Identität geladener/fehlgeschlagener Fotos
bei unverändertem und geändertem Panelinhalt. Der Browsertest prüft dieselbe
Bildinstanz über einen automatischen Poll und einen Transportstatuswechsel.


## Reparaturabnahme: Initialisierung, Cleanup und Profilpflege

Neue Fehlerfalltests rufen die Initialisierung direkt ohne äußere Transaktion
auf. Sie prüfen Katalog-, Markt- und Schreibfehler, vorhandene Teilstände,
Idempotenz und Reset-Rollback. Lifespan-Tests prüfen beide Client-Konstruktoren,
Spiel-/Account-/Auth-Aufbau, normale Beendigung, Fehler im aktiven Scope und
Fehler beim Schließen jedes Clients.

Profiltests verwenden ausschließlich temporäre Datenbanken: unbekannte IDs,
leere Zuordnungen, negative/nicht ganzzahlige Guthaben, unzureichende Nutzlast,
Rollback nach Schreibfehler, explizite Geldsetzung und Guthabenerhalt. Fremde
Profile, nicht ausgewählte Fahrzeuge, Status und Transport-Snapshots bleiben
unverändert. Das Backup wird mit offener WAL-Verbindung gelesen; uncommitted
Daten werden ausgeschlossen, bestehende Backups nicht überschrieben. CLI-Tests
sichern Argumentfehler, doppelte Zuordnungen und Abbruch vor Serviceaufbau bei
Backupfehlern ab. Architekturtests sichern die CLI-/SQL-Grenzen der Pflege.

Eine zusätzliche Nebenläufigkeitsregression pausiert Routing, ändert über die
Profilpflege das Fahrzeug und setzt Routing fort. Der Start muss den aktuellen
Kostensatz verwenden oder bei anschließend zu geringem Guthaben ohne Abbuchung
abbrechen. Neue Core-Funktionen sind im Manifest und Coverage-Gate enthalten.
Aktuelle Zahlen und tatsächlich ausgeführte Browserprüfung: QUALITY_REPORT.md.
