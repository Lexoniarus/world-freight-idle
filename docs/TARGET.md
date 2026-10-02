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
- [x] Ruff/Format mit 79 Zeichen; Architekturabnahme wird gesondert dokumentiert.
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
- Fortlaufend verbindlich: erneutes OOP-/Single-Responsibility-Review bei jedem weiteren Ausbau
- [x] Funktionstest-Manifest verhindert ungetestete Python-Core-Funktionen
- [x] strukturierte Logs
- [x] Trace-ID je HTTP-Request
- [x] technische und Produktdokumentation im Repo

### Externe Integrationen

- [x] Nominatim-Adapter ausschließlich für Offline-Enrichment
- [x] Valhalla-Adapter mit `truck`-Profil
- [x] Caching der Providerantworten
- [x] kein Luftlinien-Fallback

## Definition of Done für neue Funktionen

Eine Funktion gilt erst als fertig, wenn:

1. sie eine einzelne klar benennbare Verantwortung hat,
2. ein expliziter Gegentest existiert,
3. sie als konkrete Python-Core-Funktion in `tests/function_test_manifest.py` referenziert ist (Frontend: Verhaltenstest und Gegentest),
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

## Fahrzeugkatalog und Startausstattung

- 14 Modelle aus dem vorhandenen Referenzkatalog, getrennte technische Daten
  und Spielwerte; Katalog wird mit ausgeliefert und nur lesend geöffnet.
- Neue Spielstände: 175.000 € plus kostenlosem DB-IVECO S-Way. Bestehende
  Kaufwerte bleiben erhalten; Energieprofile werden ausschließlich über das
  explizite Offline-Upgrade ergänzt. Unbekannte Modellzuordnungen brechen es ab.
- Kaufpreis, Nutzlast, Reputationsfreigabe und individuelle Kilometerkosten aktiv.
- Konstante Verbrauchswerte, Restmengen und reichweitenabhängige Energiehalte
  sind aktiv. Wartung, Stationssuche, Ladekurven und Zuverlässigkeit bleiben offen.
- Kauf-/Quote-Validierung, verspätete Antworten und Fehlerfälle besitzen
  Regressionstests. Tatsächliche Prüfergebnisse stehen im Qualitätsbericht.
- M1 insgesamt bleibt wegen Unternehmen/eigener Depots weiterhin in Arbeit.


### Nachprüfung der Standards-Reparatur

Startinitialisierung kapselt ihre Transaktion, Lifespan umfasst fehlgeschlagenen
Aufbau und Cleanup, und lokale Profilpflege besitzt getrennte CLI-/Service-/
Repository-Grenzen. Auch Modellwechsel während Routing werden beim Transportstart
wirtschaftlich erneut geprüft. Diese Reparatur verändert weder Produktumfang
noch M1-Status. Werkzeug- und Reviewnachweise stehen im Qualitätsbericht.

## WorldCatalogue-Teilumfang

Implementiert: separater read-only Referenzkatalog, dauerhafte UUIDs,
559 routbare Facilities mit NHM-basierten Aufträgen; 95 Positionen sind
verifiziert, 464 ausdrücklich für die Simulation geschätzt;
Snapshots und explizite Backup-/Bestandsmigration sowie Facility-BBox-API.
Spielerunternehmen und eigene Depots bleiben offen. Werkzeugprüfungen und
Architektur-/Browserreview werden getrennt im QUALITY_REPORT.md ausgewiesen.

Market v2 ergänzt Angebote für geeignete Facilities aktiver Fahrzeugstädte
und deren verfügbare Distanzbänder. Mengen verwenden gespeicherte Kapazität
und NHM-Load-Factors; reale Warenbelege bleiben von simulierten Aufträgen
getrennt. Historische payload_band-Werte bleiben ausschließlich lesbar.
Mengenregeln und Kompatibilität: [WorldCatalogue](WORLD_CATALOGUE.md).

## Abnahme – gemeinsamer Live-Verkehr

- [x] Aktive Transporte anderer angemeldeter Spieler sind auf derselben Karte sichtbar.
- [x] Private Wirtschafts- und Vertragsdaten bleiben aus der öffentlichen Projektion ausgeschlossen.
- [x] Spielerfarben sind stabil und unterscheiden Fahrzeughalter visuell.
- [x] Brand-Free-Sprites werden pro Modell/Farbe wiederverwendet; fehlende Modelle behalten einen farbigen Fallback.
- [x] Eigene Routenlinien bleiben privat; fremde Fahrzeugklicks öffnen keine privaten Transportdetails.
- [x] Ausgeführte/abgelaufene Transporte werden nicht mehr als Live-Verkehr projiziert.

