# Qualitätsbericht: Global Routing Readiness

Stand: 27.09.2026. **Implementiert und lokal vollständig geprüft.**
Die lokale Gesamtabnahme ist bestanden. Der Branch-Push ist nachträglich
ausdrücklich freigegeben; PR und Merge bleiben ausgeschlossen. Die weiter
unten stehenden älteren Prüfergebnisse gelten nur für ihren damaligen Stand.

- Current branch head used: `feature/frontend-v2`.
- Base commit: `df40e7c800d21ac4187912fc9a81a6e08e1349bb`.
- Lokaler und Remote-HEAD für den Ausgangsstand erneut identisch geprüft.
- Bewusste nutzerautorisierte Ausnahme vom normalen Branchingprozess: bestehender
  Featurebranch verwendet. Kein Wechsel, Rebase oder Reset. Abschlussform:
  Commit und ausdrücklich freigegebener Branch-Push nach erfolgreicher
  Gesamtabnahme; kein PR oder Merge.
- Hooks bleiben `.githooks`. Referenzkataloge, Spielerbestände und historische
  Snapshots werden nicht verändert oder versioniert.

Changed files: 72 Source-, Test- und Dokumentationsdateien im lokalen Commit;
die folgenden Abschnitte ordnen die Änderungen fachlich zu. Das zuvor erzeugte
ZIP-Archiv und seine Prüfsummendatei wurden entfernt; es gibt kein Drop-in-Paket.

## Geänderte Bereiche und Ergebnis

### A. Routing diagnostics

Globale gerichtete Relationen besitzen ready/deterministic_failure/
transient_failure/stale-Projektionen. RoutingAttempt ist append-only und enthält
Methode, Kandidat, Providerdiagnostik, Zeit und Trace. Verworfene Zwischenversuche
bleiben nachvollziehbar. Verlorene Leases verhindern Publikation.

### B. Anchor repair

Facility → Adresse → höchstens fünf eindeutige reale Locate-Zugänge; finale
Truckvalidierung und Snapgrenze bleiben verbindlich. Globale Anchor-Leases
verhindern parallele Reparaturen desselben Endpunkts. Adress-/Koordinatenänderung
invalidiert den Source-Fingerprint. Providerunverfügbarkeit verschiebt Retries.

### C. OSM fallback

Nur tatsächliche Truck-kompatible korrelierte Locate-Metadaten werden als
Kandidaten verwendet. Keine erfundenen Zugänge, keine Luftlinienroute und kein
Verschieben zur Umgehung von no_path oder distance_limit. Unklarer Endpoint wird
höchstens einmal an beiden Enden erneut validiert.

### D. Routing relation repository

Zusätzliche Infrastruktur-Tabellen in derselben SqliteGameDatabase; Geometry
bleibt im route_cache. Separate OfferRouteReferences mit FK-Cascade. Game-Schema
1.1.0, Offer-Dokumentversion 1 und Transport-Dokumentversion 2 unverändert.
Referenz und Offer werden innerhalb derselben Markt-UoW gespeichert/entfernt.

### E. Route readiness

Aktuelle Fingerprints umfassen Provideridentität, tatsächlich beobachtete
Revision und Facility-/Anchorfakten. Beschädigte/fehlende Payloads sind nicht
ready. Globale Relations-Leases besitzen Ablauf, Erneuerung und Eigentümerfence.
Concurrent Player-Nachfrage teilt dieselbe globale Evidenz. Marktpublikation
enthält ausschließlich Delivery-ready Offers; eligible_vehicle_ids verlangt
zusätzlich vorbereitete Anfahrten. Auch ausschließlich veraltete Approaches
lösen neue Preparation aus. Partial bedeutet fehlende Coverage.

### F. Prewarm / audit

CLI `scripts/audit_routing_readiness.py`: lokales --report, explizites --prewarm,
Defaultbudget 100 tatsächliche Providerrequests einschließlich Locate/Geocoding,
Resume über persistierte Evidenz und gesonderte Freigabe des öffentlichen
Default-Endpunkts. Kein Live-Prewarm ausgeführt.

