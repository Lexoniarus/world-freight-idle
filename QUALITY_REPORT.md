# Qualitätsbericht: Frontend v2

Stand: 25.09.2026. Lokaler Branch `feature/frontend-v2`, Basis ist der vor
Arbeitsbeginn erneut geladene main `614ec730fc09a43151f9751d644190ace17a14be`.
Repository-Hooks sind aktiv. Keine Veröffentlichung und kein Merge.
Umgebung: Windows, Python 3.11.9, Node 24, Microsoft Edge / Codex In-app Browser.

## Implementierter Umfang

- Map-first HUD, graphitfarbene Managementflächen, lokale Barlow-/Inter-Schriften,
  semantische UI-/Kartenfarben, Context-/Management-Drawer und mobile Sheets.
- CityContext nach city_uid, deterministische Defaults, bewusste inaktive Städte,
  ungefilterte Auswahl, Browserhistorie, Fahrzeugvorwahl und Legacy-Hub-Auflösung.
- Stadtmarkt mit serverseitiger Eignung und deutschen Dimensionslabels,
  kompakten Cargo-Karten, getrenntem Listen-/Detailzustand und Quote-Verwerfung.
- Flotte nach Stadt und Richtung/Status, Modell-/Namensfilter und zustandsbezogene
  Front-/Side-/Map-Ansichten. Keine neuen Assets; Hash-Inventar bleibt erhalten.
- Layer-Presets und lokale Overrides nach stabiler authentifizierter user.id,
  Reset je Ansicht, unabhängige temporäre Auswahl, Gruppierung mit Count-Badges,
  Tastaturlisten, World Wrapping und echten unveränderten Koordinaten.
- Authentifizierte Analytics und exakte City-/Facility-Lookups. Analytics besitzt
  einen eigenen Reader-Port/Service/SQLite-Lesepfad, ausschließlich skalare
  JSON-Projektion und konsistenten Lesestand. Keine Transport-/Routenhydration.
- Unternehmen mit KPIs, UTC-Zeitreihen, Scopes, Ergebnisbalken und zugänglichen
  Tabellen. Importierter Fortschritt, belegte Historie und laufende Erwartungen
  sind getrennt. Keine historische Modellstatistik.

## Ausgeführte Prüfungen

Der vollständige Qualitätslauf wurde auf dem finalen Quellstand erfolgreich
ausgeführt. Die Browserregression hat anschließend denselben Produktionsbuild bestätigt.

| Prüfung | Ergebnis |
| --- | --- |
| python scripts/quality.py | bestanden |
| Python einschließlich Manifest/Architektur | 372 Verhaltenstests bestanden |
| App-Statement-Coverage | 100 %; 3979 Statements, keine Lücke |
| Ruff / Format, mypy / Pyright | bestanden; 101 Quelldateien / 0 Fehler |
| Frontend-Verhalten | 75 bestanden |
| ESLint, Stylelint, Prettier, checkJs, Vite | bestanden |
| npm run test:e2e | 18 bestanden; 4,3 Minuten |
| git diff --check | bestanden |

Die letzten verbindlichen Logs heißen `artifacts-frontend-v2-quality-final.log`
und `artifacts-frontend-v2-e2e-verified.log` (lokal, nicht versioniert). Zwischenläufe
während der Umsetzung sind keine Abnahme: dabei wurden unter anderem mobile
Navigationsebenen, zusammengepresste KPI-Gitter und mehrdeutige Testselektoren
gefunden und korrigiert. Kein Test und keine Coverage-Regel wurde deaktiviert.

## Verhalten und Datenschutz

Analytics-Gegenproben verbieten load_transport_record, load_transport sowie
RouteSnapshot-/ActiveTransport-Konstruktion und erhalten dennoch korrekte
Aggregate aus gespeicherten Fixtures mit großen Koordinatenarrays. Python
bekommt ausschließlich skalare Werte; JSON-Hülle, Version und Pflichtwerte
werden validiert. PRAGMA query_only sichert die Aggregation gegen Writes ab.
Gleichnamige beziehungsweise identische lokale Fahrzeug-IDs anderer Accounts
geben keine fremden Kennzahlen frei. Exact-Lookups und Analytics verlangen
Sessions. Fehlerantworten enthalten keine SQL-/Datei-/privaten Bestandsdetails.

