# Relationale Spielpersistenz und Transaktionsgrenzen

Status: Relationales Schema 1.2.0, direkte Port-Verdrahtung und getrennte
Persistenz-/HTTP-Projektionen sind implementiert. Frühere Formate werden nur
von expliziten Offline-Werkzeugen gelesen. Aktuelle Prüfergebnisse:
[Qualitätsbericht](../QUALITY_REPORT.md).

## Fachliche Grenzen

`GameStateRepository` liest und schreibt typisierte PlayerState-,
OwnedVehicle-, ContractOffer- und ActiveTransport-Objekte für genau einen
Spieler. Die Spieleridentität wird im Composition Root gebunden. Der Port
kennt weder Tabellen noch JSON noch KV-Schlüssel. `GameUnitOfWork` besitzt
die gemeinsame Transaktion und stellt das zugehörige Repository bereit.
Services erhalten diese Ports ausdrücklich als Abhängigkeiten.

SQLite-Verbindungen werden nur im Adapter geöffnet und zuverlässig geschlossen.
Schreibabläufe beginnen mit BEGIN IMMEDIATE. Verschachtelte synchrone Abläufe
teilen eine Verbindung; Fehler führen zum vollständigen Rollback. Asynchrone
Provideraufrufe finden nie innerhalb einer Schreibtransaktion statt.

## Relationale Daten

Die Schema-Versionierung unterscheidet explizit frische Datenbanken vom alten
KV-Spielstand. Der normale Start weist alte oder unbekannte Schemata ab, ohne
sie zu ändern. Nur der separate Offline-Importer liest KV-Altformate;
die Energieübernahme liest ausschließlich das relationale Schema 1.0.0.

| Tabelle | Schlüssel | Relationale Werte |
| --- | --- | --- |
| player_states | user_id | Guthaben, Reputation, Lieferzähler |
| owned_vehicles | user_id, vehicle_id | Modell, Name, Modus, Nutzlast, Kostensatz, Status, Facility-UID, Energieprofil/-inhalt, Höchstgeschwindigkeit |
| contract_offers | user_id, contract_id | Origin-/Destination-UID, Erstellung, Ablauf, Marktmodell |
| transports | user_id, transport_id | Fahrzeug, Auftrag, Status, Start, Ankunft, Settlement, Kosten, Auszahlung |

Konten/Auth bleiben getrennte Tabellen. Fremdschlüssel sichern die Besitzkette
Konten → Spieler → Fahrzeuge/Angebote/Transporte. Referenzkataloge werden nicht
per Fremdschlüssel angebunden: gespeicherte Spielobjekte müssen einen entfernten
oder ausgefallenen Katalog überleben. Ein partieller Unique-Index auf
(user_id, vehicle_id) mit Status active verhindert doppelte Disposition.
Identische lokale Fahrzeugkennungen verschiedener Spieler bleiben gültig.

Unveränderliche historische Standort-, Auftrags- und Routensnapshots erhalten
gezielt versionierte JSON-Dokumente. Der Adapter validiert Version und Inhalt
beim Lesen. Häufige Status-/Zeit-/Besitzfilter erfolgen über Spalten. Es gibt
keinen kompletten Spielerzustand als JSON-Blob und keine Persistenzserialisierung
in Domain/Services. API-Projektionen bleiben ein eigener Adapter.

## Atomare Use Cases

- Initialisierung: fehlenden Spieler und Startfahrzeug gemeinsam anlegen.
- Kauf: Guthaben/Reputation lesen, prüfen, abbuchen, Fahrzeug speichern.
- Disposition: zunächst Angebot/Fahrzeug lesen und Route extern bestimmen;
  danach Angebot, Zeit, Eigentum, Kapazität, Energieprofil/-inhalt, Kostensatz
  und Guthaben unter Schreibsperre erneut prüfen, abbuchen, Fahrzeug reservieren, Angebot
  entfernen und den Transport samt Snapshots speichern.
- Ankunft: nur fällige aktive Transporte lesen, Endfüllstand speichern, Fahrzeug
  bewegen, Guthaben und Zähler erhöhen und Settlement speichern. Erneutes Lesen findet keinen
  aktiven Transport mehr. Nachfolgende Markterzeugung liegt außerhalb dieser
  Transaktion und kann die Auszahlung nicht zurückrollen.
- Profilpflege: Modellübernahmen und optionale Guthabenänderung atomar, ohne
  Transport-Snapshots oder fremde Spieler anzufassen.

Abgerechnete Transporte bleiben gespeichert. Bestehende Spielerzähler werden
nicht aus lückenhafter Historie neu berechnet. Rangliste und Mehrspielerkarte
erhalten eigene typisierte Leseports. Die Rangliste addiert nur fällige, noch
aktive Lieferungen zu den gespeicherten Zählern; Settlement ersetzt diesen
virtuellen Fortschritt ohne doppelte Zählung.

## Fehler, Auth und Cache

