# Externe Provider

## Betriebsgrenzen und Quellen

Der Backend-Geocoder dient Offline-Enrichment und begrenztem Anchor-Repair.
Nominatim-Anfragen sind maximal einmal pro Sekunde zulässig; der Adapter verwendet
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

Zweck: Kandidatensuche für Offline-Enrichment und begrenzten Backend-Anchor-Repair. Vor Freigabe sind
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
- `endpoint_mismatch`: der Verbindungsprüfer erkennt einen tatsächlichen
  Geometrie-Endpunkt über 10 Meter vom vorgesehenen Anker entfernt.

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

## Valhalla Locate für Truck-Routing-Anker

Der Backend-Adapter `ValhallaTruckAnchorLocator` verwendet `POST /locate`
mit `costing=truck` und `verbose=true`. Laut Valhalla-OpenAPI basiert
`LocateRequest` auf `BaseRequest`, dessen `costing` den Wert `truck`
unterstützt. Die korrelierte Position wird aus den zurückgegebenen
`edges[].correlated_lat` / `edges[].correlated_lon` gelesen. Referenz:
https://github.com/valhalla/valhalla/blob/master/docs/docs/api/openapi.yaml

Locate liefert Kandidaten, keinen Verbindungsnachweis. Die Anwendung berechnet
deren Entfernung stets von der ursprünglichen Facility-Koordinate, auch nach
Adress-Fallback. `ROUTING_ANCHOR_MAX_SNAP_M` hat den Default und die Obergrenze
1000 Meter. Verschachtelte Truck-Zugriffe (`edges[].edge.access.truck`) werden
ausgewertet. Eine Provider-/Graph-Revision wird nur gespeichert,
wenn Valhalla sie tatsächlich in bekannten Response-Headern liefert.

Kann die Facility-Koordinate nicht als Truck-Anker verwendet werden, darf der
bereits vorhandene gecachte und rate-limitierte `NominatimGeocoder` die
gespeicherte Facility-Adresse backendseitig auflösen. Dieser Kandidat muss
erneut `/locate` bestehen. Der Browser geocodiert nicht.

Je Facility werden über beide Suchphasen höchstens fünf unterschiedliche
Kandidaten geprüft. Der injizierte Verbindungsprüfer verlangt echte Truck-Routen
in beiden Richtungen; alle vier Geometrie-Endpunkte müssen innerhalb 10 Metern
der vorgesehenen Anker liegen. Maximal 25 Paare und 120 Sekunden einschließlich
Limiter; erfolgreiche aktuelle Anker bleiben bevorzugt stabil. Erst dann werden
Anker, beide Richtungen und gemeinsamer Nachweis atomar gespeichert.


## Vorbereitung und Betriebsbudget

Nominatim: seriell, mindestens 1,05 Sekunden; kein Browser-Geocoding.
Valhalla: eigener injizierter Limiter, `VALHALLA_CONCURRENCY=1` und
`VALHALLA_MINIMUM_INTERVAL=1` als konservative Defaults. Route und Locate teilen
sein Budget. Retry-After verschiebt weitere Providerrequests. Für eigene
Instanzen können die Limits ohne Codeänderung angepasst werden.

`python scripts/audit_routing_readiness.py --report` führt keine Providerrequests
aus. `--prewarm --request-limit 100` ist explizit und resumierbar über persistierte
Readiness. Am öffentlichen Default-Endpunkt ist zusätzlich
`--allow-public-endpoint` erforderlich; eine Warnung benennt dessen Testzweck.
Der Requestzähler zählt Route, Locate und Geocoding gemeinsam. Vollständiger
globaler Prewarm ist für eine eigene Valhalla-Instanz vorgesehen.

Die Limiter sind pro Runtime-/CLI-Instanz geteilt. Für mehrere OS-Prozesse gegen
einen öffentlichen Dienst ist zusätzlich ein gemeinsamer externer Limiter
beziehungsweise ein eigener Routingdienst erforderlich; SQLite-Leases
verhindern doppelte Relationsarbeit, aggregieren aber keine Provider-Rate.
Graphwechsel werden über tatsächlich gelieferte `x-graph-revision`-Header,
sonst `x-valhalla-version`, beobachtet. Fehlende Header erfinden keine Revision
und invalidieren keine Route fortlaufend. Ein nicht angekündigter Graphwechsel
ist ohne Provider-Metadaten nicht sofort erkennbar. Erfolgreiche Nachweise gelten
deshalb höchstens 24 Stunden. Definitive Fehler werden nach einer Stunde,
temporäre Störungen und ausgeschöpftes Reparaturbudget nach 60 Sekunden wieder
vorbereitbar. Der Worker reagiert auf Nachfrage; Details und Abnahme:
[Verbindungsprüfung](CONNECTED_ROUTING_REVIEW.md).
