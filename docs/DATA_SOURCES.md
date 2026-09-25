# Datenquellen und Simulationsgrenzen

Technische Providerdetails: [API_PROVIDERS.md](API_PROVIDERS.md).
Geplante Satellitenbilder: [MAP_PROVIDERS.md](MAP_PROVIDERS.md);
aktuell noch kein Satellitenprovider integriert.

| Daten | Aktuelle Quelle | Verwendung / Grenze |
| --- | --- | --- |
| Referenzunternehmen / Facilities / Adressen | `data/world_freight_company_facility_mvp.sqlite3`, Schema 4.2.0 | 559 Facilities in 333 Städten; keine Spielerunternehmen |
| Koordinaten | gespeicherte Quellen und `facility_geocoding_evidence` | Routability und verifizierte/geschätzte Koordinaten getrennt ausgewiesen |
| Lkw-Straßenroute | Valhalla / OpenStreetMap | Geometrie, Kilometer und Fahrzeit |
| Basiskarte | OpenStreetMap Standard via MapLibre GL JS | Rastertiles; Straßen, Orte, Gebäude und POIs; keine Routingquelle |
| Fahrzeugmodelle | `data/world_freight_vehicle_catalog.sqlite3`, Schema 2.2.0 | 14 Modelle, acht Hersteller, technische Quellen in `sources`/`vehicle_sources` |
| Fahrzeug-Spielwerte | `vehicle_balance` im Katalog | fiktive Preise, Nutzlast, Reputation und Kilometerkosten; keine realen Angebote |
| NHM-Waren und Facility-Verhalten | `nhm_codes`, `facility_nhm_profiles`, `facility_handled_goods_nhm` | 15.099 NHM-Codes; belegte und transparent derived IN/OUT/BOTH-Profile; keine generische Standardfracht |
| Beziehungen, Mengen und Aufträge | Market-Services und immutable NHM-Profile | simulierte Einzelereignisse; gespeicherte Kapazität × Load Factor; 0,18 €/km/t × Warenfaktor |
| Vergütung / Betriebskosten | calculate_price | balanciertes Spielmodell |

Eurostat, GLEIF, FAF, UN Comtrade, OurAirports und SeaRoute sind mögliche
spätere Live-Quellen aus GOAL.md. Quellenreferenzen der gelieferten Datenbank
bleiben erhalten; ihre externen Live-APIs sind nicht angebunden.
Vor einer Integration: Quelle, Nutzungsbedingungen, Datenstand, Lizenz,
Aktualisierung, Fehlerverhalten und interne Normalisierung dokumentieren.

OSM-Attribution ist bei der Karte verlinkt. Ein Providerfehler bleibt ein
sichtbarer Fehler; das Spiel erfindet keine Ersatz-Straßenroute.
Cache-Einträge besitzen Zeitstempel, derzeit aber keine automatische TTL-
Invalidierung. Für Fahrzeugprofile und Bilder sind Herkunfts-/Lizenzmetadaten im Katalog
vorhanden. Für alle 14 bekannten Modelle werden zuerst lokale Spielgrafiken
verwendet. Für Modelle ohne lokale Grafiken können verifizierte Fotos direkt
von Wikimedia geladen werden. Quelle, Urheber, Lizenz und Modellfamilienbezug
bleiben dann sichtbar; ohne Foto oder bei Ladefehlern folgt die Illustration.
Lokale Grafiken: [Manifest](../assets/MANIFEST.md),
[Herkunft und Nutzung](../assets/LICENSE.md). Die Ordnerumstellung erhält alle
SVG-Bytes und externen Katalogmetadaten; sie begründet keine neue Lizenz.
Andere Datenquellen besitzen noch keine durchgängigen
Herkunfts-/Lizenzmetadaten pro Datensatz.

## WorldCatalogue: aufbereiteter Referenzstand

Die Referenzdatei wurde nach SQLite-Backup von v3 auf das normalisierte
Schema v4 in einer neuen Datei überführt. UUIDs werden
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

## Fahrzeugenergie

Die frühere Energieanreicherung (Schema 2.1.0 / Datenstand 2.2.0) ergänzt für alle 14 Modelle Verbrauch,
Einheit, Tank-/nutzbare Batteriekapazität und Höchstgeschwindigkeit. Quellen-
notizen unterscheiden Test-/Referenzwerte von repräsentativen Spielannahmen.
Der Runtime-Leser validiert diese Daten als EnergyProfile; der technische
Anschluss behauptet keine zusätzliche externe Quellenverifizierung. Diesel-
pausen (10 Minuten) und Reserve (10 %) sind zentrale Simulationswerte. Gas
verwendet 25, Elektro 35 Minuten aus dem Katalog. Fahrverbrauch und Pausen
sind als begrenzte erste Simulation aktiv. Verbrauch bleibt konstant;
Zusatzkosten entstehen nicht. Tankstellen und Ladepunkte werden nicht
recherchiert, sondern als Positionen entlang der gespeicherten Route simuliert.


## Market-v2-Profile

Der unverändert übernommene World-Katalog 4.2.0 enthält nhm_market_profiles,
nhm_distance_load_profiles und nhm_vehicle_scale_profiles. Vehicle 2.2.0 ergänzt
vehicle_transport_capabilities und explizite Segmente. Warenwerte, Frachtraten-
Faktoren, Load Factors und Suitability sind Spielparameter, keine beobachteten
Handelspreise. Haversine-Schätzungen dienen ausschließlich Marktgewichtung und
Coverage. Die Auszahlung verwendet die gerouteten Straßenkilometer und die
bei Generierung gespeicherte Frachtrate. Sie hängt nicht vom Warenwert ab.

## Wirtschaft: Quelle statt Heuristik

Neue Wartung kommt ausschließlich aus dem ausdrücklich benannten Vehicle-
Katalogfeld. Energiepreise sind Gameplaykonstanten; Käufe stammen aus dem
gespeicherten Journey-Plan. NHM-Faktoren/Lastgrenzen kommen aus World.
Die 20-%-Referenzmarge ist eine Tarifentscheidung, keine Gewinngarantie.
Warenwert bleibt ohne Einfluss auf Vergütung. [Details](ECONOMY_V2.md).

## Fahrzeug-Lackmasken

`assets/paint-inventory.json` erfasst 42 explizite, separat gepflegte Masken
für die 14 aktuellen Modelle und ihre drei Ansichten. Sie sind additive
Produktionsassets; die 134 Original-/Referenz-SVGs im bisherigen Inventar
bleiben bytegleich. Die Laufzeit verwendet keine Helligkeitsheuristik und
keine Ganzbildtönung. Belegbilder und Vergleichsraster sind lokale Artefakte.
