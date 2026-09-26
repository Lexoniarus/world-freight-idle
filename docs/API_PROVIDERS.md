# Externe Provider

## Betriebsgrenzen und Quellen

Der Spielserver erzeugt keinen Geocoder. Beim Offline-Enrichment gelten für Nominatim-
Anfragen sind maximal einmal pro Sekunde zulässig; der Adapter verwendet
1,05 Sekunden Mindestabstand und persistentes Caching. Bei mehreren Workern
ist ein verteilter Limiter oder ein eigener Dienst erforderlich.
Einen identifizierenden User-Agent mit Kontakt konfigurieren.

- [Nominatim-Richtlinie](https://operations.osmfoundation.org/policies/nominatim/)
- [Valhalla-API](https://valhalla.github.io/valhalla/api/turn-by-turn/api-reference/)
- [OpenStreetMap-Attribution](https://www.openstreetmap.org/copyright)
- [scrypt in Python](https://docs.python.org/3/library/hashlib.html#hashlib.scrypt)
- [Cookie-API](https://starlette.dev/responses/#set-cookie)

Eurostat, UN Comtrade und reale Fahrzeugpreise sind noch nicht angebunden.

## Nominatim / OpenStreetMap

Zweck: Offline-Kandidatensuche für Import/Enrichment. Vor Freigabe sind
Identität, Quelle und Genauigkeitsklasse gesondert zu prüfen. Die normalen
Facility-Lookups verwenden gespeicherte Koordinaten aus dem WorldCatalogue.

Konfiguration:

- `NOMINATIM_URL`
- `HTTP_USER_AGENT`

Der öffentliche OSMF-Dienst ist nur für kleine Nutzung gedacht. Der Offline-Adapter cached jede Adresse dauerhaft und limitiert Requests seriell. Für Produktion muss ein eigener oder kommerzieller Geocoder verwendet werden.

## Valhalla / OpenStreetMap

Zweck: echte Straßenroute, Distanz, ETA und Routengeometrie für Trucks.

Konfiguration:

- `VALHALLA_URL`
- `VALHALLA_CLIENT_ID`

Der Request verwendet `costing="truck"`. Der öffentliche FOSSGIS-Demo-Server eignet sich für Entwicklung und kleine Tests; Produktion sollte einen eigenen Routing-Service verwenden.

### Routing-Fehlergrenze

Valhalla-spezifische Fehlercodes und Meldungstexte werden ausschließlich im
Provider-Adapter ausgewertet. Nach außen verlässt den Adapter nur ein
`RoutingError` mit einer providerunabhängigen Kategorie:

- `endpoint_unreachable`: Start oder Ziel lässt sich nicht sinnvoll an das
  Straßennetz anbinden.
- `no_path`: Endpunkte sind unverbunden oder es wurde kein Straßenpfad gefunden.
- `distance_limit`: die angefragte Route überschreitet das Routing-Limit.
- `provider_unavailable`: HTTP-, Timeout- oder sonstige Providerstörung.
- `invalid_response`: eine erfolgreiche Providerantwort ist strukturell
  unbrauchbar.

Der Adapter ordnet die dokumentierten Valhalla-Codes `171` und `441`
`endpoint_unreachable`, `170` und `442` `no_path` sowie `154`
`distance_limit` zu. Bekannte Meldungstexte dienen zusätzlich als Fallback,
weil diese Fälle denselben HTTP-Status verwenden können.

Soweit Valhalla sie liefert, bleiben `error_code` und `error` als interne
Diagnosedaten am Fehler erhalten; zusätzlich kennzeichnet `retryable`, ob ein
erneuter Provider-Versuch sinnvoll sein kann. Diese Providerdetails werden
nicht über die öffentliche Contract-API ausgegeben. Fehlerantworten werden
nicht in den Route-Cache geschrieben; erfolgreiche Routen und Cache-Dokumente
bleiben unverändert.

## Natural Earth / world-atlas

Zweck: Weltumrisse für die flächentreue Hintergrundkarte. Die Spielroute selbst kommt nicht aus dieser Quelle.
