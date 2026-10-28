# ADR 0008: Gemeinsame Auftragsvorlagen, persönliche Angebote

Status: angenommen, 28.09.2026. Ergänzt ADR 0007.

## Änderung vom 27.10.2026

Der Vorrat ist weiterhin persistent und Vorlagen bleiben spielerübergreifend
wiederverwendbar. Aktiv vorbereitet werden aber ausschließlich konkrete eigene
Fahrzeugbedarfe: zuerst sichtbarer Bestand für idle Fahrzeuge, danach sichtbarer
Bestand am gespeicherten Ziel aktiver Transporte, anschließend deren Reserven.
Zielbedarf besteht unmittelbar ab Dispatch. Die frühere 60-Minuten-Schwelle und
eine Grundversorgung aller Katalogmodelle entfallen. Es gibt keine globale
dritte Eskalationsstufe und keinen Weltmarkt-Scan.

Eine Runde veröffentlicht genau ein persönliches Angebot. Bereits vorhandene
Vorlagen und erfolgreiche Relationsnachweise werden ohne Provideraufruf erneut
verwendet. Auswahl, Fahrzeugkontext und Beladungsfaktor sind mit einem
versionierten SHA-256-Kontext deterministisch; neue Angebots- und Vorlagen-IDs
bleiben eindeutig. Gleichwertige Kandidaten bevorzugen Vielfalt bei Relation,
Frachtart und Ziel. GET und periodische Browserreads füllen den Pool nicht auf.

`SqliteMarketTemplateStore` besitzt ausschließlich gemeinsame Vorlagen;
`SqlitePlayerMarketStockStore` besitzt persönliche Bindungen, Verbrauch, Cursor und
Checkpoints. Der Lifespan-Worker wird durch dauerhafte Bedarfswrites geweckt.
Die nachfolgende Erstentscheidung bleibt historisch lesbar; Aussagen zu allen
Katalogmodellen, 60 Minuten, globaler Lease und 24-Stunden-Erfolgsablauf sind
durch diese Änderung ersetzt.

## Entscheidung

Die Auswahl umfasst höchstens drei fahrbare Angebote pro Entfernungsklasse
und ausgewähltem Fahrzeug. Der Worker hält mindestens zehn Vorlagen pro
Bedarfsstadt, Katalogmodell und strukturell verfügbarem Band vor. Alle 14
Truckmodelle werden berücksichtigt; tatsächliche Fahrzeugbedarfe haben Vorrang.
Die drei sichtbaren Angebote gehören zum Vorrat, sie kommen nicht zusätzlich
zu zehn Reservierungen hinzu. Fehlende geprüfte Straßen werden nicht erfunden.

Globale Vorlagen beschreiben Modell, Handelsbeziehung und Erzeugungsgrundlage.
Persönliche Angebote erhalten eigene IDs und unveränderliche Mengen/Tarife aus
der vorhandenen Factory mit tatsächlich gespeicherter Fahrzeugkapazität.
Kompatible Fahrzeuge können dasselbe persönliche Angebot verwenden. Eine
Vorlage darf von jedem Spieler einmal verwendet werden. Verbrauch, Abbuchung,
Fahrzeugreservierung und Transportanlage teilen eine SQLite-Transaktion.

Vorlagen und persönliche Angebote haben keine zeitliche Ablaufgrenze. Abfahrt,
Neustart und Refresh entfernen oder verändern ungenutzte Angebote nicht. Eine
Annahme lässt bereits gespeicherten Vorrat sofort nachrücken. Der Worker füllt
danach wieder auf; verbrauchte Vorlagen bleiben für andere Spieler erhalten.
Zehn ist eine Untergrenze, keine globale Begrenzung oder Löschregel.

## Verantwortlichkeiten

