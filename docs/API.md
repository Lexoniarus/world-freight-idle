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

Liefert eine kompakte Projektion für die Startseite: Spielerwerte, Anzahl verfügbarer Aufträge, freie Fahrzeuge, aktive Transporte und drei Auftragsvorschläge.

## Aufträge

### `GET /contracts`

Liefert den aktuellen Markt mit realen Endpunktadressen.

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

Erzeugt einen neuen NHM-basierten Auftragsmarkt über die spielbaren Facilities.

## Flotte

### `GET /fleet`

Liefert alle Fahrzeuge inklusive aktuellem realen Hub.

### `GET /fleet/{vehicle_id}`

Liefert ein Fahrzeug.

## Transporte

### `GET /transports`

Liefert aktive Transporte.

### `GET /transports/{transport_id}`

Liefert Route, Start-/Zielpunkt, Departure/Arrival-Timestamps und Economics für das Live-Tracking.

## System

### `GET /system/health`

Zeigt konfigurierte Provider und API-Version, ohne externe Requests auszulösen.

## Fehlerkonvention

- `400` – Domain-/Validierungsfehler
- `404` – Ressource nicht vorhanden
- `422` – ungültiges Request-Schema
- `502` – Routing-/Providerfehler
- `503` – benötigter Referenzkatalog fehlt oder ist inkompatibel

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
der anschließende Flottenabruf ergänzt das Foto.

Neue Spielstände: kostenloser `iveco_sway_500`, ID `truck_01`, 175.000 Euro.
Das Konto und die Sitzung sind von der atomaren Spielinitialisierung getrennt.
Ist der Startkatalog beim ersten Spielabruf nicht verfügbar, folgt HTTP 503;
nach Wiederherstellung genügt ein neuer Abruf. Bestehende Fahrzeuge bleiben
nutzbar. Es gibt keine allgemeine automatische Altflotten-/Guthabenmigration.

Aufträge werden je routbarer Facility und belegter Nutzlastklasse aus dem
Fahrzeugkatalog ergänzt. Auch kleine Transporter und bestehende Fahrzeuge
erhalten geeignete Mengen; `payload_band` ist simuliert, reale Warenbelege
bleiben getrennt. Mengenregeln und Kompatibilität: [WorldCatalogue](WORLD_CATALOGUE.md).
