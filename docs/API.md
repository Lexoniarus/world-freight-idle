# API v1

Basis: `/api/v1`

## Authentifizierung und Schreibzugriffe

Private Ressourcen verlangen das HttpOnly-Cookie `freight_session`.
Alle mutierenden Requests benötigen `X-Freight-Request: 1`. Ein vorhandener
`Origin` muss dem Server-Origin entsprechen. Keine CORS-Freigabe.
Auch beim Testen über OpenAPI/curl muss der Schreibheader gesetzt werden.

| Methode | Pfad | Funktion |
| --- | --- | --- |
| POST | `/auth/register` | `{username, password}`: Konto und Sitzung, 201 |
| POST | `/auth/login` | `{username, password}`: Sitzung rotieren |
| POST | `/auth/logout` | Sitzung serverseitig widerrufen |
| GET | `/auth/me` | eigene ID und öffentlicher Spielername |
| GET | `/fleet/catalogue` | Fahrzeugmodelle und simulierte Preise |
| POST | `/fleet/purchase` | `{model_id}`: atomarer Kauf, 201 |
| GET | `/leaderboard` | Top 100: Namen und abgeschlossene Lieferungen |
| GET | `/map/facilities` | Spielbare öffentliche Facilities mit Verifikationsstatus, optional bbox |
| GET | `/map/hubs` | Kompatibles hubs-Envelope derselben Facilities, kein Geocoding |

Spielername: ASCII-Buchstaben, Ziffern, Unterstrich, 3–24 Zeichen;
Passwort: 12–128 Zeichen. Sitzungen laufen nach sieben Tagen ab.
Registrierung und Anmeldung teilen 30 Versuche je Client-IP pro 15 Minuten.
401 ohne gültige Sitzung, 403 bei CSRF-Verletzung, 409 bei vergebenem Namen,
422 bei ungültiger Eingabe, 429 bei überschrittenem Login-Limit.
Fremde Ressourcen-IDs liefern 404. Kein öffentlicher Reset-Endpunkt.

Spielaktionen verwenden ausschließlich diese API. Geocoder, Router und SQLite
sind keine öffentlichen Schnittstellen. Die Hintergrundkarte lädt ihre Tiles
direkt vom konfigurierten Kartenanbieter.

GET /map/facilities liefert `facilities`, `catalogue_version` und
`unavailable_count`. Verifizierte und ausdrücklich geschätzte Simulationskoordinaten werden mit ihrem Status ausgeliefert.
`bbox=west,south,east,north` unterstützt die Datumsgrenze (west > east),
weist ungültige Werte mit 422 ab und ist optional. Ohne Sitzung 401;
Katalogausfall 503. Numerische SQLite-PKs sind nicht öffentlich.
GET /map/hubs liefert weiterhin {"hubs": [...]} als Kompatibilitätsprojektion.
Beide Endpoints lösen keine Geocoding-Aufrufe aus. Projektionen und Migration:
[WorldCatalogue](WORLD_CATALOGUE.md).

## Dashboard

### `GET /dashboard`

Liefert Spielerwerte, freie Fahrzeuge sowie Fahrzeuge und aktive Transporte
mit Serverzeit und Zeitfaktor. Der Dashboardabruf erzeugt keinen globalen Markt:
`available_contracts` bleibt als kompatibles Feld 0, `featured_contracts` leer.
Den bedarfsabhängigen Markt lädt der Client gesondert über `/contracts`.

## Aufträge

### `GET /contracts`

Liefert den bedarfsabhängigen Markt mit gespeicherten Endpunktadressen.
Optional: `bbox=west,south,east,north` und `zoom`. Origins eigener freier
Fahrzeuge sind immer enthalten; ab Zoom 7 kommen spielbare Facilities im
Kartenbereich hinzu. Ohne Viewport entsteht kein globaler Markt. Ungültige
Bounding Boxes ergeben 422; die Datumsgrenze wird unterstützt.

### `GET /contracts/{contract_id}`

Liefert ein Auftragsdetail.

### `POST /contracts/{contract_id}/quote`

Führt den externen Datenpfad aus:

