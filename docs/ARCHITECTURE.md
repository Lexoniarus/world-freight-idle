# Architektur

Stand: 02.10.2026. Die Anwendung besitzt genau eine relationale Produktionslaufzeit.
UI First, native ES-Module, FastAPI und `python main.py` bleiben Grundlage.

## Schichten und Zuständigkeiten

- `app/domain`: Entities, unveränderliche Werte, historische Snapshots und
  Ports. Keine SQL-, HTTP-, KV- oder Serialisierungslogik.
- `app/services`: Initialisierung, Markt, Kauf, Disposition, Settlement,
  Authentifizierung und Profilpflege. Orchestratoren verbinden benannte
  fachliche Schritte und injizierte Ports.
- `app/repositories`: PostgreSQL-Produktionsadapter sowie SQLite-Adapter für
  Tests und Offline-Werkzeuge, Verbindungen, Transaktionen, Schema-Validierung
  und kanonisches Snapshot-Mapping. Read-only Referenzdaten bleiben getrennt
  vom beschreibbaren Spielerzustand.
- `app/providers`: validierte Valhalla-/Geocoding-Antworten, Providerfehler,
  Rate-Limit und Cache-Port. Nominatim dient Offline-Enrichment und begrenztem Backend-Anchor-Repair;
  keine allgemeinen Spieler-Geocoding-Anfragen.
- `app/api/v1`: HTTP-Eingaben, Statuscodes und öffentliche JSON-Projektionen.
  Bestehende `hub_id`-Felder werden hier aus Facility-UIDs projiziert.
- `app/bootstrap.py` und `app/main.py`: konkrete Verdrahtung und Ressourcenbesitz.
  Die Zeitquelle wird im Composition Root an GameService übergeben.

```text
Browser → API → Services → Domain-Ports
                            ├─ GameUnitOfWork / GameStateRepository → PostgreSQL
                            ├─ AccountStore / ProviderCache → PostgreSQL
                            ├─ LeaderboardReader / TrafficReader → PostgreSQL
                            ├─ VehicleCatalogue / WorldCatalogue → read-only PostgreSQL
                            └─ TruckRouter → Valhalla
```

Die Lifespan registriert den Routing-HTTP-Client sofort im AsyncExitStack.
Start- und Shutdownfehler verhindern dessen Freigabe nicht. PostgreSQL-Pools
und optionale SQLite-Verbindungen gehören dem jeweiligen Adapter und werden
auch bei Fehlern geschlossen.
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
Gespeicherte Firmenfarben werden im öffentlichen Read-Modell gelesen.
Eigentumsmarkierung, deterministischer Farb-Fallback und GeoJSON entstehen
in der API-Projektion; ein zusätzlicher durchreichender Mehrspieler-Service entfällt.

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
Die Schemaversion ist 1.2.0; Energie- und Vorratsübernahmen erfolgen explizit offline.

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
veränderlichen Voraussetzungen einschließlich Abfahrtscheckpoint erneut
gelesen. Reservierung, Abbuchung, Transportanlage, Offer-Verbrauch und notwendiges
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
Backup, Validierung und neue Ausgabe. Die Runtime unterstützt nur Schema 1.2.0.


## Frontend v2 und Analytics Read Model

Native ES-Module bleiben: Views rendern sichere DOM-Fragmente, Requests laufen
über GameApiClient in `frontend/api.js`. CityContextController besitzt die
routenlokale Stadtauswahl; LayerStateController besitzt Presets/Overrides nach
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


## Dispatch-Planung mit Anfahrt

`DispatchPlanningService` lädt vorbereitete globale Straßenrelationen. Er lädt
A → B optional und B → C vor der Schreibtransaktion und komponiert die reine
Fahrt- und Preisplanung. `GameService` koordiniert Revalidierung und Persistenz.
Der vollständige immutable Start-Snapshot muss nach Routing und unmittelbar
vor Commit mit dem aktuellen Fahrzeugcheckpoint übereinstimmen.

`DispatchRoutePlan` trennt Start, Abholung, Ziel und Providerwerte der Abschnitte.
`plan_dispatch_journey` skaliert jeden Abschnitt separat, begrenzt seine
Geschwindigkeit und übergibt den Restfüllstand an den nächsten Abschnitt.
Zeit- und Kilometerintervalle schließen ohne Lücke aneinander an. Preisbildung
verwendet Frachtkilometer für Erlös und Gesamtkilometer für Betriebskosten.