- [x] TrafficReader gibt nur öffentliche Trackingwerte weiter; der SQLite-Leser validiert zuvor gespeicherte Transport-Snapshots.
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
- [x] Karte, Flotte und Shop verwenden eine gemeinsame unveränderliche Modell-ID-Zuordnung.
- [x] Alle 134 SVGs sind mit unverändertem SHA-256 erhalten, ohne alte Pfadkopien.
- [x] 42 aktive Ansichten und 92 zusätzliche Dateien sind nach Katalogmodell geordnet.
- [x] Front- und Seitenansicht liegen in getrennten begrenzten Zellen und überlagern sich nicht.
- [x] Tests prüfen für alle 14 Modelle, dass beide Dateien vorhanden und nicht identisch sind.
- [x] Lokale Spielassets verwenden keinen Remote-Foto-Ladezustand und keine externen Credentials.

## Abnahme – vollständige Fahrzeugkarten-Sprites

- [x] Alle 14 aktuellen Katalogmodelle besitzen einen eigenen Map-Sprite.
- [x] IVECO Daily, Atego 818 L, Atego 1224 L und MAN TGL verwenden keine Punkt-Fallbacks mehr.
- [x] Die vier ergänzten Map-SVGs unterstützen dieselbe Spielerfarb-Variable wie die bestehenden Sprites.
- [x] Ein Punkt-Fallback bleibt ausschließlich für unbekannte Modell-IDs erhalten.



## Aktuelle technische Grundlage

Typisierte Entities, PostgreSQL-Spielpersistenz in privaten Supabase-Schemas und
WorldCatalogue 4.2.0 bilden die Produktionslaufzeit. SQLite bleibt auf Tests und
explizite Offline-Werkzeuge beschränkt. Historische Snapshots bleiben
bei Katalogupdates erhalten. Details beschreiben [Architektur](ARCHITECTURE.md),
[Domainmodell](DOMAIN_MODEL.md) und [Persistenz](RELATIONAL_STATE.md).
Die abgeschlossene Umbauchronik liegt im [Archiv](archive/REFACTOR_EXECUTION.md).
Aktuelle Prüfungen und Grenzen stehen im [Qualitätsbericht](../QUALITY_REPORT.md).
Dieser technische Stand ersetzt weder die vollständige MVP- noch reale iPad-Abnahme.


## Market v2 – implementierter Stand vom 25.09.2026

Stadtmärkte eigener idle Fahrzeuge ersetzen Nutzlastklassen und Viewport-Scope.
V2 bewahrt gültige fahrbare Angebote und ergänzt Facility-/Distanz-Coverage.
Explizite Fahrzeugwahl steuert Quote, Betriebskosten und Energie. Die tatsächliche
Anfahrt wird mitgeplant; Dispatch und anschließender Markt-Refill besitzen
getrennte Transaktionen. Historische Transporte und gespeicherte Konditionen
bleiben erhalten. Trailer, Versicherungen und weitere Simulationen sind nicht
Bestandteil dieser Änderung. World 4.2.0 und Vehicle 2.2.0 sind die einzigen
Referenzschemata. Frühere Bestandszahlen in der Fortschrittschronik beschreiben
den damaligen Katalog; OwnedVehicle-Zahlen sind kein Architekturvertrag.
Details und Abnahme: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md),
[Qualitätsbericht](../QUALITY_REPORT.md).


## Frontend v2 – Abnahmeziel

Stadt und Fahrzeug führen zur verständlichen Transportentscheidung auf der
fortbestehenden realen Karte. Context-/Management-Drawer, drei mobile Sheet-
Höhen, City-UID-Links, private Unternehmensstatistik und lokal pro user.id
überschreibbare Layer-Presets bilden die neue Oberfläche. Ausgewählte Objekte
bleiben sichtbar, Gruppen bleiben bis zur Fahrzeugliste bedienbar. Bestehende
Market-v2-Regeln werden nicht im Frontend nachgebaut.

Abnahme umfasst Desktop/Tablet/Mobile, Reduced Motion, Tastatur/Fokus,
Kamerakontinuität, stabile Bilder, Nah-/Stadt-/Regional-/Europa-Zoom sowie
vollständige Quality-/E2E-Gates. Historische Finanz-/Leistungswerte stammen nur
aus belegten Transporten; kein historischer Model-Scope. Die tatsächlichen
Prüfnachweise und Grenzen stehen im [Qualitätsbericht](../QUALITY_REPORT.md).


## Ergänzung: echte Abholanfahrt

Auftragsannahme plant Standort A → Abholung B → Lieferung C. Gesamtdauer,
Verbrauch und Kosten schließen A → B ein, Frachterlös ausschließlich B → C.
Kein Teleport beim Dispatch, keine Ladezeit oder zweite Aktion bei B.
Historische Fahrten, Stadtmarkt-Eignung und relationale Schemaversion bleiben.