Tatsächlich ausgeführter lokaler Wolfsburg-Lauf mit temporärer isolierter
Audit-Datenbank und unverändertem Referenzkatalog:
`python scripts/audit_routing_readiness.py --report --city Wolfsburg`.
Ergebnis: 559 Katalogfacilities mit Koordinaten, 602 relevante gerichtete
Relationen für diesen Fokus, 602 unchecked, **0 Providerrequests**. Es gibt in
dieser frischen Audit-Datenbank keine Versuchshistorie. Daraus folgt ausdrücklich
keine Aussage, dass alle Facilities truckfähig oder alle Relationen routbar sind.
Die CLI kann dieselben Berichte mit vorhandener persistierter Evidenz erzeugen;
Wolfsburg erhält keine Sonderregel.

### G. Market integration

Candidate-Erzeugung bleibt routerfrei. Preparation ist ein eigener Baustein vor
Coverage/Materialisierung. Startup validiert Kataloge und ersetzt offene Märkte
aller Profile atomar aus bestehender Readiness; kein Provider-Bulk beim Start.
Lifespan besitzt Worker, Tasks und Cleanup. Fairer persistierter Spielerbedarf,
begrenzte Batches und neue Execution-Traces; HTTP-Requestkontext wird nicht geerbt.
Fehlgeschlagene Kandidaten werden übersprungen, erschöpfter Pool separat gemeldet.

### H. Dispatch / Journey

Produktions-Quote lädt vorbereitete Delivery-/Approach-Payloads. Kein ungeprüfter
Providerfallback. Revalidierung vor Commit, A → B → C, Fahrzeuggeschwindigkeit,
Energie, Kosten, Tarife, historische Konditionen und separater Refill bleiben
bestehen. Globale Providerzeit ist keine finale Spielerfahrzeit.

### I. Frontend

Preparationstatus wird gemeinsam mit Offers projiziert. Bestehende Controller
besitzen Polling, Abort und stale-response-Schutz; Views zeigen verständliche
partial/exhausted-Zustände. Browserfixtures verwenden serverseitige Eignung und
explizite Fahrzeugwahl; Fahrzeugwechsel wählt ein für beide geeignetes Angebot.
Keine obsolete globale Stadtauswahl ergänzt.

### J. Documentation

PRODUCT (MVP, Truck-Anker, Markt, Quote/Dispatch), ARCHITECTURE, DOMAIN_MODEL,
API, API_PROVIDERS, DATA_SOURCES, RELATIONAL_STATE, OBSERVABILITY, TESTING,
TARGET und MILESTONES abgeglichen. Neue Einzelreviewliste:
[ROUTING_READINESS_REVIEW.md](docs/ROUTING_READINESS_REVIEW.md).
117 neue/geänderte Core-Callables einschließlich abstrakter Ports einzeln
abgeglichen; Frontendfunktionen separat geprüft. Der neue Audit-Einstiegspunkt
ist zusätzlich in den Ruff-/Format-/mypy-Dateilisten des Quality-Gates enthalten.

## Direkter Branchabschluss: vollständige Gates

Der erste vollständige Lauf ergab 482 bestandene und 11 fehlgeschlagene Tests.
Die Fehler betrafen die neue Preparationstatus-API, unzulässige RouteReference-
Felder in historischen Projektionen sowie bisher sofort erzeugte Testangebote.
Korrigiert wurden die Projektionsgrenze und die betroffenen Testaufbauten;
keine bestehenden Vertragsprüfungen wurden abgeschwächt.

76 gezielte Nachprüfungen in test_api, test_game_import, test_nested_import,
test_multiplayer, test_multiplayer_map, test_vehicle_catalogue und
test_market_preparation bestanden. Ergänzte Gegenchecks prüfen insbesondere
veraltete Delivery-/Approach-Routen und fehlende Referenzen. Die kombinierte
Coverage dieser Diagnosephase beträgt 5413/5413 Statements; der abschließende
vollständige Quality-Lauf prüft dies erneut ohne Coverage-Append.

Der erste vollständige Playwright-Lauf bestand 29/30 Fälle. Der letzte
Registrierungsversuch wurde durch das unveränderte IP-Limit blockiert, weil
alle Testfälle denselben lokalen Client teilten. Der Testaufbau isoliert nun
Auth-Clientadressen pro Fall hinter dem lokalen Testproxy. Der betreffende
Weltkarten-/Stadtmarktfall bestand danach einzeln (1 Test, 11,9 s).
Produktionslimit und API-Throttle-Tests wurden nicht geändert.
Nach dieser Korrektur wurden Quality und E2E erneut vollständig ausgeführt.

