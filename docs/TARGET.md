# Ziel- und Abnahmedokumentation

## M1-Teilumfang – Mehrspielergrundlage

Maßgeblich ist `GOAL.md`, Abschnitt 35. Der Gesamt-MVP ist noch offen:
Ein eigenständiges Spielerunternehmen und ein eigenes Startdepot fehlen.
Die folgenden Häkchen beziehen sich ausschließlich auf Teilfunktionen.

### Zusätzliche UI-Abnahme nach UI DESIGN.md

- [x] OSM-Karte mit MapLibre als primäre Oberfläche nach dem Login.
- [x] Pan/Zoom, Touchbedienung und horizontales World Wrapping.
- [x] Anklickbare Fahrzeuge/Aufträge mit Kontextpanel bei erhaltener Karte.
- [x] Alle aktiven Fahrzeuge und auswählbare Routen als eigene Layer.
- [x] Zoomabhängiges Standort-Clustering; gleiche Standorte zusammengefasst.
- [x] Austauschbare Basiskarte; Attribution und Nutzung dokumentiert.
- [x] Keine Simulationsberechnungen aus Bildpixeln oder Kartenprojektion.
- [x] Responsive Panels, Tastaturfokus, Reduced Motion und Fehlerzustände.

UI First gilt vor weiterem Backend-Ausbau. Satellitenbilder sind ein späterer
Ausbau und keine M1-Abnahmevoraussetzung. Öffentliche Hubs sind keine eigenen
Depots; Karten-POIs sind keine spielbaren Unternehmen. Testgrenzen stehen
in TESTING.md; die Gesamt-M1-Abnahme bleibt bis zum Backend-Ausbau offen.

### Vorhandene funktionale Basis

- [x] `python main.py` als Einstiegspunkt, auch unter Windows.
- [x] Registrierung, Login, Logout und ablaufende/widerrufbare Sitzungen.
- [x] Gesalzene scrypt-Passwörter, HttpOnly/SameSite-Cookies, CSRF-Prüfung.
- [x] Spielertrennung inklusive fremder Ressourcen-IDs.
- [x] Fahrzeugkatalog und atomarer Kauf zu Serverpreisen.
- [x] Parallele Transporte, genau einmal verbuchte Ankünfte.
- [x] Gemeinsame Rangliste inklusive Offline-Ankünften.
- [x] Coding-Standards mit Ruff und 79 Zeichen.
- [ ] Öffentlicher Produktionsbetrieb/Hosting (separater Meilenstein).
- [ ] Global begrenzter gemeinsamer Markt.

## M1-Teilumfang – API-getriebener Road-Freight-Kern

Dieser Road-Freight-Teilumfang ist erfüllt, wenn die folgenden Kriterien
grün sind. Für die Gesamt-M1-Abnahme gelten zusätzlich die offenen Punkte
aus GOAL.md und MILESTONES.md.

### Produkt

- [x] direkt adressierbare Kontextpanels für Aufträge, Flotte und Transporte
- [x] eigener Auftragsdetail-Flow
- [x] Von-Adresse und Zu-Adresse sichtbar
- [x] reale Route wird vor Annahme berechnet
- [x] Fahrzeug muss am Startort stehen
- [x] Live-Tracking auf der Weltkarte mit Detailpanel
- [x] persistenter Realzeitfortschritt
- [x] Auszahlung und Standortwechsel bei Ankunft

### API

- [x] versionierte `/api/v1`-Grenze
- [x] ressourcenorientierte Endpoints
- [x] kein Frontend-Zugriff auf SQLite oder Routing-/Geocoding-Provider
- [x] Providerfehler werden als 502 abgebildet
- [x] Domain-/Validierungsfehler erhalten stabile 4xx-Antworten
- [x] OpenAPI unter `/docs`

### Architektur

- [x] Composition Root in `app/main.py` + `app/bootstrap.py`
- [x] API-Layer getrennt von Services
- [x] Provider-Adapter getrennt von Game-Core
- [x] Persistence als Repository
- [x] Market, Pricing und Game-Orchestrierung getrennt
- [x] Spielaktionen über API v1; Basiskarten-Tiles lädt der Browser direkt

### Qualität

- [x] PEP 8
- [x] Zustandsbehaftete UI-Komponenten mit expliziten Aufgaben und Lebenszyklus
- [x] Getrennte Views, Aktionen, Synchronisierung und Kartendarstellung
- [x] Benannte Use Cases und Composition Roots für Service-Verdrahtung
- [x] Review der bereinigten Modulgrenzen, ergänzt durch Architekturtests
- [ ] Erneutes OOP-/Single-Responsibility-Review bei jedem weiteren Ausbau
- [x] Funktionstest-Manifest verhindert ungetestete Python-Core-Funktionen
- [x] strukturierte Logs
- [x] Trace-ID je HTTP-Request
- [x] technische und Produktdokumentation im Repo

### Externe Integrationen

- [x] Nominatim-Adapter
- [x] Valhalla-Adapter mit `truck`-Profil
- [x] Caching der Providerantworten
- [x] kein Luftlinien-Fallback

## Definition of Done für neue Funktionen

Eine Funktion gilt erst als fertig, wenn:

1. sie eine einzelne klar benennbare Verantwortung hat,
2. ein expliziter Gegentest existiert,
3. sie in `tests/function_test_manifest.py` referenziert ist,
4. Fehlerpfade getestet sind,
5. relevante Logs/Tracing vorhanden sind,
6. betroffene Dokumentation aktualisiert wurde.

## Technische Abnahme der Standards-Bereinigung

Werkzeugprüfungen und Architekturbeurteilung sind getrennt:

