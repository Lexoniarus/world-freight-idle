# Externe Provider

## Betriebsgrenzen und Quellen

Ein Prozess teilt einen Geocoder über alle Konten. Öffentliche Nominatim-
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

Zweck: Umwandlung der festen MVP-Postadressen in Koordinaten.

Konfiguration:

- `NOMINATIM_URL`
- `HTTP_USER_AGENT`

Der öffentliche OSMF-Dienst ist nur für kleine Nutzung gedacht. Das MVP cached jede Adresse dauerhaft und limitiert Requests seriell. Für Produktion muss ein eigener oder kommerzieller Geocoder verwendet werden.

## Valhalla / OpenStreetMap

Zweck: echte Straßenroute, Distanz, ETA und Routengeometrie für Trucks.

Konfiguration:

- `VALHALLA_URL`
- `VALHALLA_CLIENT_ID`

Der Request verwendet `costing="truck"`. Der öffentliche FOSSGIS-Demo-Server eignet sich für Entwicklung und kleine Tests; Produktion sollte einen eigenen Routing-Service verwenden.

## Natural Earth / world-atlas

Zweck: Weltumrisse für die flächentreue Hintergrundkarte. Die Spielroute selbst kommt nicht aus dieser Quelle.