| Abschließender Befehl | Tatsächliches Ergebnis |
| --- | --- |
| `.venv/Scripts/python.exe -X utf8 scripts/quality.py` | bestanden; 495 Python-Tests, 5413/5413 Statements = 100 %, 101 Frontendtests; Ruff/Format/mypy/Pyright/ESLint/Stylelint/Prettier/checkJs/Build/compileall bestanden |
| `npm run test:e2e` | 30/30 bestanden, 8,9 Minuten; Build davor vollständig abgeschlossen |
| `git diff --check` | bestanden; keine Whitespacefehler |

Der abschließende Python-Lauf dauerte 601,94 Sekunden. Zwei vorhandene
TestClient-/anyio-DeprecationWarnings sind protokolliert; keine Testfehler.
Lokale Logs: `artifacts/routing-full-quality-accepted.log`,
`artifacts/routing-full-e2e-accepted.log`, `artifacts/routing-diff-check.log`.
Diese bleiben unversioniert. Frühere Diagnose- und Fehlversuche werden durch
diese vollständigen, sauberen Abschlussläufe nicht als erfolgreich umgedeutet.

## Tatsächlich ausgeführte gezielte Prüfungen

Kein Testumfang oder Coverage-Schwellwert wurde abgeschwächt. Zwischenläufe
zeigten fehlende Gegenproben, alte Workerfixtures, einen Importformatfehler und
Browserannahmen zur asynchronen Eignung. Diese wurden korrigiert; nachfolgend
stehen die abschließenden Ergebnisse, nicht die Fehlversuche als Abnahme.

### Einheiten 1–5: Domain, Repository, Provider, Readiness, Worker und Markt

```text
.venv/Scripts/python.exe -m pytest
  tests/test_market_preparation.py
  tests/test_routing_readiness_store.py
  tests/test_request_limiter.py
  tests/test_routing_audit.py
  tests/test_routing_audit_cli.py
  tests/test_anchor_repair_history.py
  tests/test_routing_anchors.py
  tests/test_routing_anchor_provider.py
  tests/test_routing_anchor_repository.py
  tests/test_function_contract.py -q
  --cov=app.domain.routing_readiness
  --cov=app.domain.market_preparation
  --cov=app.domain.readiness_ports
  --cov=app.providers.request_limiter
  --cov=app.providers.valhalla_metadata
  --cov=app.repositories.routing_readiness
  --cov=app.repositories.market_preparation
  --cov=app.repositories.routing_audit
  --cov=app.repositories.routing_anchors
  --cov=app.services.routing_inventory
  --cov=app.services.routing_readiness
  --cov=app.services.market_preparation
  --cov=app.services.preparation_worker
  --cov=app.services.routing_anchors
  --cov=app.providers.routing_anchor
  --cov-report=term-missing --cov-fail-under=100
```

Ergebnis: **56 Tests bestanden; 755/755 Statements (100 %)**. Dies ist die Coverage der ausdrücklich
benannten 15 Routingmodule, keine behauptete vollständige Core-Coverage.
Die Manifestprüfung wurde im selben Lauf ausgeführt.

### Einheiten 5–6: bestehende Markt-/Dispatch-/Economyverträge

```text
.venv/Scripts/python.exe -m pytest
  tests/test_routing.py tests/test_routing_api.py tests/test_geocoding.py
  tests/test_routing_anchor_provider.py tests/test_routing_anchor_repository.py
  tests/test_dispatch_routing_anchors.py tests/test_dispatch_approach.py
  tests/test_market.py tests/test_market_lifecycle.py tests/test_economy_v2.py
  tests/test_initialization_lifecycle.py tests/test_architecture.py
  tests/test_function_contract.py tests/test_routing_audit_cli.py -q --no-cov
```

Ergebnis: **117 Tests bestanden**. Startup-/Shutdown-Fehler,
Dispatch-Rollback/Refill, historische Verträge und bestehende Wirtschaftsformeln
sind in den betroffenen Dateien enthalten. Kein neuer Wirtschaftsaudit mit
Balanceänderungen, da diese nicht zum Routing-Umbau gehören.

### Gezielte statische Prüfungen

