# Datenquellen und Simulationsgrenzen

Technische Providerdetails: [API_PROVIDERS.md](API_PROVIDERS.md).
Geplante Satellitenbilder: [MAP_PROVIDERS.md](MAP_PROVIDERS.md);
aktuell noch kein Satellitenprovider integriert.

| Daten | Aktuelle Quelle | Verwendung / Grenze |
| --- | --- | --- |
| Hub-Adressen | `app/seed_data.py` | kuratierte reale Adressen; vier Hubs |
| Koordinaten | Nominatim / OpenStreetMap | adressbezogenes Geocoding, Cache |
| Lkw-Straßenroute | Valhalla / OpenStreetMap | Geometrie, Kilometer und Fahrzeit |
| Basiskarte | OpenStreetMap Standard via MapLibre GL JS | Rastertiles; Straßen, Orte, Gebäude und POIs; keine Routingquelle |
| Fahrzeugmodelle | `data/world_freight_vehicle_catalog.sqlite3`, Schema 2.0.0 | acht Modelle, sieben Hersteller, technische Quellen in `sources`/`vehicle_sources` |
| Fahrzeug-Spielwerte | `vehicle_balance` im Katalog | fiktive Preise, Nutzlast, Reputation und Kilometerkosten; keine realen Angebote |
| Firmen und Aufträge | eigener Generator | vollständig fiktive Einzelereignisse |
| Vergütung / Betriebskosten | PricingService | balanciertes Spielmodell |

Eurostat, GLEIF, FAF, UN Comtrade, OurAirports und SeaRoute sind mögliche
spätere Quellen aus GOAL.md; keine davon ist aktuell angebunden.
Vor einer Integration: Quelle, Nutzungsbedingungen, Datenstand, Lizenz,
Aktualisierung, Fehlerverhalten und interne Normalisierung dokumentieren.

OSM-Attribution ist bei der Karte verlinkt. Ein Providerfehler bleibt ein
sichtbarer Fehler; das Spiel erfindet keine Ersatz-Straßenroute.
Cache-Einträge besitzen Zeitstempel, derzeit aber keine automatische TTL-
Invalidierung. Für Fahrzeugprofile und Bilder sind Herkunfts-/Lizenzmetadaten im Katalog
vorhanden. Verifizierte Fotos werden direkt von Wikimedia geladen. Quelle, Urheber, Lizenz
und Bildbezug (z. B. Modellfamilie statt exakter Variante) bleiben sichtbar.
Bei ungültigen Metadaten oder Ladefehlern bleibt die Illustration als Ersatz. Andere Datenquellen besitzen noch keine durchgängigen
Herkunfts-/Lizenzmetadaten pro Datensatz.
