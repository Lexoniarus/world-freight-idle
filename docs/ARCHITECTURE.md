# Architektur

Stand: 23.09.2026. Die Anwendung besitzt genau eine relationale Laufzeit.
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
Kapazität und Standort. ContractOffer beschreibt ein verfügbares Angebot.
ActiveTransport komponiert HistoricalContractSnapshot, Endpunkte und Route
und wechselt genau einmal von active zu settled. Historische Werte werden
nicht bei späteren Katalogänderungen neu aufgelöst.

GameUnitOfWork besitzt BEGIN IMMEDIATE. Kauf, Startinitialisierung, Reset,
Disposition und Settlement speichern zusammengehörige Mutationen atomar.
Routing läuft außerhalb der Schreibtransaktion. Danach werden Angebot,
Fahrzeug, Kosten und Guthaben erneut geprüft. Markterzeugung erfolgt erst nach
committeter Auszahlung. Details: [RELATIONAL_STATE.md](RELATIONAL_STATE.md).

Accounts besitzen getrennte Spielzustände; dieselbe lokale Fahrzeugkennung
mehrerer Spieler ist erlaubt. Rangliste und Mehrspielerkarte verwenden eigene
Leseports. Nur noch aktive fällige Transporte ergänzen die Offline-Rangliste.
Öffentliche Verkehrsdaten enthalten keine Guthaben, Kosten oder Zugangsdaten.
TrafficReader liefert unveränderliche SharedTransport-Werte mit Koordinaten.
Spielerfarben, Eigentumsmarkierung und GeoJSON entstehen erst in der API-
Projektion; ein zusätzlicher durchreichender Mehrspieler-Service entfällt.

## Referenzwelt und Markt

WorldCatalogue 4.0.0 liefert gemeinsame Country-/City-Objekte. Facility
komponiert Address und Coordinates. Company bleibt unabhängig von einer Stadt.
Immutable World-/Country-/City-/Company-Scopes filtern Facilities. Mehrdeutige
Namen werden abgewiesen; UUIDs und gepflegte Legacy-Aliase sind eindeutig.

CachedWorldCatalogue besitzt eine validierte unveränderliche Revision pro
Prozess. MarketGenerator hält daraus abgeleitete NHM-Handelsoptionen; seine
Invalidierung vergleicht Referenzwerte und nicht lediglich Standort-IDs.
NhmProduct beschreibt Kategorie und Hierarchie, FacilityNhmProfile die
standortbezogene Rolle und Evidenz. DocumentedGood bleibt ein Quellenbeleg.

MarketScopeResolver umfasst eigene idle Fahrzeuge und ab Zoom 7 zusätzliche
Facilities im Kartenbereich. MarketGenerator kennt keinen Viewport und erzeugt
Aufträge ausschließlich für die übergebenen Origins. Mengenklassen folgen den
Nutzlasten aus Fahrzeugkatalog und Bestand. Reale Fakten und Simulation bleiben
getrennt; siehe [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md).

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

ContractMarketController besitzt die bedarfsabhängigen Marktanfragen; die Karte
liefert nur neutrale Zoom-/BBox-Werte. Standortmarker entstehen aus eigener
Flotte, Transport-Snapshots und der aktuellen Auftragsscheibe. Spielerfarben
und öffentliche Transporte bleiben von privaten Wirtschaftsangaben getrennt.
World Wrapping, Clustering, Tastatur, mobile Panels und Reduced Motion bleiben.

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