- `python -m ruff check <46 geänderte Python-Dateien>`: bestanden.
- `python -m ruff format --check <dieselben Dateien>`: 46 formatiert.
- `python -m mypy <34 geänderte Core-/CLI-Dateien>`: keine Fehler.
- `node node_modules/pyright/index.js <46 geänderte Python-Dateien>`:
  0 Fehler, 0 Warnungen.
- Nach der Approach-Generation-Korrektur: Ruff und mypy auf dem betroffenen
  Service, Pyright auf Service/Testdatei erneut bestanden.
- Gezielte ESLint-/Prettier-Prüfung der geänderten Frontenddateien und
  `npm run typecheck`: bestanden.

### Einheit 7: Frontend und ausgewählte Browserfälle

```text
node --test --test-name-pattern
  'partial and exhausted|list and detail reads|offer filters'
  frontend/frontend-v2.test.mjs
npm run build
npx playwright test tests/browser/game.spec.js --grep
  'desktop: registration, map, quote|DB vehicle selection changes costs|company livery persists across map'
```

Ergebnis: **3 Node-Tests**, Vite-Build und **4 benannte Playwright-Fälle**
bestanden. Nach dem finalen Frontend-Build zusätzlich:

```text
npx playwright test tests/browser/game.spec.js --grep
  'company livery persists across map'
```

**2 Desktop-/Mobilfälle bestanden (31,2 s)**. Build und Browserläufe liefen
nacheinander. Die abschließende Approach-Generation-Korrektur ist separat durch
Backendregressionen geprüft; die Browserfälle wurden danach nicht wiederholt.

### Tatsächlich betrachtete Screenshots

- `world-freight-livery-desktop.png`: zehn beschriftete Farbswatches, Auswahl
  sichtbar, übereinstimmende Front-/Seiten-/Top-Down-Lackierung, lesbare Panels.
- `world-freight-livery-mobile.png`: Palette umgebrochen und bedienbar,
  Front-/Seitenvorschau konsistent. Untere Top-Down-Vorschau außerhalb dieses
  Ausschnitts; dafür kein weitergehender visueller Nachweis behauptet.
- `world-freight-dispatch.png`: explizite Fahrzeugwahl, Startaktion aktiv,
  400 km Anfahrt + 400 km Lieferung = 800 km. Das ist eine Mockroute.

Im vollständigen Browserlauf zusätzlich tatsächlich geöffnet und angesehen:
`artifacts/assets-current/fleet-desktop.png`, `shop-mobile.png` sowie die
Temp-Screenshots `world-freight-energy-mobile.png`,
`world-freight-approach-desktop.png`, `world-freight-costs-purchases-mobile.png`
und `world-freight-vehicle-city-market.png`. Befunde: konsistente Assets und
Lackierung, lesbare mobile Panels, sichtbare Ladephase, tatsächlicher Start vor
Abholung, nachvollziehbare Kostenkomponenten (80 + 62 + 243 = 385 Euro),
fahrzeugbezogener Stadtmarkt mit sichtbarer Ungeeignet-Kennzeichnung.

Die Bilder wurden geöffnet und angesehen. Grid-Tiles und gerade Mockgeometrie
belegen UI-Verhalten, keine reale Provider-/Wolfsburg-Routbarkeit. Screenshots,
Logs und isolierte Audit-Datenbanken sind unversionierte Prüfartefakte.

## Lokale Gesamtabnahme und verbleibende Betriebsprüfungen

**Full quality suite:**
PASSED – vollständig ausgeführt

**Full Playwright suite:**
PASSED – vollständig ausgeführt

`git diff --check` wurde nach den vollständigen Gates ausgeführt und bestanden.
Der lokale Stand ist vollständig geprüft; reale Providerprüfungen bleiben
als getrennte Betriebsprüfung offen.

Known limitations:

- Reale Valhalla-/Nominatim-Antworten wurden automatisiert gemockt. Es wurde kein
  globaler öffentlicher Prewarm und keine tatsächliche Wolfsburg-Routenprüfung
  ausgeführt.
- Graphwechsel werden nur anhand tatsächlich gelieferter bekannter Header
  erkannt. Ohne Providerrevision gibt es keine erfundene Invalidierung; ein
  unangekündigter Graphwechsel ist dann nicht automatisch sichtbar.
