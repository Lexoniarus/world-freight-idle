# Relationale Spielpersistenz und Transaktionsgrenzen

Status: Die Laufzeit ist auf das relationale Repository umgestellt. Der
zusätzlich eingeführte KV-Übergangsadapter und der alte KV-Traffic-Leser wurden
entfernt. GameService und FleetService benutzen die geplanten Ports; der
Composition Root bindet Accounts, Cache, Profilpflege und Mehrspielerleser
unmittelbar an SQLite. Die Mapping-Trennung und die abschließende Verifikation
sind noch offen. Dieser Arbeitsstand ist noch nicht zur Integration freigegeben.

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
sie zu ändern. Der separate Offline-Importer in F ist der einzige Altformatweg.

| Tabelle | Schlüssel | Relationale Werte |
| --- | --- | --- |
| player_states | user_id | Guthaben, Reputation, Lieferzähler |
| owned_vehicles | user_id, vehicle_id | Modell, Name, Modus, Nutzlast, Kostensatz, Status, Facility-UID |
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
  danach Angebot, Zeit, Eigentum, Kapazität, Kostensatz und Guthaben unter
  Schreibsperre erneut prüfen, abbuchen, Fahrzeug reservieren, Angebot
  entfernen und den Transport samt Snapshots speichern.
- Ankunft: nur fällige aktive Transporte lesen, Fahrzeug bewegen, Guthaben
  und Zähler erhöhen und Settlement speichern. Erneutes Lesen findet keinen
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
Manifest-Zuordnungen. Die alte game.db bleibt bis F ungelesen und unverändert.

## Ergänzende Ports und Leseadapter

Die Profilpflege erhält eine Factory für GameUnitOfWork und liest aktive Lasten
als ActiveTransport-Objekte. AuthService erhält AccountStore und PasswordVerifier
explizit; SQLite-Konflikte werden im Account-Adapter zu DuplicateAccountError.
Provider benutzen ProviderCache statt SqliteStore. Der neue SQLite-Cache
protokolliert beschädigte JSON-Einträge als Cache-Miss und erlaubt anschließend
einen echten Providerabruf; es werden keine Routendaten erfunden.

LeaderboardReader und TrafficReader beschreiben getrennte öffentliche
Lesezugriffe. Ihre relationalen Adapter verwenden indizierte Besitz-, Status-
und Zeitspalten. Routen stammen aus validierten historischen Snapshots. Tests
prüfen, dass private Kosten, Guthaben und Zugangsdaten nicht im Traffic-Ergebnis
stehen und dass ein Settlement den Offline-Zuschlag in der Rangliste ersetzt.
Die relationalen Leser sind im Composition Root angeschlossen. Es gibt keinen
KV-Rückfall und keinen zweiten Laufzeitpfad. Der separate Offline-Importer bleibt
dem späteren Abschnitt F vorbehalten.
