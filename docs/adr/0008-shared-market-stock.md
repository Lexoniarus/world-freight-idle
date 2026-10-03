# ADR 0008: Gemeinsame Auftragsvorlagen, persönliche Angebote

Status: angenommen, 28.09.2026. Ergänzt ADR 0007.

## Entscheidung

Die Auswahl umfasst höchstens drei fahrbare Angebote pro Entfernungsklasse
und ausgewähltem Fahrzeug. Der Worker hält mindestens zehn Vorlagen pro Stadt,
Katalogmodell und strukturell verfügbarem Band vor. Alle Truckmodelle werden
berücksichtigt; tatsächliche Fahrzeugbedarfe haben strikt Vorrang.
Die drei sichtbaren Angebote gehören zum Vorrat, sie kommen nicht zusätzlich
zu zehn Reservierungen hinzu. Fehlende geprüfte Straßen werden nicht erfunden.

Globale Vorlagen beschreiben Modell, Handelsbeziehung und Erzeugungsgrundlage.
Persönliche Angebote erhalten eigene IDs und unveränderliche Mengen/Tarife aus
der vorhandenen Factory mit tatsächlich gespeicherter Fahrzeugkapazität.
Kompatible Fahrzeuge können dasselbe persönliche Angebot verwenden. Eine
Vorlage darf von jedem Spieler einmal verwendet werden. Verbrauch, Abbuchung,
Fahrzeugreservierung und Transportanlage teilen eine relationale Transaktion.

Vorlagen und persönliche Angebote haben keine zeitliche Ablaufgrenze. Abfahrt,
Neustart und Refresh entfernen oder verändern ungenutzte Angebote nicht. Eine
Annahme lässt bereits gespeicherten Vorrat sofort nachrücken. Der Worker füllt
danach wieder auf; verbrauchte Vorlagen bleiben für andere Spieler erhalten.
Zehn ist eine Untergrenze, keine globale Begrenzung oder Löschregel.

## Verantwortlichkeiten

| Baustein | Aufgabe |
| --- | --- |
| `StockPolicy`, `PreparedTemplate`, `MarketDemand`, `MarketArrival` | Typisierte Regeln, Bestand und Planungskontexte ohne SQL/HTTP |
| `MarketDemandResolver` | Konkrete Idle-Standorte und gespeicherte Ziele ab Dispatch; globale Katalogkontexte getrennt projizieren |
| `StockPlanningService` | Defizite, Prioritäten und stabile Rotation; keine Seiteneffekte |
| `MarketTemplateService` | Wiederverwendung und Materialisierung passender unveränderlicher Angebote |
| `MarketSelectionService` | Stabile Dreier-Projektion bereits vorbereiteter Angebote ohne Providerarbeit |
| `StockPreparationBatch` | Eine Verbindung pro Spielerrunde, Wiederaufnahme und Orchestrierung |
| `GlobalStockPreparationBatch` | Ohne Spieler-UoW genau einen globalen Stadt-/Modell-/Band-Kontext vorbereiten |
| `StockPublicationService` | Lesesnapshot, Revisionsvergleich und atomare Veröffentlichung |
| `SqliteMarketTemplateStore` | SQL für globale Vorlagen und mengenbasierte Bestandsstände |
| `SqliteMarketStockStore` | Persönliche Zuordnung/Verwendung, kompakte Ziele und Checkpoints; delegiert Vorlagenzugriffe |
| `MarketStockUpgradeRepository` | Ausschließlich explizite Offline-Übernahme nach 1.2.0 |

Der bestehende Worker besitzt Scheduling, Trace und globale Lease. Die
Zusammensetzung erfolgt in `app/bootstrap.py`. Die Produktions-Runtime baut
keine Kandidaten und ruft keine Routingprovider auf. Der Marktcontroller fragt
die serverseitige Fahrzeugauswahl ab; Views besitzen keine eigenen Requests.

Die fünf effektiven Stufen sind: sichtbarer Bestand für idle Fahrzeuge,
sichtbarer Bestand in Zielstädten aktiver Transporte, Idle-Reserve,
Zielstadt-Reserve und erst danach globaler Vorrat für alle übrigen
Stadt-/Modell-/Band-Kontexte. Zielstadtbedarf gilt unmittelbar ab Dispatch.
Solange irgendein Spielerstatus `partial` ist, läuft Stufe fünf auch während
Backoff nicht. Nach jedem globalen Routenpaar wird Spielerbedarf erneut geprüft.
Deterministische Fehler und Providerbackoff blockieren keine anderen Kontexte
derselben zulässigen Stufe.

## Konsistenz und Folgen

Planung und Provideraufrufe liegen außerhalb von Schreibtransaktionen. Vor dem
Commit werden Lease, Bedarfsversion, Flotte, persönliche Angebote, Ankünfte,
Vorlagen, Verbrauch, Weltkatalog und verwendete Routingnachweise erneut geprüft.
Veraltete Arbeit wird verworfen. Einmalige Verwendung ist zusätzlich durch
einen eindeutigen `(user_id, template_id)`-Schlüssel abgesichert.

Straßennachweise bleiben zeitlich begrenzt: 24 Stunden bei Erfolg, eine Stunde
bei endgültigem Fehler, 60 Sekunden bei Providerstörung. Ungültige Nachweise
verbergen Angebote bis zur erneuten Prüfung, ohne ihre Konditionen zu löschen.
Katalogseitig unbrauchbare Angebote/Vorlagen zählen nicht zur Versorgung.
Die bestehende bidirektionale Prüfung (fünf Kandidaten, 1 km, zehn Meter,
25 Kombinationen, 120 Sekunden) bleibt unverändert.

Die dauerhafte Speicherung wächst mit Spielerfortschritt und besuchten Städten.
Es gibt kein synchrones Vorladen aller Weltstandorte. Der opportunistische
globale Lauf erzeugt ausschließlich Delivery-Vorlagen; standortabhängige
Anfahrten gehören zu konkretem Spielerbedarf. Infrastruktur liegt relational
in PostgreSQL/Supabase, mit SQLite-Adaptern für Tests und Offline-Werkzeuge.
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
