# Architektur

## UI-Zielarchitektur

UI First: Eine permanente MapLibre-Karte ist die Hauptansicht; Management
öffnet Kontextpanels. M1 verwendet OSM-Rastertiles. Ein BasemapProvider
liefert Style, URLs, Attribution und Zoomgrenzen; Satelliten folgen später.
Native ES-Module unter frontend/ trennen State, Darstellung, Karte und
Panels. Vite bündelt Bibliotheken, Worker und Schriften nach static/dist/.
FastAPI liefert denselben Einstieg für alle bestehenden Produkt-URLs.
History API erhält Deep Links und Zurück/Vorwärts ohne Karten-Neustart.

RefreshScheduler plant Polls alle 10 s nur bei sichtbarer Anwendung;
GameState bündelt überlappende Reads. Nach Mutationen wird ein frischer
Stand geladen. LatestRequest verhindert
veraltete Panel-/Quote-Antworten. Aus Serverzeit wird ein Client-Zeitoffset
ermittelt. Die gemeinsame Kartenanimation nutzt vorberechnete Routendistanzen
und unwrapped Längengrade. Gutschriften bleiben ausschließlich serverseitig.
Basiskarte und GeoJSON-Overlayquellen sind getrennt; leere Firmen-/Depot-
Layer sind Erweiterungspunkte, keine erfundenen Besitztümer.

GET /api/v1/map/facilities verwendet MapLocationService und WorldCatalogue.
Nur verifizierte Endpunkte mit passendem Nachweis sind routbar. /map/hubs
bleibt eine Kompatibilitätsprojektion; beide Pfade benötigen keinen Geocoder.
Keine künstlichen Ersatzkoordinaten. Kartenabrufe gehen direkt vom Browser
zum Tile-Anbieter, ohne Spiel-Header/Credentials. Referrer-Policy ist
strict-origin-when-cross-origin. Öffentliche Attribution bleibt sichtbar.

## Mehrspieler-Erweiterung

`main.py` ist der ausführbare Einstiegspunkt; `app/main.py` ist die FastAPI-
Composition-Root. `AuthService`/`PasswordHasher` und `AccountRepository`
verwalten Konten/Sitzungen. `FleetService` kapselt den Fahrzeugkauf.
`get_current_user` authentifiziert; `build_player_service` erzeugt den
Spielservice mit eigenem KV-Namensraum und gemeinsamem Router und unveränderlichen Referenzkatalogen.

Transporte sind eine Liste `active_trips`. Abrechnung erfolgt bei Zugriff
anhand serverseitiger Unix-Zeit; es ist kein dauerhaft laufender Timer nötig.
Die Rangliste berücksichtigt fällige Offline-Transporte ohne Schreibzugriff.
Transaktionsgrenzen und Migrationsentscheidung: ADR 0003.

## Ziel

Die Architektur trennt Produktoberfläche, HTTP-Contracts, Game-Orchestrierung, Domain-Logik, Persistenz und externe Provider. Kein Layer darf Abkürzungen durch einen anderen Layer nehmen.

```text
Browser Pages
    │
    ▼
/api/v1/*
    │
    ▼
GameService  ─────► MarketGenerator
    │              PricingService
    │
    ├────► WorldCatalogue Port ► SqliteWorldCatalogue (read-only)
    │
    ├────► TruckRouter Port ──► ValhallaTruckRouter ► Valhalla / OSM
    │
    └────► SqliteStore ───────► SQLite
```

## Modulgrenzen

### `app/api/v1`

Öffentliche HTTP-Schnittstelle. Verantwortlich für Request/Response, Statuscodes und Versionierung. Keine Game-Regeln.

### `app/services`

Anwendungslogik. `GameService` orchestriert, `MarketGenerator` generiert, `PricingService` kalkuliert. Providerdetails bleiben außerhalb.

### `app/providers`

Anti-Corruption-Layer zu externen Diensten. Providerantworten werden in interne Domainmodelle normalisiert.

### `app/repositories`

Persistenz und Caches. Keine Game-Regeln.

### `app/domain`

Provider- und Framework-unabhängige Datenmodelle.

### `frontend/api.js`

`GameApiClient` ist der einzige HTTP-Zugang zu Spielressourcen. Er setzt
Same-Origin-Credentials und CSRF-Header, lehnt Weiterleitungen ab und bricht
beim Beenden alle offenen Anfragen ab. MapLibre lädt Basiskarten separat.

### Frontend-Komponenten

`main.js` importiert Assets und startet `bootstrap.js`. Dort werden die
Komponenten und ihre externen Abhängigkeiten verbunden. `GameApplication`
koordiniert Start, Navigation, Logout und Aufräumen.

