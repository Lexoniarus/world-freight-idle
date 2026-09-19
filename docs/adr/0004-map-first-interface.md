# ADR 0004 – UI First und providerunabhängige Weltkarte

Status: Entscheidung vom 18.09.2026 umgesetzt; ersetzt die frühere
Satelliten-Pflicht für M1. Gesamt-M1 inklusive Unternehmen/Depots bleibt offen.

## Entscheidung

Zuerst die Oberfläche auf dem bestehenden Backend fertigstellen.
MapLibre GL JS rendert die OSM-Standardkarte. Satellitenbilder folgen später.
Ein BasemapProvider kapselt Style, Tiles, Attribution und Zoomgrenzen.
Ein zukünftiger SatelliteTileProvider erfüllt dieselbe Schnittstelle.

Native ES-Module und Vite bündeln Worker, Bibliotheken und Schriften lokal.
FastAPI liefert die Build-Assets aus. main.py bleibt der Laufzeit-Einstieg;
Node wird für den vorherigen Build benötigt. Docker nutzt eine Node-Build-Stufe.

Die Karte bleibt bei Aufträgen, Flotte, Shop, Transporten und Rangliste erhalten.
History API und bestehende URLs erlauben Deep Links und Zurück/Vorwärts.
Mobil dienen Bottom Sheets mit veränderbarer Höhe als Kontextpanels.
Tastatur und Reduced Motion werden unterstützt.

## Daten und Verantwortlichkeiten

Geld, Besitz, Aufträge und Ankünfte bleiben serverseitig. Das Frontend
interpoliert nur die Anzeige aus Route und Serverzeit. GeoJSON-Layer für
Fahrzeuge, Routen, Frachtstandorte und Aufträge sind getrennt. Firmen-/Depot-
Quellen bleiben leer, bis Backend-Daten existieren. Öffentliche Hubs sind
keine eigenen Depots.

GET /api/v1/map/facilities verwendet den read-only WorldCatalogue mit
BBox-Filter; /map/hubs bleibt kompatibel. Kein normaler Geocoding-Aufruf.
Ungeprüfte Endpunkte werden gezählt, nicht als routbare Marker ausgegeben.

OSM-Tiles werden direkt durch den Browser mit dauerhafter Attribution geladen.
Providerkonfiguration und Nutzungsgrenzen stehen in MAP_PROVIDERS.md.
Es gibt keine Bindung an MapTiler oder einen Satellitenanbieter.

## Abnahme

Unit-Tests sichern Zeitoffset, Abfragekoordination, verspätete Antworten,
Datumsgrenzen-Routen und Dispatch-Voraussetzungen. Browsertests prüfen den
Spielablauf auf 1440 × 900 und 390 × 844 mit isolierter Datenbank und lokalen
Tiles. Echte Provider werden nur in einer begrenzten manuellen Prüfung genutzt.
