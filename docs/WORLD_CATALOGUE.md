# WorldCatalogue: Referenzen und Spielzustand

Stand: 18.09.2026. UI First, FastAPI, native ES-Module, OSM und
`python main.py` bleiben Grundlage. Reale Referenzunternehmen sind keine
Spielerunternehmen; öffentliche Facilities sind keine eigenen Depots.

## Referenzdaten

`data/world_freight_company_facility_mvp.sqlite3` wird mit Schema **3.0.0**
versioniert ausgeliefert. `WORLD_CATALOGUE_PATH` kann diese Datei ersetzen,
unabhängig von `DATA_DIR` und `DB_PATH`. Laufzeitverbindungen verwenden
`mode=ro`, `query_only`, Fremdschlüsselprüfung und eine konsistente Lesetransaktion.
Jeder Handle wird auch bei Fehlern geschlossen. Es gibt keinen Seed-Fallback.

Der aufbereitete Stand enthält 83 Referenzunternehmen und 155 Facilities.
43 Facilities sind routbar: endliche Koordinaten innerhalb WGS84,
`verified_coordinates` und ein exakt passender Nachweis mit Quelle,
Prüfdatum und einer der Genauigkeitsklassen `official_facility_coordinate`,
`facility_centroid`, `osm_feature`, `verified_address_point`.
19 ursprüngliche Koordinaten ohne passenden Nachweis und 93 Standorte ohne
Koordinaten bleiben ausgeschlossen. Ein erfolgreicher Nominatim-Aufruf ist
keine Verifikation. Der Spielserver erzeugt keinen Geocoding-Client.

Alle 43 routbaren Facilities erhalten ausgehende Aufträge je Nutzlastklasse.
24 besitzen geeignete dokumentierte Ausgangs-/Umschlagwaren. An den übrigen
19 wird ausdrücklich simulierte Standardfracht angeboten: `cargo_basis=simulated`,
`cargo_evidence=null`, sichtbarer Hinweis in der UI. Reale Warenbelege werden
nicht erfunden. Neue Ziele können alle routbaren Facilities sein; Folgeaufträge
stehen an jedem Standort bereit. Fehlende Aufträge werden ergänzt, während
weiter gültige Auftrags-IDs und Snapshots unverändert bleiben.

## Identitäten und Aufbereitung

`company_uid` und `facility_uid` sind einmalig erzeugte und gespeicherte UUIDs.
Unique-Indizes sowie Pflicht- und Unveränderlichkeitstrigger sichern sie ab.
Numerische SQLite-PKs werden nur intern für Joins verwendet. Sie erscheinen
nicht in API-Projektionen oder neuen Spielstandreferenzen. Einseitige
NULL-Koordinaten werden per Trigger und Lesevalidierung abgewiesen;
polymorphe externe Identifikatoren werden auf existierende Zielobjekte geprüft.

Das Offline-Werkzeug trennt CLI, Validierung und SQL. Es erstellt zuerst ein
SQLite-Backup (einschließlich committed WAL-Daten), erweitert v2 transaktional
und prüft alle Legacy-Endpunkte vor dem Commit. Wiederholung erhält UUIDs.

```sh
python scripts/prepare_world_catalogue.py --catalogue data/world_freight_company_facility_mvp.sqlite3 --backup data/backups/world-before-v3.sqlite3 --evidence docs/data/legacy-facilities.json
```

Ein vorhandener Backuppfad wird nicht überschrieben. Die ausgelieferte Datei
ist bereits aufbereitet; der Befehl ist kein notwendiger Serverstartschritt.
Das Werkzeug ist kein allgemeiner Merge-Importer: bestehende Aliase werden
nicht durch geänderte Namen/Adressen neu zugeordnet. Künftige Importe müssen
die gespeicherten UUIDs mitführen oder eine ausdrücklich geprüfte eindeutige
Identitätszuordnung liefern. Abgleich durch Namen, Adressen oder PKs allein
ist nicht zulässig. UID-Updates werden von der Datenbank blockiert.

`facility_aliases` verbindet `berlin_westhafen`, `hamburg_cta`, `duisburg_d3t`
und `rotterdam_maasvlakte` mit den vier ergänzten verifizierten Facilities.
Quellen und geprüfte Koordinaten stehen in [legacy-facilities.json](data/legacy-facilities.json).
Start und Kauf liefern weiterhin nach Berlin Westhafen. Das Aufbereiten der
Referenzdaten verändert keine Spielerprofile.

## Simulation und Snapshots

Company, Facility, Adresse, Koordinaten, dokumentierte Güter und ihre Quellen
kommen aus dem WorldCatalogue. Wo geeignete dokumentierte Waren fehlen,
ist Standardfracht ausdrücklich Mock-/Simulationsinhalt. Empfängerbeziehung, Tonnage, Vergütung und
Einzelauftrag sind simuliert. Ein tatsächlicher Wareneingang beim Empfänger
wird nicht behauptet. Same-City und Same-Company sind erlaubt; identische
Facility-UIDs auf beiden Seiten sind ausgeschlossen.

