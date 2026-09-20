# Domänenmodell

Abgleich mit [GOAL.md](GOAL.md), Stand 18.09.2026.

| Konzept | Umsetzung | Persistenz |
| --- | --- | --- |
| Benutzer | ID, eindeutiger Spielername, scrypt-Hash | Tabelle `users` |
| Sitzung | Token-Digest, Benutzer, Ablaufzeit | Tabelle `sessions` |
| Spielerzustand | Kapital, Lieferungen, Reputation | KV `user:<id>:player` |
| Fahrzeug | ID, Modell, Modus, Kapazität, Hub, Status, gespeicherter Kilometerkostensatz | KV `user:<id>:vehicles` |
| Auftrag | Facility-Snapshots, NHM-Ware, simulierte Beziehung/Menge, Ablaufzeit | KV `user:<id>:contracts` |
| Transport | Fahrzeug, Auftragssnapshot, Route, Kosten, Zeitstempel | KV `user:<id>:active_trips` |
| Referenzunternehmen / Facility | dauerhafte UUIDs, Adresse, Koordinaten, Waren und Quellen | separater read-only WorldCatalogue |
| Route / Offline-Geocode | normalisierte Providerdaten | Cache-Tabellen; Geocoder außerhalb des Spielpfads |

`Hub`, `CargoType`, `Contract`, `RouteResult`, `PriceQuote`, `VehicleImage` und `VehicleModel` sind typisierte
Dataclasses. Dynamischer Spieler-/Flottenzustand ist derzeit JSON. Die SQL-
Eigentumsgrenze wird über den serverseitig bestimmten Benutzernamensraum gezogen.

Invarianten: Kein Kauf ohne Guthaben und nötige Reputation; ein aktiver Transport pro Fahrzeug;
Standort, Transportmodus und Kapazität müssen passen; kein abgelaufener
Auftrag; Kosten beim Start, Vergütung genau einmal nach Ankunft.
Alle Beträge sind ganzzahlige Spiel-Euro. UTC-Unix-Zeit kommt vom Server.

Noch fehlende Zielobjekte: Spielerunternehmen, eigenes `Depot`, Transportarchiv,
Geldbewegungsjournal und normalisierte Wirtschaftsdaten. Reale Fahrzeugprofile
sind als separater Referenzkatalog integriert; Energie- und Wartungsmodelle
sind weiterhin offen.
Ein öffentlicher Hub ist kein gekauftes Depot. Ein Spielerzustand ist noch
kein eigenständiges Unternehmensmodell. Diese Unterscheidung bleibt in
Zieldokumentation und M1-Abnahme ausdrücklich sichtbar.


Neue Startfahrzeuge verwenden `iveco_sway_500` mit DB-Nutzlast und DB-Kilometerkosten
als Snapshot. Alte Fahrzeuge ohne gespeicherten Kostensatz behalten 0,62 €/km.
VehicleImage ist eine optionale Präsentationsprojektion, kein Bestandteil der
Transportkosten. Laufende Transporte behalten ihre Kosten-/Auszahlungs-Snapshots,
auch bei ausdrücklich beauftragter Testprofilpflege.

`Company`, `Facility`, `CargoProfile`, `DocumentedGood`, `SourceReference`,
`WorldSnapshot` und `FacilityQuery` sind eingefrorene Domain-Referenzmodelle.
Öffentliche UIDs werden einmalig gespeichert, nicht aus Namen oder PKs abgeleitet.
Contracts/Transporte/Fahrzeuge besitzen unabhängige Endpunkt-Snapshots.
Die genauen Referenz-/Simulationsgrenzen stehen in [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md).