Reservierung schreibt nur den Status enroute. Der Standort bleibt A bis zum
Settlement in C; es gibt weder Standortschreibvorgang noch Dispatch bei B.
Markt-Pruning bleibt Teil der Dispatch-Transaktion; Refill erfolgt nach Commit.
Öffentliche RouteLeg-Werte enthalten nur Geometrie, Providerzeit und Grenzen.
Die Karte hält vorbereitete Geometrien je Abschnitt und interpoliert mit dessen
Straßenkilometern. Eigene und fremde Fahrzeuge nutzen dieselbe Implementierung.
Das Funktionsreview steht in [DISPATCH_APPROACH_REVIEW.md](DISPATCH_APPROACH_REVIEW.md).


## Frontend-v2: getrennte Wirtschafts- und Startup-Verantwortungen

`DispatchPlanningService` orchestriert Routing/Journey/Kosten; der injizierte
`VehicleCostResolver` liest Referenzwerte über den Catalogue-Port. Domain-
Funktionen berechnen getrennt Beladung, Tarif, Einkaufskosten und Auszahlung.
`ContractFactory` bekommt immutable Kosten-/Energiekontexte im Candidate;
sie führt keine Katalogabfragen durch. Der minimale NHM-Faktor wird einmal
je World-Revision bestimmt. `MarketGenerator` bleibt reine Orchestrierung.

Der frühere globale Rebuild über `MarketStartupService` gehört nicht mehr zum
API-Startpfad. Die API validiert Schema und Referenzen. Der separate Prewarm-
Einstieg liest vorhandene Profil-IDs über den Store und plant Bedarf ein.
`MarketPreparationBatchService` und `MarketLifecycleService` veröffentlichen
anschließend bedarfsgesteuert gegen geprüfte Revisionen (ADR 0007).
Der ältere explizite Rebuild und seine Regressionstests bleiben vorhanden;
er wird von keinem Produktionsstart aufgerufen.

`PreferenceService` besitzt Palette/Fallback und Schreibtransaktion;
`SqlitePreferenceStore` besitzt ausschließlich Account-SQL. Analytics liest
aktuelle Namen konsistent neben historischen Skalarwerten. Anzeigenamen
werden rein berechnet, Gruppierungsschlüssel bleiben Fahrzeug-IDs.

Im Browser besitzt `VehicleColorAssets` Quellen und referenzgezählte Blob-
Varianten. `VehicleImageController` bindet DOM-Bilder und übergibt Leases vor
Freigabe ihrer Vorgänger. `VehicleIconRegistry` besitzt den MapLibre-Atlas,
`PreferencesController` Requests/Listener und Farbveröffentlichung. Views
rendern nur; verspätete Ergebnisse werden verworfen. Gemeinsame Quellen
werden für DOM und Karte wiederverwendet, bereits kolorierte Quellen nicht
nochmals gefiltert. Funktionsreview: [FRONTEND_ECONOMY_REVIEW.md](FRONTEND_ECONOMY_REVIEW.md).


Beide Referenzkataloge werden beim Serverstart validiert und für die Laufzeit
als immutable Revision gecacht. `CachedVehicleCatalogue` lädt seinen
injizierten validierenden Port unter einem Lock einmal erfolgreich; Fehler
werden nicht gecacht. Ein neuer Katalogstand erfordert einen Serverneustart
mit erneuter Validierung und globalem Marktneuaufbau. Offline-Werkzeuge lesen
weiterhin explizit ihren gewählten Katalog. Historische Transporte bleiben
von neuen Revisionen unabhängig.

## Kartenregressionsfix: Darstellungsgrenzen

`groupVehicles` partitioniert nach Eigentümer und Bewegungszustand. Reine
Footprint-Funktionen prüfen die Überlappung sichtbarer gedrehter Assetflächen
mit den identischen Skalierungsstops des Renderers. `VehicleGroups` besitzt
nur Gruppenzustand, Badges und Interaktion; Representative und Singleton
verwenden dieselben MapLibre-Symbole. Badge-Posen folgen jedem Bewegungsupdate.