Neue Standardfracht nutzt 0,18 €/km/t. Mengen sind unter `app/simulation.py`
getrennt simuliert: Nutzlasten aus VehicleCatalogue und bestehenden Fahrzeugen
werden in leicht (bis 3,5 t), mittel (über 3,5 bis 12 t) und schwer (über 12 t)
eingeordnet. Dies sind Nutzlastklassen, keine zulässigen Gesamtgewichte.
Je belegter Klasse und Standort entsteht mindestens ein Auftrag mit 60–100 %
der kleinsten Nutzlast dieser Klasse, auf 0,01 t abgerundet (mindestens 0,01 t).
Damit kann jedes Katalogmodell und jedes Bestandsfahrzeug dort Arbeit finden.
Der lokale 14-Modell-Katalog ergibt 129 Aufträge an 43 Standorten; der
versionierte 8-Modell-Katalog belegt nur die schwere Klasse und ergibt 43.
`payload_band` speichert die Simulationsklasse; alte Aufträge ohne dieses Feld
bleiben erhalten und werden durch passende neue Angebote ergänzt. Beim Kauf
wird kein bestehender Auftrag geändert. Die UI zeigt Nutzlast und Menge mit
bis zu zwei Dezimalstellen. Kühlung, Gefahrgut, Tank- und Schüttgut sind
ausgeschlossen. Es gibt kein globales Limit von 6 Aufträgen. Laufzeit (6 h), Erlösformel und
fahrzeugbezogene Betriebskosten bleiben erhalten. Alte Aufträge behalten ihre bisherigen Warenregeln.

Bei Erzeugung speichert ein Auftrag vollständige Endpunktprojektionen:
UIDs, Referenzunternehmen, Namen, Typ, Adresse, Koordinaten, Nachweise,
dokumentierte Waren, Quellen und Katalogversion. Quote und Disposition nutzen
diese Snapshots. Transporte besitzen zusätzlich `origin_snapshot` und
`destination_snapshot`; Fahrzeuge `facility_uid` und `location_snapshot`.
Ein später gelöschter oder geänderter Katalogeintrag verändert diese nicht.

## Bestandsmigration

Vor der Migration **Server stoppen**; es darf kein paralleler Spielzugriff
erfolgen. Danach mit derselben `DB_PATH`-/`WORLD_CATALOGUE_PATH`-Konfiguration:

```sh
python scripts/migrate_world_state.py --backup data/backups/game-before-world-v1.sqlite3
python main.py
```

Das Werkzeug sichert zuerst, liest einen konsistenten Katalogstand und ergänzt
alle Spieler-Namensräume in einer atomaren Transaktion. Es setzt
`world_state_version=1`. Wiederholung verändert nichts. Unbekannte oder nicht
verifizierte Zuordnungen brechen ohne Teiländerungen ab. Guthaben, Fahrzeug-
und Auftrags-IDs, Status und Transportkosten bleiben erhalten. Fahrzeuge
werden derselben bisherigen Facility zugeordnet, nicht an einen neuen Ort versetzt.

Aktive Transporte behalten ihre ursprünglichen `origin`-/`destination`-Daten,
Geometrien, Zeiten und Auszahlungen. Die zusätzlichen Snapshots übernehmen
historische Routingpunkte ausdrücklich als `legacy_endpoint`; abweichende
historische Koordinaten beanspruchen keine neue Verifikation. Keine Neuroute.
Auch bei Katalogausfall wird eine fällige Auszahlung einmalig verbucht.
Die anschließende Markterzeugung liegt außerhalb der Abrechnungstransaktion.

## API, Darstellung und Fehler

`GET /api/v1/map/facilities?bbox=west,south,east,north` ist authentifiziert.
Antwort: `facilities`, `catalogue_version`, `unavailable_count`.
Bounds müssen endlich und innerhalb WGS84 sein; west > east bedeutet
Datumsgrenzenübertritt. Fehlerhafte Bounds: 422. Fehlender/inkompatibler
Katalog: 503. Das Query-Modell hält spätere Zoomfilter offen; aktuell gibt
es keine serverseitige Zoomaggregation.

`GET /api/v1/map/hubs` bleibt als Envelope `hubs` erhalten, ohne Geocoding.
`hub_id`, `origin_hub_id`, `destination_hub_id` projizieren die Facility-UIDs.
Alte UI-Links mit `?hub=berlin_westhafen` werden über Snapshot-Aliase erkannt.
Kartenobjekte, Auswahl und Vergleiche verwenden dauerhafte Facility-Identität.
Bei Katalogausfall bleiben gespeicherte Fahrzeug- und Transportpositionen
verfügbar; unbekannte Standorte erhalten keinen erfundenen Marker.

Strukturierte Ereignisse: `world.catalogue_read`, `world.catalogue_error`,
`world.prepared`, `world.state_migrated`, `world.delivery_unavailable`,
`market.catalogue_unavailable`, bestehende Quote-/Transportereignisse.
Katalogversion, Ausschlusszahlen und Facility-UIDs werden mitgeführt;
HTTP-Anfragen behalten ihre bestehenden Trace-IDs. CLI-Ausgaben sind separat
vom HTTP-Betrieb und werden als strukturierte Logs ausgegeben.

## Verantwortlichkeiten und Abnahme

Der Domain-Port liefert unveränderliche Referenzmodelle. Game-Core und Markt
kennen weder SQL noch konkrete WorldCatalogue-Adapter. Composition Roots
verdrahten Laufzeit-, Pflege- und Migrationsports. SQL liegt in Repositories.
Nominatim bleibt für kontrolliertes Offline-Enrichment mit anschließender
Prüfung verfügbar; kein normaler Karten-, Quote- oder Dispositionspfad nutzt es.

Tests prüfen Provenienz, Read-only/Cleanup, UID-Erhalt bei PK-Änderungen,
Idempotenz/Rollback/Backupfehler, dokumentierte oder ausdrücklich simulierte Standardwaren,
Same-City/Same-Company, flächendeckende Auftragsversorgung,
Snapshots bei Katalogausfall und unveränderte Auszahlungen. Jeder konkrete
Core-Callable hat eine Manifest-Zuordnung. Werkzeug-, Architektur- und
Browserergebnisse werden getrennt in [QUALITY_REPORT.md](../QUALITY_REPORT.md)
ausgewiesen. M1, echte iPad-Hardware und öffentlicher Betrieb bleiben eigene
Abnahmegrenzen.