Ankunft wird durch die vorhandene idempotente Settlement-Logik reconciled.
Der zweite Analytics-Aufruf bucht weder Kapital noch Fortschritt erneut.
Die Tageszuordnung verwendet historisches arrives_at in UTC, nicht Loginzeit.
V1-Historie bleibt für Unternehmen/Stadt/Fahrzeug nutzbar, ohne erfundene
Transportklasse/Distanzband-Zuordnung. Aktuelle Unternehmenswerte bleiben
unternehmensweit, Zeitraumauswertungen folgen dem gewählten Scope.

Frontend-Gegenproben prüfen UUIDs trotz gleicher Stadtnamen, explizite bekannte
Stadt ohne Markt, Verlust des letzten idle Fahrzeugs, Session-Auswahl, verspätete
Reads und unabhängige Marktlisten/-details. Eligibility wird ausschließlich
über eligible_vehicle_ids gelesen. Gruppen trennen eigene/fremde Objekte,
respektieren Auswahl, Wrapping und deaktivierte Gruppierung. Relative
Koordinaten bleiben unverändert. Auswahlquellen umgehen ausgeblendete normale
Layer, ohne lokale Präferenzen zu verändern.

## Browser und visuelle Abnahme

E2E-Größen: 1440×900, 1024×768 und 390×844; zusätzlich Reduced Motion.
Der vollständige Ablauf umfasst Anmeldung, Fahrzeug/Stadt, Auftrag, visuelle
Fahrzeugwahl, Quote, Dispatch, Transport, Unternehmen, alle Zeiträume und Scopes.
Geprüft werden Tastatur-/Rückkehrfokus, mobile Sheet-Höhen mit inert-Karte,
Canvas-Kontinuität, Pan/Zoom ohne Marktreads, unveränderte Bilder beim Polling,
Layer-Persistenz, Gruppenliste bei identischen Koordinaten, Analytics-Fehler/Retry
und KPI-Layout.

Manuelle OSM-Prüfung im isolierten lokalen Prüfserver: Europa-/Regionalzoom
zeigt lesbare Count-Marker beziehungsweise kompakte Fahrzeuge; Stadtzoom
ordnet Angebote nach Origin-Facility; Nahzoom zeigt Modellasset und Auswahlhalo
über Straßen/Labels. Aufklappbare Filter lassen den Aufträgen Platz. Lange
NHM-Namen behalten zugänglichen Volltext. Desktop-KPIs, Fahrzeugbilder und
mobile Vollhöhenansicht wurden zusätzlich anhand gerenderter Screenshots
kontrolliert. Im automatisierten Lauf ersetzen lokale PNGs OSM-Kacheln;
die echte Kartenprüfung wurde separat über Browserbedienung durchgeführt.

Screenshots liegen im temporären Verzeichnis unter
`world-freight-frontend-v2-company-desktop.png`, `...-tablet.png`, `...-mobile.png`
sowie `world-freight-frontend-v2-selected-hidden-layer.png`,
`world-freight-market-v2-desktop.png`, `...-mobile.png` und unter
`artifacts/assets-current/`. Keine physischen Mobilgeräte oder Safari-Abnahme
werden behauptet. Zwei bestehende Starlette/httpx-/AnyIO-Deprecation-Warnungen
sind keine Testfehler.

## Architekturreview und Grenzen

Views rendern ohne Requests. frontend/api.js bleibt der einzige Spiel-API-Zugang.
Controller besitzen Auswahl, Requests und Cleanup. WorldMap rendert/interagiert;
CityContext, Gruppenberechnung, Präferenzen und Analytics sind separate Module.
Panel- und Application-Orchestrierung enthalten keine neue Simulation oder
Eligibility-Logik. Listener und ausstehende Requests werden beendet; versteckte
Karten pausieren unnötige Bewegung. Bilddateien und Referenzkataloge wurden nicht
verändert. Statische globale Facility-/History-Downloads wurden nicht ergänzt.

Market v2 blieb fachlich unverändert; lediglich die irreführende anfängliche
TradeOptions-Gesamtzahl wurde aus dem Log entfernt. Dispatch-/Refill-Transaktionen
wurden nicht optimiert. World 4.2.0, Vehicle Catalogue 2.2.0 und Spielschema 1.1.0
bleiben bestehen. Keine Persistenzmigration. Fehlende historische Geld-/Strecken-
oder Tonnenwerte werden weder aus Fortschrittszählern noch heutigen Modellen
rekonstruiert. Die all-time Summen benötigen eigene belegte historische Skalare;
Routengeometrien werden dafür nicht nach Python übertragen.