- `BrowserRouter`: History API und interne Navigation.
- `GameState`: vollständige Serversnapshots, Zeitoffset und Abfragebündelung.
- `GameActions`: benannte Use Cases für Quote, Kauf, Dispatch und Marktwechsel.
- `GameSync`/`RefreshScheduler`: HUD-Synchronisierung und sichtbarkeitsabhängige Timer.
- `PanelController`: Auswahl, Zusatzdaten, veraltete Antworten und Fokus.
- `views/`: eigenständige DOM-Darstellung je Spielfunktion, ohne HTTP-Zugriff.
- `MobileSheet`, `InputController`, `Notifications`: klar begrenzte UI-Zustände.
- `WorldMap`: Renderer-Lebenszyklus und Karteninteraktionen. `OverlayData`
  bereitet GeoJSON auf, `layers.js` definiert Darstellung, `MapCamera` führt
  die Kamera, `VehicleAnimator` besitzt genau eine Animationsschleife.

Reine Geometrie-, Zeit- und Formatfunktionen bleiben funktional. Der alte
D3-/Mehrseiten-Frontendbestand wurde entfernt; `static/` enthält nur die
gebauten Dateien und einen Verzeichnisplatzhalter. Produkt-URLs bleiben erhalten.

## Single Responsibility

- API-Funktion: genau ein Endpoint
- Provider-Methode: genau einen Providerprozess kapseln
- Service-Methode: genau einen Use Case orchestrieren
- Repository-Methode: genau eine Persistenzoperation
- Format-/Template-Funktion: genau eine Darstellungsaufgabe

## Abhängigkeiten

Abhängigkeiten zeigen nach innen. Services kennen Ports, nicht HTTP-Implementierungen. Die konkrete Verdrahtung erfolgt ausschließlich in `bootstrap.py` und `main.py`.

## Provider-Fehler und Verdrahtung

Geocoder-/Router-Ports sowie deren Fehler liegen unter `app/domain`.
Adapter normalisieren HTTP-, Verbindungs- und fehlerhafte Antwortdaten zu
`GeocodingError`/`RoutingError`. Services importieren keine konkreten
Provider und kein `httpx`. APIs übersetzen die Portfehler weiterhin nach 502.
Die Standortprojektion erhält bei Teilfehlern ihren `unavailable`-Status.

Fleet- und Map-Services werden über Builder in `app/bootstrap.py` erzeugt;
FastAPI-Dependencies lösen sie auf. Spielregeln, Transaktionsgrenzen,
Persistenzformat und öffentliche API-v1-Verträge bleiben unverändert.
Der vorhandene GameService bleibt der Orchestrator des aktuellen Core;
ein umfassender Backend-Domänenausbau ist keine Leistung dieser UI-Phase.

## Fahrzeugkatalog und Kalkulation

`VehicleCatalogue` ist ein Domain-Port; `SqliteVehicleCatalogue` liest die
separate Referenzdatei mit `mode=ro` und `PRAGMA foreign_keys=ON`. Verbindungen
werden pro Lesen geschlossen. Composition Roots injizieren den Katalog in
FleetService; das Repository validiert Daten, der Service prüft Kaufregeln.
Fehlerhafte Kataloge werden protokolliert und als HTTP 503 abgebildet.
Die Katalogdatei wird gezielt mit ausgeliefert; Spielstände bleiben ausgeschlossen.

Neue Fahrzeuge speichern Name, Modell-ID, Nutzlast und Kilometerkosten beim
Kauf. PricingService berechnet `round(80 + distance_km * cost_per_km)`;
Alt-/Startfahrzeuge ohne Kostensatz verwenden weiterhin 0,62 €/km. Die Erlösformel
bleibt unverändert. Transport-Snapshots bleiben nach ihrem Start unverändert.
Quotes können an eine Fahrzeug-ID gebunden sein; Dispatch kalkuliert selbst
und validiert nach dem Provider-Await erneut innerhalb der Transaktion.

Auch bei verlorenen Schreibantworten wartet die Synchronisierung ältere Polls
ab und liest anschließend frisch. Routen werden als zusammenhängende Geometrie
in die nächste Weltkopie verschoben; Flottenpunkte nutzen das kleinste kreisförmige
Längengradintervall. Ungültige Provider-Cachewerte werden nicht verwendet;
gültige neue Providerantworten können sie ersetzen. Es gibt keine erfundenen Routen.


### Fahrzeugbilder und Startausstattung