- Provider-Limiter gelten pro Runtimeinstanz. Mehrere OS-Prozesse benötigen
  gemeinsame externe Drosselung oder eigenen Dienst. Globale SQLite-Leases
  deduplizieren Relationen pro Datenbank, nicht die gesamte Provider-Rate.
- Die aktuelle lokale Audit-Datenbank enthält keine bestehenden
  Providerfehlerhistorien; der Bericht kennzeichnet ungeprüfte Relationen.

Manual real-provider checks still recommended:

1. Eigenen Valhalla-Endpunkt konfigurieren, begrenzten Wolfsburg-Prewarm ausführen
   und mit --report Endpointmethoden, Versuche und gerichtete Ergebnisse prüfen.
2. Reale no_path-, distance_limit-, 429/Retry-After- und unavailable-Fälle prüfen;
   keine Reparatur bei deterministischem No-path oder Providerstörung erwarten.
3. Restart während Vorbereitung, anschließende Recovery und bereits fertige
   Angebote mit tatsächlich bekannten Graphrevisionen prüfen.
4. Produktionsbetrieb zusätzlich mit der eigenen Providerinstanz beobachten.

Source, Tests und Dokumentation werden direkt auf `feature/frontend-v2`
committed. `static/dist` bleibt lokaler generierter Build-Output. Keine
Spieler-Datenbanken, Secrets oder Testartefakte werden gestagt.

**Branch push explicitly authorized. No PR. No merge.**

---

# Historischer Qualitätsbericht (unverändert, frühere Implementierung)

# Qualitätsbericht: Frontend-v2 und Wirtschaft

Stand: 25.09.2026, geprüfte Implementierung `05b4f08` auf dem lokalen Branch
`feature/frontend-v2`. Ausgangsbasis
`548336f` einschließlich aller drei Anfahrtscommits blieb erhalten. Die
vorhandene Abholdokumentation wurde separat als `742e14b` gesichert.
Hooks sind aktiv. Keine Veröffentlichung, kein PR, kein Merge.

## Implementiertes Ergebnis

- Beta(3,1)-Beladung innerhalb unveränderter NHM-/Distanzgrenzen; unabhängige
  gewichtete Auswahl des Generierungsfahrzeugs und keine exklusive Bindung.
- Direkter Katalog-Wartungssatz, 80 € Grundkosten und tatsächlich geplante
  Energieeinkäufe. Decimal/HALF_UP, exakte Addition gerundeter Komponenten.
- Immutable NHM-Mindesttarife, Kostensnapshots und transparente Quotes.
  Fahrzeugwechsel verändert weder Tonnage noch Angebotstarif.
- Global atomarer Startup-Rebuild für bestehende Profile und eigene idle-
  Städte; beide Referenzkataloge validiert/gecacht. Keine Routingaufrufe und
  keine historische Rekonstruktion. Fehler verhindert Serverfreigabe.
- Markt-Stadtauswahl ohne Ziele oder enroute-Checkpoints; ungültige Auswahl
  inklusive URL wird zurückgesetzt. Kein Marktrefresh bei Pan/Zoom.
- Persistente Account-Farben mit zehn validierten Werten und unverändertem
  Fallback; eigene/öffentliche Darstellung, Front/Seite/Map, Gruppenassets,
  selektive Facility-Unterdrückung und verständliche Analyticsnamen.
- A → B → C, kontinuierliche Energie, Standortcheckpoint, atomarer Dispatch
  und gesonderter post-commit Refill bleiben erhalten.