`VehicleColorAssets` besitzt Quellen-/Masken-/Varianten-Caches und Leases.
`vehicle-paint` trennt sichere Rasterextraktion, Pixelfärbung und Browser-I/O.
`PreferencesController` besitzt Read-Abbruch, serialisierte Writes und die
bestätigte/vorgemerkte Farbe. Views projizieren Zustände ohne Requests.

`MapFocusController` konsumiert genau einen Fokus pro Navigationswechsel.
`focusCoordinates` projiziert gespeicherte Routen und aktuelle Journey-Posen;
`MapCamera` übernimmt nur Geometrie, Padding und Bewegungseinstellungen.
Flottenfilter sind aus der View in `fleet-selection` ausgelagert.
Einzelreview und Abnahme: [MAP_REGRESSION_REVIEW.md](MAP_REGRESSION_REVIEW.md).


### Fahrzeugkontext statt globalem Stadt-Scope

Die Weltkarte besitzt keinen operativen Scope. `market-context.js` löst das
idle Referenzfahrzeug rein aus Snapshot und URL auf. `CityContextController`
übernimmt ausschließlich den routenlokalen Ort; Liste und Eignungsanzeige
bleiben getrennt. Ein explizit ungeeignetes Fahrzeug darf der Panelcontroller
nicht automatisch ersetzen. Listenfilter der Flotte und fachliche Analytics-
Scopes bleiben eigenständige Ansichten, keine globale Kartenbeschränkung.

## Globale Truck-Routing-Anker

`RoutingAnchorResolver` ist ein zustandsbehafteter Service mit injizierten
Ports für Store, Valhalla-Locate und Geocoding. `SqliteRoutingAnchorRepository`
besitzt das einzige SQL für die abgeleiteten Anker. Externe Requests bleiben
in `NominatimGeocoder` und `ValhallaTruckAnchorLocator`.

```text
Facility UID -> WorldCatalogue -> RoutingAnchorResolver
                               -> Valhalla /locate (truck)
                               -> optional Nominatim -> /locate
                               -> RoutingAnchorRepository
                               -> TruckRouter /route
```

Display-Koordinaten bleiben unveränderliche World-/Snapshot-Fakten und werden
nicht als Straßenanker gespeichert. `DispatchPlanningService` entscheidet
Anfahrt anhand der Facility-Identität und lädt ausschließlich vorbereitete
Relationen. Die separate Preparation führt Provider-Awaits außerhalb von
Schreibtransaktionen aus; erst danach wird das Ergebnis gespeichert.


## Global Routing Readiness

MarketCandidateService bleibt strukturell routerfrei. Market Preparation liegt
zwischen Candidate-Erzeugung und Coverage/Materialisierung; MarketGenerator
orchestriert keine Providerrequests. Auch partial Markets veröffentlichen
**ausschließlich route-ready Offers**.

Globale gerichtete Relationen, Anchor-Versuche und Leases verwenden zusätzliche
Tabellen derselben SqliteGameDatabase. Keine zweite Runtime-Datenbank. Das
Player-State-Schema 1.1.0 bleibt unverändert; Offer-Referenzen liegen separat in
`offer_route_references` und werden mit Marktänderungen atomar geschrieben.
Die Offer-Dokumentversion 1 und Transport-Dokumentversion 2 bleiben erhalten.
RoutePayload benennt Straßenkilometer und Providerzeit explizit; Mapping zu
historischen RouteSnapshot-Feldern erfolgt ohne Migration an der Dispatchgrenze.

Der separate Prewarm-Prozess besitzt den Preparation-Worker und registriert Cleanup
vor dessen Start. Der API-Lifespan startet keinen Worker und baut keine Maerkte auf.
Shutdown cancelt und awaited die Worker-Task vor dem HTTP-Client.
Eine neue Context-Instanz verhindert geerbte HTTP-Traces und Schreibtransaktionen.
Globale Relations-/Anchor-Leases begrenzen parallele Arbeit; abgelaufene Leases
sind übernehmbar, verlorene Schreibrechte verhindern Relationsveröffentlichung.
Provider-Awaits liegen außerhalb von Schreibtransaktionen. Nach Await wird der
Markt aus aktuellem Flottenzustand neu gelesen und in kurzer UoW veröffentlicht.