Der Composition Root injiziert den VehicleCatalogue-Port auch in GameService.
Die gemeinsame Servicevorlage erzeugt keinen globalen Spielstand; erst der
benutzerbezogene Aufbau initialisiert atomar die fehlenden Werte. Starter und
Kauf verwenden denselben Snapshot-Builder. Ein Katalogfehler lässt keine halbe
Startflotte zurück und wird beim authentifizierten Spielabruf als 503 übersetzt.
Bereits vorhandene Fahrzeuge werden ohne Katalogzugriff initialisiert.

SqliteVehicleCatalogue projiziert verifizierte Bild-/Quellen-/Lizenzdatensätze
auf VehicleImage. present_vehicles ergänzt ausschließlich Präsentationsdaten;
Spielwerte werden dadurch nicht verändert. Views binden DOM-Bildattribute,
InputController behandelt Load/Error und räumt seine Listener auf. Browser-
Bilderabrufe sind von GameApiClient getrennt; keine Backend-Header, Credentials
oder Referrer an die Bildquelle. Fehlerhafte optionale Bilder sperren keine Käufe.

Panelaktualisierungen gleichen den Inhalt optionaler Medien separat ab.
Unveränderte Fotos behalten ihre DOM-Knoten und ihren Lade-/Fehlerzustand,
auch wenn Status oder andere Panelinhalte wechseln. Neue URLs oder geänderte
Bildnachweise erzeugen neue Knoten. Das verhindert Flackern durch Polling.


### Reparatur der Standards-Grenzen (18.09.2026)

GameService.ensure_initial_state öffnet die Transaktion selbst und delegiert
an _ensure_initial_state. Der Spieler-Service-Builder verdrahtet und ruft die
öffentliche Methode auf; er muss deren Atomarität nicht mehr herstellen.
Reset umfasst Löschen und Neuinitialisierung weiterhin in einer Transaktion.

Der FastAPI-Lifespan registriert den Routing-HTTP-Client unmittelbar nach Erstellung
in einem AsyncExitStack. Client-/Service-/Accountaufbau und yield liegen innerhalb
dieses Scopes. Fehler beim Aufbau oder Schließen lassen weitere registrierte
Ressourcen nicht aus dem Cleanup fallen; Exceptions werden weitergegeben.

ProfileMaintenanceService erhält VehicleCatalogue, AccountRepository und eine
benutzerbezogene Store-Factory vom Composition Root. Er orchestriert Auswahl,
Validierung und atomare Speicherung. Modellübernahme und Nutzlastprüfung sind
separate Funktionen; sie verändern keine Fahrzeug-IDs, Standorte oder laufenden
Transport-Snapshots. Das CLI enthält weder SQL noch Spielregeln. Der SQLite-
Backupadapter gehört zu app/repositories und bewahrt auch committed WAL-Daten.

Während einer Routenabfrage kann eine ausdrücklich angeforderte Profilpflege
das Modell ändern. _commit_dispatch kalkuliert deshalb nach dem Await innerhalb
der Transaktion mit dem dann gültigen Fahrzeugkostensatz neu. Guthabenprüfung,
Abbuchung und neuer Transport verwenden dieselben Kosten. Bereits gestartete
Transporte behalten ihre gespeicherten Werte.

## WorldCatalogue und Bestandsmigration

[WORLD_CATALOGUE.md](WORLD_CATALOGUE.md) ist die verbindliche Ergänzung:
UUIDs statt SQLite-PKs, Domain-Referenzmodelle, dokumentierte Standardwaren,
Simulationswerte getrennt in app/simulation.py, vollständige Endpunktsnapshots.
Pflege- und Migrationsservices erhalten Ports; Repositories besitzen SQL,
Composition Roots die konkreten Adapter. Backup geht der Mutation voraus.
Auszahlung und anschließende Markterzeugung sind getrennte Transaktionen.
Nominatim ist nur noch ein Offline-Enrichment-Adapter. Der FastAPI-Lifespan
verwaltet ausschließlich den Routing-HTTP-Client über AsyncExitStack.
Produktionsimporte von Seed-Daten sind entfernt; Legacy-Testdaten liegen
unter tests/seed_data.py. Spielerunternehmen/eigene Depots bleiben offen.

Aufträge werden je routbarer Facility und belegter Nutzlastklasse aus dem
Fahrzeugkatalog ergänzt. Auch kleine Transporter und bestehende Fahrzeuge
erhalten geeignete Mengen; `payload_band` ist simuliert, reale Warenbelege
bleiben getrennt. Mengenregeln und Kompatibilität: [WorldCatalogue](WORLD_CATALOGUE.md).

## Read-only Multiplayer-Verkehrsprojektion

