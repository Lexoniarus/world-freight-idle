# Architektur

Stand: 25.09.2026. Die Anwendung besitzt genau eine relationale Laufzeit.
UI First, native ES-Module, FastAPI und `python main.py` bleiben Grundlage.

## Schichten und Zuständigkeiten

- `app/domain`: Entities, unveränderliche Werte, historische Snapshots und
  Ports. Keine SQL-, HTTP-, KV- oder Serialisierungslogik.
- `app/services`: Initialisierung, Markt, Kauf, Disposition, Settlement,
  Authentifizierung und Profilpflege. Orchestratoren verbinden benannte
  fachliche Schritte und injizierte Ports.
- `app/repositories`: SQLite, Verbindungen, Transaktionen, Schema-Validierung
  und kanonisches Snapshot-Mapping. Read-only Referenzdaten bleiben getrennt
  vom beschreibbaren Spielerzustand.
- `app/providers`: validierte Valhalla-/Geocoding-Antworten, Providerfehler,
  Rate-Limit und Cache-Port. Nominatim gehört ausschließlich zum Enrichment.
- `app/api/v1`: HTTP-Eingaben, Statuscodes und öffentliche JSON-Projektionen.
  Bestehende `hub_id`-Felder werden hier aus Facility-UIDs projiziert.
- `app/bootstrap.py` und `app/main.py`: konkrete Verdrahtung und Ressourcenbesitz.
  Die Zeitquelle wird im Composition Root an GameService übergeben.

```text
Browser → API → Services → Domain-Ports
                            ├─ GameUnitOfWork / GameStateRepository → SQLite
                            ├─ AccountStore / ProviderCache → SQLite
                            ├─ LeaderboardReader / TrafficReader → SQLite
                            ├─ VehicleCatalogue / WorldCatalogue → read-only SQLite
                            └─ TruckRouter → Valhalla
```

Die Lifespan registriert den Routing-HTTP-Client sofort im AsyncExitStack.
Start- und Shutdownfehler verhindern dessen Freigabe nicht. SQLite-Verbindungen
gehören dem jeweiligen Adapter und werden auch bei Fehlern geschlossen.
Domainregeln erhalten Zeitpunkte als Parameter.

## Zustand und Atomarität

PlayerState schützt Geld und Fortschritt; OwnedVehicle schützt Status,
Kapazität, Energieprofil, Füllstand und Standort. ContractOffer beschreibt ein verfügbares Angebot.
ActiveTransport komponiert HistoricalContractSnapshot, Endpunkte, Route und Fahrtplan
und wechselt genau einmal von active zu settled. Historische Werte werden
nicht bei späteren Katalogänderungen neu aufgelöst.

GameUnitOfWork besitzt BEGIN IMMEDIATE. Kauf, Startinitialisierung, Reset,
Disposition und Settlement speichern zusammengehörige Mutationen atomar.
Routing läuft außerhalb der Schreibtransaktion. Danach werden Angebot,
Fahrzeug, Energieausstattung, Startfüllstand, Kosten und Guthaben erneut geprüft. Markterzeugung erfolgt erst nach
committeter Auszahlung. Details: [RELATIONAL_STATE.md](RELATIONAL_STATE.md).

Accounts besitzen getrennte Spielzustände; dieselbe lokale Fahrzeugkennung
mehrerer Spieler ist erlaubt. Rangliste und Mehrspielerkarte verwenden eigene
Leseports. Nur noch aktive fällige Transporte ergänzen die Offline-Rangliste.
Öffentliche Verkehrsdaten enthalten keine Guthaben, Kosten oder Zugangsdaten.
TrafficReader liefert unveränderliche SharedTransport-Werte mit Koordinaten.
Spielerfarben, Eigentumsmarkierung und GeoJSON entstehen erst in der API-
Projektion; ein zusätzlicher durchreichender Mehrspieler-Service entfällt.

### Begrenzte Transportabfragen

Normale Spielabfragen laden ausschließlich aktive beziehungsweise fällige
Transporte über typisierte Repository-Methoden. SQL filtert Besitzer, Status
und Ankunft vor der Snapshot-Deserialisierung; der Index `arrivals` unterstützt
diesen Zugriff. Vollständige Historienabfragen bleiben expliziten
Bestandsabgleichen vorbehalten. Settlement bleibt atomar.

Die Startprüfung vergleicht Primär-/Fremdschlüssel und die ausführbaren
Transport-Guards mit dem unterstützten Schema, nicht nur deren Namen.
SQL-Formatierung wird ignoriert, Literalinhalte bleiben unverändert.
Abweichungen liefern `UnsupportedGameSchema` und `state.schema_rejected`;
eine automatische Reparatur bestehender Dateien findet nicht statt.
Die Schemaversion ist 1.1.0; die Energieübernahme erfolgt explizit offline.