SQLite-Fehler werden im Adapter in definierte Persistenzfehler übersetzt und
mit Ereignis/Trace protokolliert; HTTP liefert eine stabile Fehlermeldung ohne
SQL, Pfade oder Zugangsdaten. Account-Service und Provider-Caches erhalten
eigene Ports. Passwort-Hashes werden weder geloggt noch öffentlich projiziert.
Cache- oder Kontenoperationen kennen keine Spielzustands-KV-Schlüssel.

## Verifikation

Temporäre frische Datenbanken prüfen Roundtrips, Schemaabwehr, Fremdschlüssel,
zwei Spieler mit truck_01, parallele Käufe/Disposition/Abrechnung, Rollback,
Cleanup und Snapshotbeständigkeit. Portbasierte Service-Tests benötigen kein
SQL. Architekturtests verbieten konkrete Persistenzadapter und Mapping in
Domain/Services. Alle neuen konkreten Core-Callables erhalten Gegentests und
Manifest-Zuordnungen. Die drei Testprofile wurden nach Backup und vollständigem
Vergleich übernommen.

## Ergänzende Ports und Leseadapter

Die Profilpflege erhält eine Factory für GameUnitOfWork und erlaubt
Modelländerungen ausschließlich an freien Fahrzeugen. AuthService erhält
AccountStore und PasswordVerifier explizit; SQLite-Konflikte werden im
Account-Adapter zu DuplicateAccountError.
Provider benutzen den ProviderCache-Port. Der SQLite-Cache
protokolliert beschädigte JSON-Einträge als Cache-Miss und erlaubt anschließend
einen echten Providerabruf; es werden keine Routendaten erfunden.

LeaderboardReader und TrafficReader beschreiben getrennte öffentliche
Lesezugriffe. Ihre relationalen Adapter verwenden indizierte Besitz-, Status-
und Zeitspalten. Routen stammen aus validierten historischen Snapshots. Tests
prüfen, dass private Kosten, Guthaben und Zugangsdaten nicht im Traffic-Ergebnis
stehen und dass ein Settlement den Offline-Zuschlag in der Rangliste ersetzt.
Die relationalen Leser sind im Composition Root angeschlossen. Es gibt keinen
KV-Rückfall und keinen zweiten Laufzeitpfad. Der separate Offline-Importer gehört
nicht zum Spielbetrieb.

Historische Dokumente enthalten die kanonischen Domainwerte: Endpunkte,
NHM-Evidenz und Route ohne HTTP-Aliase oder berechneten Gewinn. Der historische
Auftrag und die Transportendpunkte bleiben eigenständige gespeicherte Fakten.
Das Repository dekodiert verschachtelte Werte und unveränderliche Tupel;
fehlende Pflichtfelder und unbekannte Felder werden abgewiesen. HTTP-Felder
werden unabhängig davon im API-Bereich projiziert. Diese Dokumentversion ist
Teil des relationalen Schemas 1.1.0; alte KV-Spielstände
werden weiterhin nicht im normalen Serverstart gelesen.


## Explizite Energieübernahme nach 1.1.0

Schema 1.1.0 ergänzt `energy_snapshot`, `energy_level` und `top_speed_kmh`
am eigenen Fahrzeug. Transportsnapshots verwenden Version 2 und enthalten
`JourneyPlan`; Standort- und Auftragssnapshots bleiben Version 1. Normales
Starten führt keine Migration aus und weist Schema 1.0.0 ab.

`python scripts/upgrade_vehicle_energy.py --source <old.db> --check`
prüft den Altbestand ausschließlich lesend. Ausführung erfordert zusätzlich
`--backup <backup.db> --output <new.db>` statt `--check`. Alle Pfade müssen
verschieden sein und die Ausgabe darf nicht existieren. Erst nach erfolgreichem
Backup wird dessen Inhalt übernommen. Ein vollständiger Quellen-/Zielvergleich
bewahrt auch Konten, Sessions, alte Kaufwerte und wirtschaftliche Fakten.

Bekannte Modelle erhalten einmalig ein vollständiges Energieprofil und einen
vollen Vorrat. Alte Transporte bekommen einen ungemessenen Fahrtplan mit genau
ihren bisherigen Zeiten, ohne zusätzliche Halte oder Energieabrechnung.
Fehler entfernen die neue Zieldatei; die Quelle bleibt unangetastet. Das Werkzeug
aktiviert keine Datei und startet keinen Server. Profilpflege ist nur für freie
Fahrzeuge zulässig und überträgt den Füllgrad auf die neue Kapazität.


## Optionaler Dispatch-Routenplan

Spiel-Schema 1.1.0 und Snapshot-Hüllen bleiben unverändert. Neue Transportdaten
speichern `dispatch_route` mit start/pickup/destination, delivery und optionalem
approach. Alle Geometrien und Providerwerte sind historische Werte. Die
Gesamtroute bleibt für bestehende Projektionen enthalten. Der Mapper liest
fehlenden Plan als None, ohne Katalog-/Routerzugriff und ohne Migration.
Historische aktive/settled Snapshots werden nicht nachträglich ergänzt.