## Frontend-v2: Abnahmestand

Umgesetzt sind die getrennte Mengen-/Tarif-/Kostenlogik, atomarer globaler
Marktstart, aktive Stadtmarktauswahl, Account-Farben, Fahrzeuggruppen und
lesbare Analyticslabels. Prüfnachweise und verbleibende Datenlücken stehen im
[Qualitätsbericht](../QUALITY_REPORT.md), fachliche Verträge in
[ECONOMY_V2.md](ECONOMY_V2.md). Veröffentlichung ist nicht Teil dieser Umsetzung.

Kartenstabilisierung: gemeinsame Fahrzeugrenderpfade, ausschließlich
überlappungsbasierte Statusgruppen, selektive Lackierung und einmaliger
Navigationsfokus. Keine Änderung an Tarifen, Kosten oder Marktregeln.


Ergänzung zum freigegebenen Navigationsmodell: Weltkarte als Überblick ohne
„Alle Städte“-Scope. Fahrzeug → Transport beziehungsweise idle Fahrzeug →
Stadtmarkt. Dieser zeigt ausschließlich Angebote, deren serverseitige
`eligible_vehicle_ids` das ausgewählte eigene idle Fahrzeug enthalten.
Liste und Kartenmarker verwenden dieselbe Eignungsprojektion. Ohne gültige
Auswahl erscheint „Fahrzeug wählen“. Bei Abfahrt wird der Kontext geleert;
Polling wählt kein Ersatzfahrzeug. Der gespeicherte Spielerpool bleibt geteilt;
ein Offer darf mehrere Fahrzeuge versorgen.

## Ziel: getrennte Display- und Truck-Routing-Koordinaten

- Kartenmarker und historische Snapshots behalten Facility-Displaywerte.
- Truck-Routing löst Endpunkte ausschließlich über stabile Facility-UIDs auf.
- Ein Routing-Anker muss von Valhalla für `truck` korreliert und innerhalb
  von maximal 1.000 Metern zur ursprünglichen Facility liegen. Locate liefert
  nur Kandidaten; Freigabe verlangt Hin- und Rückweg mit passenden tatsächlichen
  Geometrie-Endpunkten (jeweils höchstens 10 Meter zum vorgesehenen Anker).
- Nominatim ist ausschließlich Backend-Fallback und bleibt gecacht sowie
  rate-limited.
- Providerfehler und nicht routbare Facilities werden klassifiziert
  persistiert; es gibt keine synthetischen Straßenkoordinaten.


## Global Routing Readiness

Routing-Readiness-Implementierung: implementiert / vollständige lokale Quality- und E2E-Gates bestanden.
495 Python-Tests, 100 % Core-Statement-Coverage, 101 Frontendtests und
30 Playwright-Fälle bestanden. Branch-Push ausdrücklich freigegeben;
kein PR oder Merge.


## Reviewkorrekturen und Vehicle-Ready-Markt (27.09.2026)

Direkte Umsetzung auf dem ausdrücklich vorgegebenen `feature/frontend-v2`,
Basis `e49e5fa`. Kein ZIP, Push, PR oder Merge. Zehn Reviewkorrekturen sowie
fahrzeugbezogene Coverage ergänzen den bestehenden globalen Routingpfad.
Status: implemented / targeted tests passed / full acceptance pending,
maßgeblich sind die tatsächlich dokumentierten Ergebnisse im Qualitätsbericht.
Frühere Gesamtabnahmen gelten nicht für diesen Korrekturstand.


## Befahrbare Standortverbindungen (27.09.2026)

Auf Basis `5d7ff77` im bestehenden `feature/frontend-v2` umgesetzt: Freigabe
jeder Lieferung und Anfahrt erst mit echten Hin- und Rückwegen und passenden
Endpunkten. Automatische Kandidatensuche höchstens 1.000 Meter, fünf Kandidaten
je Standort, 25 Paare und 120 Sekunden. Gemeinsame Leases und atomare
Veröffentlichung; versionierte Nachweise mit Wiederprüfung nach 24 Stunden,
einer Stunde bei definitiven Fehlern beziehungsweise 60 Sekunden bei Störungen.

Wolfsburger LKW auf isolierter Spielstandkopie regulär disponiert; Ankunft und
Folgeauftrag geprüft. Zehn begrenzte Live-Provideranfragen insgesamt. Backup vorhanden, echter
Spielstand unverändert. Gezielte Prüfungen siehe
[Änderungs- und Abnahmebericht](CONNECTED_ROUTING_REVIEW.md).
Vollständige Suite und Gesamtintegration verbleiben ausdrücklich beim Nutzer.