`gespeicherter Facility-Snapshot → Valhalla truck → Route → Pricing`

Ohne erfolgreiche Providerroute gibt es kein Angebot.

### `POST /contracts/{contract_id}/accept`

Body:

```json
{"vehicle_id": "truck_01"}
```

Validiert Fahrzeugstatus, Modus, Standort, Kapazität und Liquidität. Bei Erfolg wird ein persistenter Transport erzeugt.

### `POST /contracts/refresh`

Erneuert den NHM-basierten Markt für denselben Fahrzeug-/Viewport-Scope
wie `GET /contracts`; dieselben optionalen `bbox`-/`zoom`-Parameter gelten.

## Flotte

### `GET /fleet`

Liefert alle Fahrzeuge mit gespeichertem Facility-Standort. `hub_id` bleibt
ein kompatibler Name für die Facility-UID; öffentliche Facilities sind keine Depots.

### `GET /fleet/{vehicle_id}`

Liefert ein Fahrzeug.

## Transporte

### `GET /transports`

Liefert aktive Transporte.

### `GET /transports/{transport_id}`

Liefert einen eigenen aktiven Transport mit Route, Endpunkten, Zeitpunkten
und Kalkulation. Abgerechnete Transporte bleiben gespeichert, sind über
diese aktive Ansicht aber nicht mehr abrufbar (404).

## Öffentlicher Live-Verkehr

### `GET /map/traffic`

Authentifizierte, accountübergreifende Kartenprojektion aktiver Transporte:
öffentlicher Spielername, Fahrzeugdarstellung, Route, Zeiten und Spielerfarbe.
Private Guthaben, Verträge, Kosten und Auszahlungen werden nicht veröffentlicht.
Ein fremder Transport kann nicht über private Detailendpoints geöffnet werden.

## System

### `GET /system/health`

Zeigt konfigurierte Provider und API-Version, ohne externe Requests auszulösen.

## Fehlerkonvention

- `400` – Domain-/Validierungsfehler
- `404` – Ressource nicht vorhanden
- `422` – ungültiges Request-Schema
- `502` – Routing-/Providerfehler
- `503` – benötigter Referenzkatalog oder Spielstand ist nicht verfügbar;
  interne SQL-Fehler, Dokumente und lokale Pfade werden nicht ausgeliefert

Jeder HTTP-Request erhält `X-Trace-Id` in der Response.

## Fahrzeugkatalog und fahrzeugbezogene Quotes

`GET /fleet/catalogue` behält `models` und `delivery_hub`. Modelle enthalten
`id`, `name`, `mode`, `capacity_tons`, `price_eur`, `manufacturer`, `powertrain`,
`unlock_reputation` und `operating_cost_eur_per_km`; sortiert nach Preis und ID.
`POST /fleet/purchase` prüft Reputation/Guthaben serverseitig und speichert
Fahrzeugwerte atomar. Unbekanntes/gesperrtes Modell: 400. Katalogfehler: 503.

`POST /contracts/{id}/quote` akzeptiert optional `{"vehicle_id":"..."}`.
Mit ID werden Besitz, Standort, Kapazität, Modus und Verfügbarkeit geprüft;
ungültige Fahrzeugauswahl ergibt 400. Ohne Body/ID bleibt die allgemeine
Vorschau mit 0,62 €/km erhalten. Antworten ergänzen `vehicle_id` (ggf. null)
und `operating_cost_eur_per_km`. Kosten: `round(80 + km * Satz)`.
`accept` berechnet Kosten für das gewählte Fahrzeug erneut auf dem Server.
Negative/nicht endliche Strecken oder Zeiten und ungültige Geometrien erzeugen
502 statt eines verwendbaren Angebots. Produkt-URLs bleiben unverändert.


### Optionale Fahrzeugfotos und Startprofil