Nominatim und Valhalla besitzen getrennte Provider-Limits. Worker steuern Batches
und Backoff, keine providerspezifischen Sleeps. Nominatim liefert lediglich
Kandidaten; Akzeptanz benötigt finale Valhalla-Truck-Validierung. Versuche bleiben
append-only. No-path und Distanzlimit erzwingen keine Anchor-Verschiebung.


## Reviewgrenzen und Vehicle-Ready-Veröffentlichung

`RelationDemandState` enthält gerichtete Identität, erwarteten Fingerprint,
effektiven Status und Referenz auch für fehlgeschlagene/ungeprüfte Relationen.
Zeitabhängige Abfragewerte gehören nicht in die Preparation-Generation.
Cache-Schlüssel bleiben ausschließlich im Routing-Repository; das bisherige
Schlüsselformat und Schema bleiben lesbar. Bind und Repository-Ersetzung besitzen
ihre atomare Grenze und beteiligen sich an einer äußeren Markt-UoW.

`MarketPreparationBatchService` erhält State-Port, Candidate-/Coverage-/Scope-
Services, Preparation und Refresh injiziert. Sein immutable Plan/Ergebnis trennt
fachlichen Bedarf vom Worker. Der Worker besitzt Scheduling, Trace, Lifecycle
und Fehlerschutz des gesamten Durchlaufs einschließlich Status und Finish.
Datenbankfehler führen zu abbrechbarem 60-Sekunden-Backoff. Nach externen Awaits
werden Generation und aktuelle Coverage neu gelesen; alte Ergebnisse sind gefenced.

`MarketCandidateService` bleibt routerfrei. Preparation reduziert kompatible
Kontexte auf ready Delivery plus individuellen ready Approach. `VehicleCoverageService`
plant zusätzliche, teilbare Coverage, ohne Offers zu materialisieren oder HTTP/SQL.
Approaches werden vor wechselnden Delivery-Auswahlen vorbereitet, um bei begrenzten
Batches nicht zu verhungern. Lifecycle publiziert und projiziert atomar lokal;
Provider-Awaits bleiben außerhalb aller Schreibtransaktionen.

Analytics-Repositories liefern immutable validierte Zeilen, der Service liefert
typisierte fachliche Aggregate. Nur die API-Projektion erzeugt die bisherige
JSON-Struktur. `EconomyAuditService` erhält Katalogports und RNG; Bootstrap verdrahtet
SQLite, die CLI formatiert CSV/JSON. Keine neue Persistenzarchitektur.

`releaseAll` versucht jede synchrone Freigabe in Reihenfolge und wirft danach
AggregateError. App und Karte sperren verspätete Antworten sofort. Bootstrap/Logout
melden Cleanupfehler zusätzlich zum ursprünglichen Workflowfehler. Controller-
und Map-Verträge sind typisiert; `synchronizeMapSelection` beschreibt die Auswahl
von Fahrzeug, Transport oder Offer. Kartenmarkt und Liste verwenden ausschließlich
serverseitige Eignungs-IDs; Views berechnen keine neue Kompatibilität.


## Runtime-/Vorbereitungsgrenze und kompakte Projektionen

ADR 0007 ersetzt den bisherigen Worker im API-Lifespan. `main.py` startet und
ueberwacht getrennte Rollen; beide verwenden dieselbe relationale SQLite-Datei
mit WAL/FULL und 5 s begrenzter Lock-Wartezeit. Runtime liest publizierte Offers
und Coverage; nur der Worker baut Kandidaten ausserhalb des Writers. Persistierte
Bedarfsversionen, globale Worker-Lease und Routingnachweise sichern kurze
Publikationstransaktionen ab. Zeitaufwendige Providerarbeit ist kein API-Fallback.

RuntimeReader liefert typisierte kompakte aktive Transporte direkt aus SQL-
Skalarprojektionen. Historische Geometrien werden einzeln autorisiert geladen.
Der Frontend-Cache koordiniert maximal vier Downloads, 200 Eintraege und
Account-Lebenszyklus. Spielansicht, Verkehr und Geometrien laden unabhaengig.
Details und manuelles Verantwortungsreview: [Runtime-Review](RUNTIME_ISOLATION_REVIEW.md).

## Gemeinsamer Auftragsvorrat