- Verbindliche Gates: Ruff/Format, mypy, Core-Manifest/100 % Statements,
  ESLint, Stylelint, Prettier, checkJs, Frontendtests und Produktionsbuild.
- Architekturreview: klare Verantwortung pro Komponente/Funktion, reine
  Views, explizite Providergrenzen, definierte Ressourcenfreigabe, kein
  paralleler Alt-Frontendbestand. Automatische Importprüfungen ergänzen das Review.
- Funktionale Regression: vollständiger Spielablauf, persistierte Konten,
  parallele Transporte, Fokus, mobile Panels, Fehler und verspätete Antworten.

Prüfzahlen und tatsächliche Ausführung stehen ausschließlich im aktuellen
[QUALITY_REPORT.md](../QUALITY_REPORT.md). Die Abnahme dieser Bereinigung
ist keine pauschale Freigabe künftiger Architektur oder des gesamten M1.

## Ergänzung: Stabilisierung und Fahrzeug-DB

- Acht Modelle aus dem vorhandenen Referenzkatalog, getrennte technische Daten
  und Spielwerte; Katalog wird mit ausgeliefert und nur lesend geöffnet.
- Neue Spielstände: 175.000 € plus kostenlosem DB-IVECO S-Way. Keine automatische Gutschrift
  oder Umwandlung alter Flotten; alte Modelle bleiben disponierbar.
- Kaufpreis, Nutzlast, Reputationsfreigabe und individuelle Kilometerkosten aktiv.
- Wartung, Reichweitenbeschränkungen, Energiehalte und Zuverlässigkeit bleiben offen.
- Die sechs Reviewbefunde sind durch gezielte Korrekturen und Regressionstests
  adressiert. Tatsächliche Abnahmeergebnisse stehen in QUALITY_REPORT.md.
- M1 insgesamt bleibt wegen Unternehmen/eigener Depots weiterhin in Arbeit.


### Nachprüfung der Standards-Reparatur

Startinitialisierung kapselt ihre Transaktion, Lifespan umfasst fehlgeschlagenen
Aufbau und Cleanup, und lokale Profilpflege besitzt getrennte CLI-/Service-/
Repository-Grenzen. Auch Modellwechsel während Routing werden beim Transportstart
wirtschaftlich erneut geprüft. Diese Reparatur verändert weder Produktumfang
noch M1-Status. Werkzeug- und Reviewnachweise stehen im Qualitätsbericht.

## WorldCatalogue-Teilumfang

Implementiert: separater read-only Referenzkatalog, dauerhafte UUIDs,
43 verifizierte routbare Facilities mit Aufträgen; 24 mit dokumentierten
Standardwaren, 19 mit ausdrücklich simulierter Standardfracht,
Snapshots und explizite Backup-/Bestandsmigration sowie Facility-BBox-API.
Spielerunternehmen und eigene Depots bleiben offen. Werkzeugprüfungen und
Architektur-/Browserreview werden getrennt im QUALITY_REPORT.md ausgewiesen.

Aufträge werden je routbarer Facility und belegter Nutzlastklasse aus dem
Fahrzeugkatalog ergänzt. Auch kleine Transporter und bestehende Fahrzeuge
erhalten geeignete Mengen; `payload_band` ist simuliert, reale Warenbelege
bleiben getrennt. Mengenregeln und Kompatibilität: [WorldCatalogue](WORLD_CATALOGUE.md).

## Abnahme – gemeinsamer Live-Verkehr

- [x] Aktive Transporte anderer angemeldeter Spieler sind auf derselben Karte sichtbar.
- [x] Private Wirtschafts- und Vertragsdaten bleiben aus der öffentlichen Projektion ausgeschlossen.
- [x] Spielerfarben sind stabil und unterscheiden Fahrzeughalter visuell.
- [x] Brand-Free-Sprites werden pro Modell/Farbe wiederverwendet; fehlende Modelle behalten einen farbigen Fallback.
- [x] Eigene Routenlinien bleiben privat; fremde Fahrzeugklicks öffnen keine privaten Transportdetails.
- [x] Ausgeführte/abgelaufene Transporte werden nicht mehr als Live-Verkehr projiziert.

## Abnahme – gemeinsamer Live-Verkehr V2

- [x] Repository liest nur öffentliche Live-Traffic-Felder aus Spielerzuständen.
- [x] Private Vertrags-, Erlös-, Kosten- und Guthabendaten werden nicht projiziert.
- [x] Multiplayer-Traffic-Fehler werden in der UI sichtbar und nicht still verschluckt.
- [x] Letzter gültiger Traffic-Stand bleibt bei temporärem Fehler erhalten.
- [x] Modell-ID und Modellname bleiben im öffentlichen Kartenpayload getrennt erhalten.
- [x] Spielerfarbe wird direkt im Sprite beziehungsweise beim Fallback-Punkt dargestellt.
- [x] Eigene Fahrzeuge und Multiplayer-Verkehr sind als getrennte Kartenlayer schaltbar.
- [x] Anwendungsshell wird mit `Cache-Control: no-store` ausgeliefert, damit ein
      neuer Vite-Build nicht durch eine alte HTML-Shell verdeckt wird.

## Abnahme – lokale Mehransichten in Flotte und Shop

- [x] Alle 14 aktuellen Katalogmodelle besitzen normalisierte Front- und Seitenansichten.
- [x] Flotte und Shop verwenden dieselbe Modell-ID-Zuordnung zu den lokalen UI-Assets.
- [x] Front- und Seitenansicht liegen in getrennten begrenzten Zellen und überlagern sich nicht.
- [x] Tests prüfen für alle 14 Modelle, dass beide Dateien vorhanden und nicht identisch sind.
- [x] Lokale Spielassets verwenden keinen Remote-Foto-Ladezustand und keine externen Credentials.