| Baustein | Aufgabe |
| --- | --- |
| `StockPolicy`, `PreparedTemplate`, `MarketDemand`, `MarketArrival` | Typisierte Regeln, Bestand und Planungskontexte ohne SQL/HTTP |
| `MarketDemandResolver` | Idle-Standorte und gespeicherte Ziele unmittelbar ab Dispatch; keine Auszahlung/Fahrzeugbewegung |
| `StockPlanningService` | Defizite, Prioritäten und stabile Rotation; keine Seiteneffekte |
| `MarketTemplateService` | Wiederverwendung und Materialisierung passender unveränderlicher Angebote |
| `MarketSelectionService` | Stabile Dreier-Projektion bereits vorbereiteter Angebote ohne Providerarbeit |
| `PlayerMarketPreparation` | Spielerbedarf, Offer-Routenbindungen und begrenzte Routenprüfung über injizierte Ports |
| `StockPreparationBatch` | Eine Verbindung pro Spielerrunde, Wiederaufnahme und Orchestrierung |
| `StockPublicationService` | Lesesnapshot, Revisionsvergleich und atomare Veröffentlichung |
| `SqliteMarketTemplateStore` | SQL ausschließlich für spielerübergreifend wiederverwendbare Vorlagen |
| `SqlitePlayerMarketStockStore` | SQL für persönliche Zuordnung/Verwendung, kompakte Ankünfte, Cursor und Checkpoints |
| `MarketStockUpgradeRepository` | Ausschließlich explizite Offline-Übernahme nach 1.2.0 |

Der bestehende Lifespan-Worker besitzt Scheduling und Trace; Paar- und
Anker-Leases schützen ausschließlich konkrete Providerarbeit. Die
Zusammensetzung erfolgt in `app/bootstrap.py`. Die Produktions-Runtime baut
keine Kandidaten und ruft keine Routingprovider auf. Der Marktcontroller fragt
die serverseitige Fahrzeugauswahl ab; Views besitzen keine eigenen Requests.

Reihenfolge: fehlende sichtbare Angebote idle Fahrzeuge, sichtbare Angebote
angekündigter Ankünfte, danach deren Reserven. Andere Katalogmodelle ohne
konkretes eigenes Fahrzeug werden nicht vorbereitet. Gleichrangige
Kontexte rotieren über persistierte Schlüssel; teilweise geprüfte Relationen
bleiben nachvollziehbar. Andere fällige Spieler erhalten nach einer Verbindung
wieder Gelegenheit. Deterministische Fehler und Providerbackoff blockieren
keine anderen Kontexte.

## Konsistenz und Folgen

Planung und Provideraufrufe liegen außerhalb von Schreibtransaktionen. Vor dem
Commit werden Lease, Bedarfsversion, Flotte, persönliche Angebote, Ankünfte,
Vorlagen, Verbrauch, Weltkatalog und verwendete Routingnachweise erneut geprüft.
Veraltete Arbeit wird verworfen. Einmalige Verwendung ist zusätzlich durch
einen eindeutigen `(user_id, template_id)`-Schlüssel abgesichert.

Erfolgreiche Straßennachweise bleiben für denselben Fingerprint dauerhaft
verwendbar. Endgültige Fehler werden nach einer Stunde, Providerstörungen nach
60 Sekunden erneut prüfbar. Ungültige Nachweise
verbergen Angebote bis zur erneuten Prüfung, ohne ihre Konditionen zu löschen.
Katalogseitig unbrauchbare Angebote/Vorlagen zählen nicht zur Versorgung.
Die bestehende bidirektionale Prüfung (fünf Kandidaten, 1 km, zehn Meter,
25 Kombinationen, 120 Sekunden) bleibt unverändert.

Die dauerhafte Speicherung wächst mit Spielerfortschritt und besuchten Städten.
Es gibt kein Vorladen aller Weltstandorte. Infrastruktur liegt relational in
derselben SQLite-Datei, mit Indizes nach Stadt/Modell und Spieler/Vorlage.
Historische Transporte behalten ihre Snapshots einschließlich alter Ablaufwerte.

Schema 1.2.0 erlaubt `expires_at = null`. Bestehende 1.1.0-Dateien werden beim
Serverstart ausdrücklich abgelehnt; ein Backup, eine neue Ausgabe und ein
vollständiger Abgleich sind notwendig. Gültige Altangebote behalten IDs und
Konditionen und verlieren nur die Ablaufgrenze. Abgelaufene Angebote werden
nicht wiederbelebt. Altangebote werden keiner gemeinsamen Vorlage zugeordnet.
Live-Aktivierung bleibt ein eigener Schritt bei gestoppten Schreibern.

Prüfungen und Grenzen: [Testdokumentation](../TESTING.md),
[Betriebsanleitung](../RUNTIME_OPERATIONS.md),
[Qualitätsbericht](../../QUALITY_REPORT.md).