## Referenzwelt und Markt

WorldCatalogue 4.2.0 liefert gemeinsame Country-/City-Objekte. Facility
komponiert Address und Coordinates. Company bleibt unabhängig von einer Stadt.
Immutable World-/Country-/City-/Company-Scopes filtern Facilities. Mehrdeutige
Namen werden abgewiesen; UUIDs und gepflegte Legacy-Aliase sind eindeutig.

CachedWorldCatalogue hält genau eine validierte immutable Revision pro Prozess.
NhmProduct enthält nur Identität, Code, Namen und Hierarchie. Operative
Market-, Distance-, Scale- und Capability-Profile sind eigene Domainwerte.

| Baustein | Fachlicher Zweck |
| --- | --- |
| MarketScopeResolver | Stabile City-UIDs eigener idle Fahrzeuge |
| TradeNetwork | Globale NHM-Zielindizes und lazy Origin-Relationen |
| MarketCandidateService | Distanz, Warenprofile und Fahrzeugkompatibilität |
| MarketCoverageService | Retention anrechnen und Coverage-Auswahl planen |
| ContractFactory | Candidate mit separat gewähltem Fahrzeugkontext materialisieren |
| MarketGenerator | Diese drei Schritte orchestrieren |
| MarketLifecycleService | Retention, Pruning, Markttransaktion und Projektion der Eignung koordinieren |
| GameService | Spielabläufe koordinieren und Domainregeln delegieren |

Stateful Services und Repository-Grenzen sind injizierte Klassen. Gemeinsame
reine Funktionen prüfen Fahrzeugklasse/Scale; Haversine, Band, Gewichtung und
Tonnage bleiben kleine typisierte Funktionen. Der Generator kennt keine
Filterdetails, Coverage-Schleifen, SQL oder Transaktionen. Coverage liefert
einen immutable Plan und Diagnosen, keine materialisierten Angebote.

Routing findet vor der Dispatch-Schreibtransaktion statt. Danach werden alle
veränderlichen Voraussetzungen erneut gelesen. Same-City-Reposition,
Reservierung, Abbuchung, Transportanlage, Offer-Verbrauch und notwendiges
Pruning committen gemeinsam. Erst anschließend startet eine separate
Markttransaktion mit erneut gelesener Flotte und Retention. Refill-Fehler rollen
nur diese zweite Transaktion zurück und protokollieren `market.refill_failed`.
Der erfolgreiche Transport wird zurückgegeben; ein späterer Refresh füllt auf.

## Frontend

Die permanente MapLibre-Karte bleibt beim Wechsel der Kontextpanels erhalten.
Vite bündelt native Module und lokale Schriften. OSM-Raster ist die Basiskarte;
Satelliten, Spielerunternehmen und Depots bleiben außerhalb dieser Phase.

API-Client, Zustand, Controller, Views, Kartenlayer und Animation sind getrennt.
Views führen keine Requests aus. Dynamische Texte werden als DOM-Text gesetzt.
Controller besitzen und beenden Listener, Requests und Timer. LatestRequest
verwirft überholte Detailantworten. RefreshScheduler pollt nur bei Sichtbarkeit;
GameState verhindert überlappende Reads. Nach unsicheren Schreibantworten folgt
nach älteren Reads zwingend ein frischer Read; Mutationen werden nicht wiederholt.

ContractMarketController besitzt die Stadtmarktanfragen. Pan und Zoom lösen
keine Marktanfragen aus; Flotten-/Spielaktionen und Refresh aktualisieren sie. Standortmarker entstehen aus eigener
Flotte, Transport-Snapshots und der aktuellen Auftragsscheibe. Spielerfarben
und öffentliche Transporte bleiben von privaten Wirtschaftsangaben getrennt.
World Wrapping, Clustering, Tastatur, mobile Panels und Reduced Motion bleiben.

### Fahrzeugassets

`frontend/vehicle-assets.js` besitzt die einzige unveränderliche Zuordnung
von Katalogmodell zu Karten-, Front- und Seitenbild. `getVehicleAssets()`
liefert Pfade oder null. Views wählen weiterhin zuerst lokale Grafiken,
sonst ein vorhandenes Katalogfoto beziehungsweise die generische Illustration.
Karten-Rasterisierung, Farbmasken, Rotation und Cache-Lebenszyklus bleiben im
Kartenmodul. Stabile Bildknoten verhindern erneutes Laden beim Polling.

Die 134 SVGs liegen nach Modell unter `assets/vehicles/`; drei ausgewählte
Ansichten je Modell liegen direkt darin, weitere Varianten unter `source/`.
FastAPI liefert diese Dateien über `/assets/` aus. Vite bündelt die Zuordnung,
kopiert aber keine zweite Asset-Sammlung in den Build. Docker übernimmt den
Asset-Ordner mit dem Anwendungscode. Build und Assets werden gemeinsam
bereitgestellt; bereits geöffnete Seiten benötigen nach dem Update einen Reload.
Dateierhalt und Bildauswahl werden gegen das vorab erfasste Inventar geprüft.
Siehe [Asset-Manifest](../assets/MANIFEST.md).