`MultiplayerMapRepository` liest ausschließlich Benutzer-ID, öffentlichen
Benutzernamen sowie die persistierten Fahrzeug-/Transport-Snapshots aus den
getrennten `user:<id>:`-Namespaces. `MultiplayerMapService` filtert bereits
abgelaufene Transporte und projiziert nur Transport-ID, Fahrzeug-ID, Modell-ID,
Route, Zeitfenster, öffentlichen Namen, Eigentümerflag und stabile Spielerfarbe.
Private Vertrags-, Kosten-, Erlös- und Kontodaten verlassen den Namespace nicht.

`GET /api/v1/map/traffic` benötigt weiterhin eine gültige Sitzung, ist aber im
Gegensatz zu Fleet-/Transport-Detailendpoints absichtlich accountübergreifend.
`GameState` lädt diese Projektion zusammen mit dem privaten Snapshot alle zehn
Sekunden. `OverlayData` hält private Routenlinien und öffentliche Fahrzeugmarker
getrennt. `VehicleIconRegistry` lädt jedes Brand-Free-SVG je Modell nur einmal
und erzeugt daraus bei Bedarf farbige MapLibre-Atlasbilder pro Spielerfarbe.
Die Position zwischen Polls wird weiterhin rein lokal aus Route und Serverzeit
interpoliert; es entstehen keine hochfrequenten Positionsschreibvorgänge.

## Read-only Multiplayer-Verkehrsprojektion V2

`MultiplayerMapRepository.list_active_transports()` verwendet SQLite JSON1, um
nur aktive Trip-ID, Vehicle-ID, Modell-ID/-name, Route, Zeitfenster sowie
öffentliche Account-ID und Benutzername zu projizieren. Vollständige private
`vehicles`-/`active_trips`-JSON-Objekte verlassen die Persistenzgrenze nicht.
`MultiplayerMapService` ergänzt ausschließlich stabile Spielerfarbe und das
`is_own`-Flag und schreibt ein strukturiertes `map.traffic.read`-Event mit
aggregierten Zählwerten.

`GameState.loadTraffic()` kapselt den optionalen Shared-Traffic-Read. Bei einem
Fehler bleibt der letzte gültige Traffic-Snapshot erhalten, gleichzeitig wird
`trafficAvailable=false` veröffentlicht. `GameSync` meldet Ausfall und
Wiederherstellung genau beim Zustandswechsel. Die Karte erhält weiterhin
modell- und farbspezifische MapLibre-Image-IDs. Eigene Fahrzeuge und
Fremdverkehr werden in getrennte GeoJSON-Quellen und MapLibre-Layer projiziert,
sodass der Layer-Schalter `Multiplayer-Verkehr` ausschließlich andere Spieler
ein- oder ausblendet. Zusätzliche Dekorationsringe werden nicht verwendet.
Die HTML-Anwendungsshell ist `no-store`, während gebaute Vite-Assets
weiterhin über ihre gehashten Dateinamen versioniert werden.

## Lokale Mehransichten für Flotte und Shop

`frontend/vehicle-card-assets.js` kapselt die Zuordnung aller 14 Modell-IDs zu
normalisierten lokalen Front- und Seitenansichten. Beide Dateien besitzen feste
transparente Referenzflächen und werden in `renderVehicleImage` in unabhängigen,
begrenzten Grid-Zellen dargestellt. Dadurch hängt ihre Geometrie nicht von der
ursprünglichen Generatorfläche ab und die Bilder können sich nicht überlagern.

Lokale Spielassets tragen bewusst kein `data-vehicle-photo` und keinen
`data-image-state`; diese Zustände gehören ausschließlich zu externen
Katalogfotos. `preserve-vehicle-images.js` bewahrt deshalb nur Remote-Fotos mit
explizitem Ladezustand. Die Flotten- und Shop-Views kennen weiterhin weder
Assetpfade noch Ladezustandslogik.

## Vollständige Fahrzeugkarten-Sprites

Die Map-Asset-Registry deckt alle 14 aktuellen Fahrzeugmodell-IDs ab. Die vier
zuletzt ergänzten Nutzfahrzeuge (IVECO Daily, Atego 818 L, Atego 1224 L und
MAN TGL) verwenden eigene Top-down-SVGs statt des generischen Punkt-Fallbacks.
Ihre SVG-Wrapper exponieren ebenfalls `--vehicle-color`, sodass
`VehicleIconRegistry` für sie denselben modell- und spielerfarbspezifischen
MapLibre-Atlaspfad wie für die bisherigen zehn Modelle verwendet. Der
Punkt-Fallback bleibt nur für Modell-IDs außerhalb des ausgelieferten Katalogs.

