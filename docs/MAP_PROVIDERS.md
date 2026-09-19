# Kartenrenderer und Basiskarten

## Verbindliche M1-Entscheidung: OSM statt Satelliten

MapLibre GL JS 6.10.0 rendert die interaktive Karte mit horizontalem World
Wrapping. Der BasemapProvider erzeugt Rasterquellen, Darstellung, Attribution
und Zoomgrenzen. Spiellayer haben eigene GeoJSON-Quellen. WorldCatalogue-Koordinaten
und Valhalla-Truck-Routing bleiben unabhängig von der Hintergrundkarte.

Standard für lokale Entwicklung:

- Tiles: https://tile.openstreetmap.org/{z}/{x}/{y}.png
- Quelle: OpenStreetMap Standard, Raster, 256 Pixel, maximal Zoom 19.
- Attribution: © OpenStreetMap, dauerhaft sichtbar mit Copyright-Link.
- Keine API-Schlüssel oder Abonnements erforderlich.
- Straßen, Gebäude und POIs erscheinen je nach Zoom und OSM-Erfassungsstand.
- Hintergrund-POIs sind keine automatisch spielbaren Unternehmen.

Der öffentliche Tile-Dienst ist Best Effort ohne SLA und kein zugesagter
Produktionsdienst. Für größeren öffentlichen Betrieb einen geeigneten
vertraglichen oder selbst betriebenen Tile-Dienst konfigurieren.

## Austauschbare Konfiguration

Vite liest beim Build aus frontend/.env.local bzw. aus Umgebungsvariablen:

| Variable | Standard |
| --- | --- |
| VITE_MAP_TILE_URL | öffentliche OSM-URL oben |
| VITE_MAP_ATTRIBUTION | HTML-Link auf OSM Copyright |
| VITE_MAP_MAX_ZOOM | 19 |

Nach einer Änderung npm run build ausführen. Attribution ist eine
vertrauenswürdige Deployment-Einstellung, keine Nutzereingabe.
Keine geheimen API-Schlüssel in VITE_-Variablen speichern.

Ein zukünftiger SatelliteTileProvider kann dieselbe Schnittstelle nutzen.
Satellitenbilder sind nach M1 vorgesehen; Anbieter, Lizenzen und Kosten
müssen dann konkret geprüft werden.

## Nutzung und Fehler

Es gelten die [OSM Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/)
und [Attributionsregeln](https://www.openstreetmap.org/copyright).
Browserabrufe senden einen Referer durch strict-origin-when-cross-origin.
Keine internen API-Header, Zugangsdaten oder Cache-Busting-Parameter werden
an Tile-Dienste geschickt. Der Browser beachtet die Cache-Header des Dienstes.
Kein Tile-Prefetching, kein Offline-Download und kein automatisiertes Abfahren
öffentlicher Tiles. Automatisierte Browsertests ersetzen alle OSM-Tiles
durch lokal erzeugte PNGs.

Bei Kartenfehlern bleiben Spielaktionen verfügbar, während ein Hinweis
erscheint. Nicht auflösbare Standorte erhalten keine Ersatzkoordinaten.
