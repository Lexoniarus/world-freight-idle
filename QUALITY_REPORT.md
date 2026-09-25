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