[ADR 0008](adr/0008-shared-market-stock.md) ergänzt die Runtime-Trennung.
Die Produktionsverdrahtung verwendet `StockPreparationBatch` mit getrennten
Bedarfs-, Planungs-, Vorlagen- und Publikationsservices. Sie liest kompakte
Zielfakten ohne Geometrien und plant Zielstädte unmittelbar ab Dispatch.
Die reine Dreier-Auswahl bleibt in `MarketSelectionService`.
SQL, Konsistenzgrenzen und Migrationsregeln sind in ADR 0008 benannt.

`MarketPreparationWorker` priorisiert sichtbaren Idle-Bestand, sichtbaren
Zielstadtbestand, Idle-Reserve und Zielstadtreserve. Nur wenn kein Spielerstatus
mehr `partial` ist, erhält `GlobalStockPreparationBatch` eine Runde für den
übrigen Weltvorrat. Er baut Kandidaten nur für einen ausgewählten
Stadt-/Modell-/Band-Kontext und prüft nur dessen Delivery-Paar. Gemeinsame
Vorlagen liegen hinter `SqliteMarketTemplateStore`; der persönliche Store
besitzt weiterhin Ausgabe, Verbrauch und Checkpoints.

`ReadinessView` lädt Relationen, Anker, Verbindungsevidenz und
Payload-Verfügbarkeit mengenbasiert. Candidate-Readiness und beide Batches
verwenden denselben Snapshot; die SQL-Zahl wächst daher nicht mit jeder
einzelnen Relation. Gezielte Provider-/Dispatchpfade behalten Einzelzugriffe.

`StockPublicationService` hält den vollständigen unveränderlichen Bestand für
den Revisionsvergleich und projiziert davon separat kataloggültige Angebote
und Vorlagen für Planung/Abdeckung. Veraltete oder frühere Stadtbestände werden
bewahrt. Normales Polling löst wegen dieser unsichtbaren Bestände keine neue
Bedarfsversion aus. Nur Zustandsänderungen, Refresh und fällige Wiederprüfung
fordern weitere Arbeit an. Verbrauch ist Teil der vorhandenen Dispatch-UoW.

Das [manuelle Verantwortungsreview](MARKET_STOCK_REVIEW.md) prüft die konkreten
Funktionen zusätzlich zu den automatischen Importgrenzen und Manifesttests.
Veränderte Frachtklasse oder geografisch verschobene Katalogstandorte sperren
alte Vorlagen/Angebote für die Freigabe und Defizitberechnung. Ihre gespeicherten
Konditionen und historische Transporte werden dabei nicht umgeschrieben.

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

Supabase Auth ist eine getrennte Providergrenze. `@supabase/supabase-js` besitzt
im Browser Session und Refresh; FastAPI prüft Bearer-Tokens lokal per ES256/JWKS
und projiziert den stabilen `sub` über den Account-Port nach `game.users`.
Weder der Datenbankzugang noch ein Supabase Secret Key gelangen ins Frontend.
Die vorhandene Cookie-Authentifizierung bleibt nur als Migrationsbrücke für
bestehende lokale Konten erhalten. Der Browser versucht Supabase Auth zuerst;
der same-origin Fallback akzeptiert ausschließlich die drei in der privaten
Tabelle `game.account_emails` hinterlegten Altkonten. Dabei werden die bisherigen
scrypt-Hashes und kompakten UUIDs weiterverwendet. Neue Registrierungen bleiben
vollständig bei Supabase Auth.

Die Schemas `game`, `world_catalogue` und `vehicle_catalogue` entziehen
`PUBLIC`, `anon` und `authenticated` alle Schema-, Tabellen-, Sequenz- und
Funktionsrechte. RLS ist auf allen 72 Tabellen als zweite Schutzschicht aktiv;
Browser-Policies existieren absichtlich nicht. Die Backend-Rolle ist der einzige
Runtimezugang. Der Start bricht ab, wenn einer erforderlichen `game`-Tabelle RLS
fehlt.

Der immutable World-Snapshot lädt Facility-Provenienz, Geocoding-Evidenz,
Aliasse und dokumentierte Güter in vier Batch-Projektionen. Damit bleibt die
SQLite-Domainprojektion erhalten, ohne deren frühere N+1-Leseform über die
PostgreSQL-Netzwerkgrenze zu tragen.