## Offline-Werkzeuge und Beobachtbarkeit

Der normale Start lehnt KV-/unbekannte Spielschemata ab. Ausschließlich
`import_legacy_game.py` liest Altformate: Backup, neue Datei, Transaktion,
vollständiger Abgleich, keine automatische Aktivierung. Das Werkzeug ist kein
zweiter Spielpfad. Geografie-Normalisierung erzeugt ebenfalls eine separate
Katalogdatei nach Backup. Profilpflege verwendet injizierte Account-/Katalog-
Ports und eine spielerbezogene Unit-of-Work-Factory.

Strukturierte Ereignisse und Trace-IDs begleiten Provider, Markt, Disposition,
Auszahlung und Katalogzugriff. Persistenzfehler werden an Adaptergrenzen
normalisiert; HTTP 503 enthält weder SQL noch private Daten. Migrationsberichte
mit Spielerbezug, Datenbanken, Backups und Prüfarbeitsdateien bleiben außerhalb
von Git. Werkzeugnachweise und manuelles Review stehen im Qualitätsbericht.


## Energie, Zeit und historische Abläufe

EnergyProfile und JourneyPlan sind unveränderliche Domainwerte. Die reine
Fahrtplanung erhält Fahrzeug-Snapshot, Route, Ausgangsfüllstand und Zeitfaktor.
ActiveTransport wertet seinen Plan anhand übergebener Zeit aus; OwnedVehicle
besitzt ausschließlich den letzten persistenten Energiecheckpoint. Settlement
schreibt den Endfüllstand atomar mit Auszahlung und Standort. Keine Simulation
schreibt pro Animationstakt. Public MovementSegment enthält ausschließlich
Phase, Zeit und Strecke; private Energie- und Wirtschaftsdaten bleiben außerhalb
der Mehrspielerprojektion. `frontend/journey.js` ist die gemeinsame reine
Interpolation für Karte und Panels, keine zweite serverseitige Spielplanung.

Die Offline-Energieübernahme kennt das alte relationale Schema ausschließlich
im Repository `energy_upgrade.py`. CLI und Composition Root orchestrieren
Backup, Validierung und neue Ausgabe. Die Runtime unterstützt nur Schema 1.1.0.


## Frontend v2 und Analytics Read Model

Native ES-Module bleiben: Views rendern sichere DOM-Fragmente, Requests laufen
über GameApiClient in `frontend/api.js`. CityContextController besitzt die
Session-Stadtauswahl; LayerStateController besitzt Presets/Overrides nach
stabiler `user.id`; AnalyticsController besitzt bedarfsgeladene Statistikreads.
Separate LatestRequest-Instanzen schützen Marktbestand und Auftragsdetail.
WorldMap rendert; VehicleGroups, Opportunities, Layerdefinitionen und Kamera
bleiben eigene Module. Karteninstanz und Bildknoten überleben Navigation/Polls.

Analytics API → AnalyticsService → AnalyticsReader (Port) → SqliteAnalyticsReader.
Die Session liefert die Nutzer-ID, niemals ein Queryparameter. Vor dem Read
führt die API ausschließlich bestehende Arrival-Reconciliation samt getrenntem
Refill aus. Der Reader öffnet einen konsistenten SQLite-Lesestand. Kein Schema-
Update und keine Analytics-Schreibverantwortung im GameService.

Nutzer, Status und oberer Zeitstempel werden relational gefiltert; all-time
Totals benötigen die belegte Vergangenheit. Relationale Geldwerte und IDs
werden direkt gelesen, historische Dimensionen per `json_extract` aus der
Hülle `kind=transport, version=2`. Nur Skalare gelangen nach Python, niemals
vollständige JSON-Dokumente oder Routengeometrien. Der Reader verwendet weder
load_transport_record/load_transport noch RouteSnapshot-/ActiveTransport-
Hydration. Pflichtwerte werden validiert, optionaler V1-Kontext bleibt zulässig.
Ein verbietender Hydrationstest und SQLite-query_only-Test sichern die Grenze.
Arrival-Reconciliation darf ihre bestehenden Domainobjekte weiterhin laden.

Scope-Gesamtsummen, Zeitraumserie und Breakdowns entstehen aus demselben
Lesestand. UTC-Tage richten sich nach gespeichertem arrives_at; abgeschlossene
V1-Fahrten zählen, bleiben aber ohne V2-Klassifizierung. Kein Join auf heutige
Fahrzeugmodelle als angebliche Historie. Private Kennzahlen gelangen weder in
Traffic noch Leaderboard.
