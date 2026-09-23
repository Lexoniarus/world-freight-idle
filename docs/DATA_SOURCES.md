# Datenquellen und Simulationsgrenzen

Technische Providerdetails: [API_PROVIDERS.md](API_PROVIDERS.md).
Geplante Satellitenbilder: [MAP_PROVIDERS.md](MAP_PROVIDERS.md);
aktuell noch kein Satellitenprovider integriert.

| Daten | Aktuelle Quelle | Verwendung / Grenze |
| --- | --- | --- |
| Referenzunternehmen / Facilities / Adressen | `data/world_freight_company_facility_mvp.sqlite3`, Schema 3.0.0 | 83 Unternehmen, 155 Facilities; keine Spielerunternehmen |
| Koordinaten | gespeicherte Quellen und `facility_geocoding_evidence` | 352 routbar; 79 verifiziert, 273 ausdrücklich für die Simulation geschätzt |
| Lkw-Straßenroute | Valhalla / OpenStreetMap | Geometrie, Kilometer und Fahrzeit |
| Basiskarte | OpenStreetMap Standard via MapLibre GL JS | Rastertiles; Straßen, Orte, Gebäude und POIs; keine Routingquelle |
| Fahrzeugmodelle | `data/world_freight_vehicle_catalog.sqlite3`, Schema 2.0.0 | acht Modelle, sieben Hersteller, technische Quellen in `sources`/`vehicle_sources` |
| Fahrzeug-Spielwerte | `vehicle_balance` im Katalog | fiktive Preise, Nutzlast, Reputation und Kilometerkosten; keine realen Angebote |
| NHM-Waren und Facility-Verhalten | `nhm_codes`, `facility_nhm_profiles`, `facility_handled_goods_nhm` | 15.099 NHM-Codes; belegte und transparent derived IN/OUT/BOTH-Profile; keine generische Standardfracht |
| Beziehungen, Mengen und Aufträge | MarketGenerator, `app/simulation.py` | simulierte Einzelereignisse; DB-nutzlastabhängige Mengen, 0,18 €/km/t |
| Vergütung / Betriebskosten | PricingService | balanciertes Spielmodell |

Eurostat, GLEIF, FAF, UN Comtrade, OurAirports und SeaRoute sind mögliche
spätere Live-Quellen aus GOAL.md. Quellenreferenzen der gelieferten Datenbank
bleiben erhalten; ihre externen Live-APIs sind nicht angebunden.
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

## WorldCatalogue: aufbereiteter Referenzstand

Die gelieferte v2-Datei wurde nach SQLite-Backup auf v3 erweitert. UUIDs werden
einmalig gespeichert. Originalreferenzen und Bildmetadaten bleiben erhalten;
Facility-Fotos werden in dieser Phase nicht als UI-Funktion eingeführt.
Nominatim dient ausschließlich Kandidatensuche beim Offline-Enrichment.
Ein Treffer ersetzt weder Identitätsprüfung noch Koordinatennachweis.

Die vier Legacy-Facilities sind mit offiziellen Standort-/Tätigkeitsquellen
und gesonderten Koordinatennachweisen in
[legacy-facilities.json](data/legacy-facilities.json) dokumentiert:

| Facility | Koordinaten (Lat, Lon) | Geprüfter Nachweis |
| --- | --- | --- |
| Berlin Westhafen / BEHALA | 52.5374096, 13.3354466 | OSM way 137810028, Geländezentrum; offizieller BEHALA-Umschlaghinweis |
| HHLA Container Terminal Altenwerder | 53.5046363, 9.9328091 | OSM relation 8448069, Geländezentrum; HHLA-Terminalangaben |
| Duisburg D3T | 51.39595, 6.73296 | Koordinate aus offizieller D3T-Anfahrtsverlinkung |
| APM Terminals Maasvlakte II | 51.9506799, 4.0041828 | OSM way 599016100, Europaweg 910; offizielle APM-Terminalangaben |

OSM-Geometrien/-Koordinaten: © OpenStreetMap-Mitwirkende, ODbL;
[Attribution und Lizenz](https://www.openstreetmap.org/copyright). Offizielle
Webseiten belegen Fakten; deren Texte/Bilder werden dadurch nicht pauschal
freigegeben. Quell-URLs und Prüfdatum 18.09.2026 sind in den Datensätzen erhalten.
Der Datenstand ist eine kuratierte Referenz, kein Live-Nachweis aktueller
Geschäftsbeziehungen oder Wareneingänge. Keine allgemeine Freigabe fremder
Bilder/Marken und keine vollständige rechtliche Prüfung für öffentlichen Betrieb.
Technische Regeln und Migration: [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md).


Geografie-Normalisierung (Schema 4.0.0): Die versionierte Zuordnung in
`docs/data/world-geography-v4.json` erhält vorhandene Company-/Facility-UUIDs,
Koordinaten, Waren und Quellen. Sie ergänzt administrative Stadtidentitäten
und lesbare Länderbezeichnungen. Die Zuordnung ist keine zusätzliche Quelle
für verifizierte Koordinaten; die bisherige Evidence-Klassifikation bleibt
unverändert. Das alte Referenzschema wird nur vom expliziten Offline-Werkzeug
zur Erstellung einer neuen Katalogdatei gelesen.