Reservierung, Abbuchung, Transport, Offer-Verbrauch und Pruning committen atomar.
Der Abfahrtsstandort wird dabei bewahrt; Settlement schreibt erst das Ziel C.
Refill hat eine zweite Transaktion und kann den Dispatch nicht zurückrollen.

## Frontend-v2: additive Snapshots und Preferences

Game-Schema 1.1.0 und Snapshot-Hüllen bleiben bestehen. Neue Offers speichern
`market_context.tariff`, neue Transporte optional `cost_breakdown`; alte
Transporte werden weder umgeschrieben noch aus aktuellen Katalogen ergänzt.
`account_preferences(user_id, company_color)` ist eine separate Account-Tabelle
mit Fremdschlüssel auf users. Preference-Änderungen betreffen nur den eigenen
Account und kein Game-Schema. Startup ersetzt offene Offers aller bestehenden
Profile in einer gemeinsamen äußeren Transaktion; historische Transporte,
Guthaben und Standorte bleiben dabei unverändert.

## Globale Routing-/Provider-Persistenz

`routing_anchors` gehört wie Provider-Caches zur gemeinsamen serverseitigen
Infrastruktur und nicht zum Spielerzustand. Der Primärschlüssel ist
`(facility_uid, routing_profile)`. Spieler-Reset und historische
Fahrzeug-Snapshots verändern diese globalen abgeleiteten Daten nicht.
SQL bleibt ausschließlich in `SqliteRoutingAnchorRepository`.


## Global Routing Readiness

RoutingRelations, RoutingAttempts, RoutingLeases, MarketPreparations und
OfferRouteReferences sind additive Infrastruktur derselben Runtime-Datenbank.
Player-State-Tabellen und Game-Schema 1.1.0 werden nicht geändert. Die separate
Offer-Referenz unterliegt einem FK mit ON DELETE CASCADE. Publikation erfolgt in
der bestehenden Markt-UoW. Historische Snapshot-Dokumente bleiben unverändert.

`routing_anchor_sources` bindet Anchor-Caches an Facility-Adresse und Koordinaten.
`routing_provider_revisions` speichert die zuletzt tatsächlich beobachtete
Providerrevision. Geometrie liegt weiterhin ausschließlich in `route_cache`.
`current()` liefert bei Fingerprintabweichung oder beschädigtem Payload eine
stale-Projektion; die gespeicherte vorige Evidenz bleibt bis zur Neubewertung
erhalten. Der Auditbericht unterscheidet deshalb gespeicherte Statusaggregate
von `current_relations` (effektiver aktueller Status).


## Reviewkorrektur: atomare Referenzbindung

Game-Schema 1.1.0 und historische Snapshot-Hüllen bleiben unverändert.
RoutingRelation enthält keinen `cache_key`; das Repository liest/schreibt die
existierende Infrastrukturspalte und erzeugt den bisherigen `readiness:v1`-
Schlüssel intern. Ready Relation und Payload bleiben atomar. Offer-Referenzen
werden vollständig validiert und transaktional ersetzt. Eigenständiger Bind
und äußere Markt-UoW rollen vollständig zurück. Coverage-/Analytics-/Audit-
Read-Modelle benötigen keine Schema-Migration.

## Dauerhafter Vorrat: Schema 1.2.0

Die obigen 1.1.0-Abschnitte beschreiben die jeweiligen Einführungsschritte.
Aktuell ist `contract_offers.expires_at` nullable; bei einem gesetzten Wert
gilt weiterhin `expires_at > created_at`. Der Server migriert keine bestehende
Datenbank beim Start. Die explizite Übernahme prüft kanonisches Quellschema,
Dokumente, Fremdschlüssel, sämtliche unveränderten Tabellen/Rowids und Historie.
Zu diesem Zeitpunkt gültige Altangebote erhalten nur den Null-Ablaufwert,
abgelaufene Angebote werden ausgeschlossen. Historische Transport-JSONs bleiben
bytegetreu. Vorgehen: [Betrieb](RUNTIME_OPERATIONS.md).

`market_templates` enthält globale Modell-/Stadtvorlagen mit immutablem
Erzeugungssnapshot. `market_offer_templates` ordnet persönliche Offers zu;
`market_template_uses` enthält die dauerhafte Verwendung je Account/Vorlage.
Beide besitzen eindeutige Spieler-/Vorlagenschlüssel. Angebot, Verbrauch,
Finanzen und Transport committen gemeinsam. Ein Offer-Löschen entfernt nur
die aktive Zuordnung; der Verbrauch bleibt bestehen. Eine normale
Spielzurücksetzung setzt den Account-Verbrauch nicht zurück.

`market_stock_cursors` und `market_stock_pending` speichern Rotation und
angefangene Handelsbeziehungen. Alle Tabellen liegen in derselben WAL-Datenbank.
Bedarfsankünfte werden aus indexierten aktiven Transporten mit skalarem
Ziel-/Zeitpunktzugriff gelesen, ohne Routenarrays in Python zu laden.
Die API liest vorhandene Offers; Refill und Kandidatenbildung gehören zum
separaten Worker. Alter Bestand außerhalb aktueller Bedarfsstädte bleibt erhalten.