## Tatsächlich ausgeführte Prüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Erster vollständiger `python scripts/quality.py` | bestanden: 423 Python-Tests, 4384 Statements, 100 %, 87 Frontendtests; Ruff/Format/mypy/Pyright/ESLint/Stylelint/Prettier/checkJs/Build/compileall |
| Gezielte Cache-/Manifestprüfung nach letztem Planabgleich | 2 bestanden; fehlgeschlagener Read, Retry, parallele immutable Wiederverwendung |
| Abschließender vollständiger Quality-Gate mit Vehicle-Cache | bestanden: 424 Python-Tests, 4401 Statements, 100 % Coverage; 87 Frontendtests; sämtliche Format-/Typ-/Lint-/Build-Gates bestanden |
| Browserregression vor ergänzter Kostenvisualisierung | 22 bestanden, 7,2 Minuten |
| Abschließendes `npm run test:e2e` einschließlich Kostenvisualisierung | 24 bestanden, 8,8 Minuten |
| `python scripts/audit_economy.py` | 163.296 Zeilen, alle 14 Modelle, Seed 20260925; keine Spielerzugriffe |
| `git diff --cached --check` und Hooks | bestanden; keine Prüfartefakte oder Spieler-DBs gestagt |
| Referenz-/Assetintegrität | beide kanonischen DB-Blobs unverändert gegenüber 548336f; SVG-Inventarprüfungen bestanden |
| Einzelreview | 54 direkt geänderte konkrete Python-Callables plus 2 indirekt betroffene Katalogmapper, 5 abstrakte Portmethoden und 61 Browserfunktionen/-methoden einzeln geprüft |

Die finalen lokalen Logs heißen `artifacts-economy-quality-final.log`,
`artifacts-economy-e2e-final-verified.log`, `artifacts-economy-frontend-final.log`
und `artifacts-economy-audit.log`. Zwischenläufe waren keine Abnahme:
veraltete Aggregatkostenerwartungen und historische Importfixtures wurden
korrigiert. Browserregressionen fanden eine verlorene Dispatch-Navigation
bei Stadtparameterbereinigung und eine zu früh freigegebene Blob-URL.
Beide besitzen jetzt gezielte Gegentests. Der Map-Atlas verarbeitet bereits
kolorierte Quellen genau einmal. Ein weiterer Browser-Zwischenlauf wurde
nicht als Abnahme gewertet: Ein parallel gestarteter Vite-Neubuild entfernte
kurzzeitig `static/dist/index.html` und verursachte einen HTTP-500 beim
Anmeldeseitenaufruf (23/24 bestanden). Der vollständige Browserlauf wurde
auf dem anschließend fertig gebauten Bundle wiederholt.

Die zwei Python-Warnungen betreffen bestehende Starlette/httpx- und
anyio-Deprecations. Keine Ausnahme vom 100-%-Statement-Gate wurde eingeführt.
Playwright verwendet Edge, lokalen isolierten Spielzustand, FakeRouter und
lokale Tile-Fixtures; es ist kein Live-Valhalla-/OSM-Verfügbarkeitstest.

## Wirtschaftsaudit

Die Matrix umfasst 14 Modelle × 484 operative NHM-Profile × 3 Bänder.
2.457 inkompatible Modell/NHM/Band-Kombinationen sind explizit markiert.
17.871 kompatible Kombinationen ergeben je neun Szenarien: niedrige,
typisch neu generierte und hohe Beladung, jeweils mit 0/10/50 km Anfahrt
und 100/50/10 % Startfüllung. Die typische Beladung nutzt den Median aus
101 Seed-Draws und exakt dieselbe Domainverteilung wie die Factory.

- Normierte Lastverteilung: 20.000 Draws je repräsentativem Intervall und
  Kapazität; Grenzen, Reproduzierbarkeit, Mittelwert 0,74–0,76, Median
  0,78–0,81, obere Hälfte 86–89 %, unteres Viertel 1–2,2 % getestet.
- Mindestwert der Referenzmarge in der Matrix: **45,75 %**. Diese Zahl gilt
  für die untersuchten 75/375/1000 km, nicht als Gewinnversprechen.
- **16.298** negative tatsächliche Cashflow-Szenarien; **4.878** davon mit
  typischer Beladung. Sie werden nicht durch Tonnagen-/Tarifnachbesserung
  versteckt. Tank-/Ladekäufe und Anfahrt unterscheiden sich bewusst von
  der Referenzbewertung verbrauchter Energie der Frachtstrecke.