## Runtime-Trennung und Alttransport-Reparatur (27.09.2026)

Die neue verbindliche Abschlussvoraussetzung ersetzt die fruehere Beschraenkung
auf gezielte Routingtests: vollstaendiges Quality-Gate mit 100 % app-Statement-
Coverage sowie komplette Browserregression vor Commit/Push auf feature/frontend-v2.
Runtime und Vorbereitung laufen getrennt; Spielstand und Flotte erscheinen vor
Geometrien und Markt. Read-Ziel p95 <= 250 ms, weitere Spielerstarts <= 2 s
(einmaliger Kaltstart mit Settlement bei 3,39 s am 28.09.2026 akzeptiert),
Runtime plus Verkehr <= 250 KiB pro Poll. Keine unveraenderten Geometrien im Polling.

Die beiden bestaetigten optionalen Alt-Anfahrtsplaene werden nur offline auf
einer gesicherten Kopie repariert. Live-Aktivierung und echte iPad-Abnahme bleiben
separate Betriebsschritte. Implementierung und tatsaechlicher Abnahmestand:
[Runtime-Review](RUNTIME_ISOLATION_REVIEW.md) und [Qualitaetsbericht](../QUALITY_REPORT.md).


## Gemeinsamer Auftragsvorrat (28.09.2026)

Das ausgewählte Fahrzeug erhält genau drei fahrbare Angebote je Streckentyp,
sofern genügend geprüfter Bestand verfügbar ist. Der gemeinsame Hintergrundvorrat
hält mindestens zehn Vorlagen je Bedarfsstadt, konkretem Modell und Band; jede
Vorlage ist einmal je Spieler verwendbar. Die drei sichtbaren gehören zu diesen
zehn. Kompatible eigene Fahrzeuge dürfen dieselben persönlichen Angebote nutzen.

Ungenutzte Vorlagen und Angebote verfallen nicht zeitlich und bleiben bei Abfahrt
und Rückkehr erhalten. Ein Verbrauch lässt gespeicherte Reserve sofort nachrücken;
der Worker füllt nach. Bedarf entsteht im Stand und ab 60 Minuten vor gespeicherter
Ankunft. Fehlende Hin-/Rückwege, veraltete Prüfnachweise oder unbrauchbare
Katalogbezüge geben keine Angebote frei. Alle 14 Modelle werden in Bedarfsstädten
berücksichtigt, tatsächlich wartende Fahrzeuge zuerst.

Die Schemaübernahme nach 1.2.0 ist ein expliziter Offline-Schritt mit Backup und
neuer Ausgabe. Live-Aktivierung ist nicht Teil von Commit/Push. Verbindliche
Gesamtabnahme: Quality-Gate mit 100 % app-Statement-Coverage, vollständige
Browserregression und Leistungsabnahme. Tatsächlicher Stand und Grenzen stehen
im [Qualitätsbericht](../QUALITY_REPORT.md); Verantwortlichkeiten in
[ADR 0008](adr/0008-shared-market-stock.md).

## Supabase/PostgreSQL production runtime (28.09.2026)

Produktiv verwendet die Anwendung eine serverseitige PostgreSQL-Verbindung zu
Supabase. `game`, `world_catalogue` und `vehicle_catalogue` sind getrennte
Schemas derselben PostgreSQL-Instanz. Browserzugriff auf diese Schemas findet
nicht statt; der Browser bleibt an `/api/v1` gebunden.

`DATABASE_URL` aktiviert den PostgreSQL-Pfad. Ohne diese Variable bleiben die
bestehenden SQLite-Adapter ausschließlich für Tests und explizite Offline-
Werkzeuge verfügbar. Die Produktions-Composition-Root wählt PostgreSQL für
Spielzustand und beide Referenzkataloge. Der World-/Vehicle-Snapshot wird wie
zuvor pro Prozess validiert und gecacht.

Die PostgreSQL-Game-UoW hält die bestehende atomare Semantik konservativ durch
einen transaktionsgebundenen Advisory Lock aufrecht. Provider-Awaits bleiben
außerhalb von Schreibtransaktionen. Read-Transaktionen verwenden einen
repeatable-read/read-only Snapshot. Der Connection-Pool gehört dem jeweiligen
Runtime-/Prewarm-Prozess und wird beim Shutdown geschlossen.

Historische Snapshot-Texte bleiben Text und werden nicht still nach JSONB
migriert. SQLite-spezifische JSON1-Leseprojektionen werden ausschließlich an
der PostgreSQL-Adaptergrenze in native PostgreSQL-JSONB-Ausdrücke übersetzt.
Die Domain-, Service- und HTTP-Verträge ändern sich dadurch nicht.