Katalogmodelle und `GET /fleet` bzw. `GET /fleet/{id}` enthalten zusätzlich
`image`: entweder null oder `{url, source_url, author, license_name,
license_url, attribution, scope}`. Nur verifizierte HTTPS-Metadaten werden
angeboten. `scope=model_family` bezeichnet ein Beispielfoto, keine Zusage der
exakten Variante. Bei fehlendem Katalog liefert die Flottenansicht weiterhin
die gespeicherten Fahrzeuge mit `image=null`. Kaufantworten bleiben kompatibel;
der anschließende Flottenabruf ergänzt die Fotometadaten. Die Oberfläche
bevorzugt für bekannte Modelle lokale SVGs über `getVehicleAssets(modelId)`;
die HTTP-Bildmetadaten werden dadurch nicht verändert.

Neue Spielstände: kostenloser `iveco_sway_500`, ID `truck_01`, 175.000 Euro.
Das Konto und die Sitzung sind von der atomaren Spielinitialisierung getrennt.
Ist der Startkatalog beim ersten Spielabruf nicht verfügbar, folgt HTTP 503;
nach Wiederherstellung genügt ein neuer Abruf. Bestehende Fahrzeuge bleiben
nutzbar. Es gibt keine allgemeine automatische Altflotten-/Guthabenmigration.

Aufträge werden je routbarer Facility und belegter Nutzlastklasse aus dem
Fahrzeugkatalog ergänzt. Auch kleine Transporter und bestehende Fahrzeuge
erhalten geeignete Mengen; `payload_band` ist simuliert, reale Warenbelege
bleiben getrennt. Mengenregeln und Kompatibilität: [WorldCatalogue](WORLD_CATALOGUE.md).

## Domain- und Persistenzgrenze

HTTP-Projektionen entstehen unter `app/api/v1`, unabhängig von den versionierten
Persistenzdokumenten. Bestehende Felder wie `hub_id`, `origin_hub_id` und
`destination_hub_id` bleiben Projektionen der Facility-UID. Standortprojektionen
enthalten zusätzlich die dauerhaft gespeicherte `city_uid`; numerische
Katalogschlüssel werden nicht zu öffentlichen Identitäten.

Übernommene Transporte behalten ihre historischen Standort- und Warenangaben.
Bei älteren dokumentierten Waren können NHM-spezifische Felder null sein; eine
nachträgliche NHM-Zuordnung wird nicht behauptet. Vollständige Quellen und
Handling-Nachweise bleiben in den historischen Repository-Snapshots erhalten;
die öffentliche Standortprojektion bleibt kompakt.

Der normale Server akzeptiert ausschließlich das relationale Spielstandschema.
Der Offline-Importer ist kein Endpoint und wird nicht beim Start ausgeführt.
Nach dem KV-Altformatimport ist eine erneute Anmeldung erforderlich, weil dieser
Sessions nicht übernimmt. Das separate Energie-Upgrade von Schema 1.0.0 nach
1.1.0 bewahrt dagegen vorhandene Sessions. Beide Werkzeuge bleiben offline.


## Fahrzeugenergie und Fahrtpläne

Katalog und Flotte ergänzen `energy` (kind, unit, capacity,
consumption_per_100km, stop_minutes, reserve_fraction) und `top_speed_kmh`.
Eigene Fahrzeuge liefern `energy_level` für den Zeitpunkt der Abfrage; während
einer Fahrt wird dieser Wert aus dem unveränderlichen Fahrtplan berechnet.

Fahrzeugquotes ergänzen `journey`, `energy_consumption`, `energy_stop_count`,
`driving_seconds`, `pause_seconds` und `total_duration_seconds`. Die drei neuen
Dauern sind bereits mit dem Spielzeitfaktor skaliert. `duration_seconds` bleibt
die unveränderte Valhalla-Fahrzeit. Ohne Fahrzeug sind die Planungsfelder null.

Eigene Transporte enthalten den gespeicherten Plan sowie zeitabhängiges
`progress` (Phase, Entfernung, Bruchteil, Energiestand, Phasenrestzeit).
Intervalle verwenden Zeiten relativ zur Abfahrt. Die öffentliche Karte bekommt
unter `journey` nur Entfernung sowie Phasen-, Zeit- und Streckenintervalle;
keine Energieinhalte, Verbrauchsprofile, Auftrags- oder Wirtschaftsdaten.