| Modell | Scale | Inkompatible Kombinationen | Kleinste Referenzmarge | Negative typische Cashflows | Median typische Tons |
| --- | --- | ---: | ---: | ---: | ---: |
| `vw_crafter_35_130kw` | van | 453 | 49.42 % | 0 | 0.84 |
| `mercedes_sprinter_317_cdi` | van | 453 | 49.15 % | 0 | 0.80 |
| `iveco_daily_35s18` | van | 453 | 48.57 % | 0 | 0.87 |
| `mercedes_atego_818_l` | light_distribution | 366 | 46.50 % | 0 | 1.48 |
| `mercedes_atego_1224_l` | medium_distribution | 366 | 45.75 % | 362 | 3.79 |
| `man_tgl_12_250` | medium_distribution | 366 | 45.92 % | 362 | 3.93 |
| `iveco_sway_500` | heavy | 0 | 51.21 % | 704 | 18.93 |
| `renault_t_high_520` | heavy | 0 | 51.08 % | 616 | 18.91 |
| `man_tgx_520` | heavy | 0 | 51.15 % | 625 | 19.01 |
| `daf_xg_plus_480` | heavy | 0 | 51.38 % | 578 | 18.95 |
| `mercedes_actros_l_380` | heavy | 0 | 51.08 % | 620 | 18.82 |
| `volvo_fh_aero_500_isave` | heavy | 0 | 51.25 % | 620 | 18.84 |
| `scania_r460_gas` | heavy | 0 | 51.76 % | 391 | 18.41 |
| `mercedes_eactros_600` | heavy | 0 | 51.66 % | 0 | 17.21 |


CSV/JSON liegen lokal unter `artifacts/economy/` und werden nicht versioniert.
Die Tabelle ersetzt keine gesamte Marktverteilung: Profile und Szenarien
sind systematisch enumeriert, nicht nach realer Spielerhäufigkeit gewichtet.

## Architektur- und Dokumentationsabgleich

[Einzelreview](docs/FRONTEND_ECONOMY_REVIEW.md) benennt pro Callable Zweck,
Schicht, Abhängigkeiten und Seiteneffekte. Kostenresolver, Tarif-, Mengen-
und Kostenfunktionen, Startup-Service, Preference-Service und Read-Modelle
halten getrennte Grenzen. SQL bleibt in Repositories; keine Views mit
Requests oder parallele Client-Eignungs-/Preisregeln. Der GameService
materialisiert gespeicherte Quote-Ergebnisse und delegiert Berechnungen.

Aktualisiert: README, Produkt, Ziel, Milestones, Architektur, Domain, API,
Persistenz, World-/Datenquellen, UI, Tests, Observability und Security.
[ECONOMY_V2.md](docs/ECONOMY_V2.md) dokumentiert verbindliche Formeln,
Rundung, Cache-Revisionsverhalten, Historie und Auditmethodik. Frühere
Anfahrtsabnahme bleibt im Git-Verlauf und in DISPATCH_APPROACH_REVIEW.md.

## Visuelle Prüfung und verbleibende Datenlücken

Desktop (1440×900), Tablet und Mobil (390×844), Reduced Motion, Stadt-/Europa-
Zoom, Flotte/Shop, Firmenfarben, Analytics sowie Abhol-/Lieferphasen wurden
an den erzeugten Screenshots geprüft. Kostenansichten kleiner und großer
Aufträge sowie mehrerer Ladehalte wurden zusätzlich aufgenommen und visuell
geprüft: Einzelkomponenten/Summen lesbar, keine horizontale Überbreite.

Die Front-/Seiten-SVGs enthalten Rasterbilder ohne Lackiermaske. Der
implementierte SVG-Tint erhält Transparenz/Schattierung, betrifft jedoch das
gesamte Fahrzeug. Map-Assets nutzen ihre vorhandene Farbmaske. Quelldateien
bleiben unverändert; eine selektive Kabinenlackierung ist datenbedingt nicht
vorhanden. Fehlende Assets erhalten einen Fahrzeugfallback.

Alle 14 Modelle haben direkte Wartungswerte; hierfür besteht keine Datenlücke.
Der World-Katalog enthält 559 routbare Facilities, davon 95 verifizierte
und 464 ausdrücklich geschätzte Standorte. Die Berliner Testflotte erreicht
alle drei Distanzbänder mit mindestens drei Angeboten. Für inaktive Städte
wurden entsprechend der Architektur keine globalen Origin-Berechnungen
angestellt; nicht erzeugbare Bands bleiben explizite Coverage-Diagnosen.
Die 2.457 inkompatiblen Auditkombinationen werden nicht künstlich ergänzt.

Spieler-DBs, Backups, Screenshots und Prüfartefakte sind nicht Bestandteil
der Commits. Beide kanonischen Referenz-DBs stimmen bytegenau mit dem
Ausgangsstand überein.
