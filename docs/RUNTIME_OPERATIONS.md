# Betrieb: Runtime, Vorbereitung und Offline-Reparatur

Alle Befehle werden aus der Repositorywurzel mit `main.py` ausgeführt.
Ohne aktive virtuelle Umgebung wählt `main.py` die vorhandene Projekt-`.venv`
vor dem Import der Anwendungsabhängigkeiten aus. Er installiert nichts und
überschreibt keine ausdrücklich aktivierte Umgebung. So verwendet auch der
normale Windows-Python-Aufruf die installierten Projektpakete. Der Elternprozess
wartet auf den gestarteten Interpreter und dessen Ctrl+C-Aufräumen.
Der bei Bedarf gestartete Projektinterpreter erhält den absoluten Pfad zum
Einstiegspunkt; Aufrufe aus einem anderen Arbeitsordner sind damit möglich.
Relative Konfigurationspfade wie `DB_PATH` bleiben relativ zum aufrufenden
Arbeitsordner. Es wird kein zweiter Runtime-/Prewarm-Prozess erzeugt.

```powershell
python main.py
```

Der FastAPI-Lifespan besitzt genau einen Marktworker. Er wird nach erfolgreicher
Runtime-Initialisierung gestartet und vor HTTP-Client/Adapterressourcen beendet.
Für kontrolliertes Beenden Ctrl+C beziehungsweise den Dienstmanager benutzen.
Die Datenbank muss auf einem lokalen Dateisystem liegen, das SQLite-WAL korrekt
unterstützt. Kein Kopieren einer aktiven `.db` ohne WAL:
Backups immer über die vorhandene SQLite-Backup-Funktion erstellen.

Dauerhafte Bedarfswrites wecken den Worker über ein lokales Event. Er fragt die
Datenbank nicht sekündlich ab; 60 Sekunden sind nur das Sicherheitsintervall für
fällige Backoffs. Bedarf und fertige Teilergebnisse bleiben gespeichert. Die API
wartet weder beim Start noch beim Refresh auf vollständige Märkte. `partial` ist
ein bedienbarer Zustand. GET, Runtime-Polling und Kartennavigation erzeugen
keinen Bedarf und rufen keinen Provider auf.

`market.preparation_failed` / `market.preparation_scheduler_failed` signalisieren
einen erneut eingeplanten Lauf.
Bei gesperrten finanziellen Aktionen entscheidet der Spieler nach erneutem
Lesen des Kontostands über einen weiteren Auftrag; keine automatische Wiederholung.

## Eng begrenzte Alttransport-Reparatur

Zunächst ausschließlich prüfen, ohne Quelle zu verändern:

```powershell
python scripts/repair_transport_metadata.py --source data/game.db --check
```

Die Ausgabe nennt nur Transportanzahl sowie bekannte aktive/abgeschlossene
Reparaturfälle. Unbekannte Schäden führen zum Abbruch. Für den ersten Spieltest
eine neue Ausgabe mit eigenständigem Backup und privatem Archiv erzeugen:

```powershell
python scripts/repair_transport_metadata.py --source data/game.db --backup data/backups/before-transport-repair.db --output data/repaired-test.db --archive data/repair-archive/transport-originals.jsonl
$env:DB_PATH = "data/repaired-test.db"
python main.py
```

Alle drei Zielpfade müssen neu und voneinander sowie von der Quelle verschieden
sein. Das Archiv enthält private Originaldokumente bytegetreu als UTF-8-Strings,
Original-/Ersatz-SHA256 und Reparaturversion. Es wird erneut gelesen und geprüft.
Die Ausgabe behält Schema, Row-Identitäten, Fahrtplan, Endpunkte, Gesamtstrecke,
Kosten, Auszahlung und Status; ausschließlich `dispatch_route` wird auf `null`
gesetzt. Vollständiger Tabellenabgleich, SQLite-Integrität, Fremdschlüssel und
kanonische Transportvalidierung müssen vor Erfolg bestehen. Fehlgeschlagene
neue Ausgaben werden entfernt; vorhandene Dateien niemals überschrieben.

Auf der Kopie: anmelden, Flotte/Transporte laden, fällige Ankünfte normal
abrechnen lassen, Kontostand und abgeschlossene Anzahl nach erneutem Laden
auf unveränderte Werte prüfen. Neue Angebote und Folge-Dispatch weiterhin
durch Readiness freigeben lassen. Keine Live-Fahrzeuge versetzen und keine
rückwirkenden Kostenänderungen vornehmen.

## Gesonderte Live-Aktivierung

1. API, Worker und alle Wartungswriter stoppen; Prozessende kontrollieren.
2. Frisches SQLite-Backup der zuletzt aktiven Quelle erstellen und denselben
   Reparaturlauf in **neue** Ziel-/Archivpfade wiederholen. Keine inzwischen
   veraltete Testkopie über aktuelle Spielerfortschritte kopieren.
3. Erfolgreichen Bericht und Quellen-/Zielabgleich prüfen. `DB_PATH` auf die
   neue Ausgabe umstellen; ursprüngliche Datenbank und Backup aufbewahren.
   Soll der Standardpfad `data/game.db` erhalten bleiben, nach erneutem
   Stillstandscheck die Originaldatei samt vorhandenen `-wal`-/`-shm`-Sidecars
   in ein neues privates Archiv verschieben und erst dann die geprüfte Ausgabe
   an den Standardpfad verschieben. SHA256 vor/nach Übernahme vergleichen;
   bei einem fehlgeschlagenen Dateischritt die archivierten Originale
   zurückstellen. Niemals neben laufenden Schreibern austauschen.
4. Rollen starten, Anmeldung, Runtime, genau einmaliges Settlement und
   Marktfortschritt prüfen. Bei Fehlern stoppen, Diagnose sichern und vor
   einem Rückwechsel berücksichtigen, ob die neue Datei bereits Fortschritt hat.

Dieser Schritt wird nicht durch Tests, Commit oder Push ausgelöst. Datenbanken,
Backups, Reparaturarchive, Sitzungen und Messartefakte bleiben außerhalb von Git.

## Vorratsschema 1.2.0 ausdrücklich übernehmen

Vor dem nächsten Start mit dieser Version muss ein vorhandener 1.1.0-Spielstand
übernommen werden. `main.py` verändert das alte Schema nicht automatisch.
Zunächst auf einer isolierten Kopie prüfen, dann erst die Live-Aktivierung
als gesonderten Betriebsschritt durchführen:

```powershell
python scripts/upgrade_market_stock.py --source data/game.db --check
python scripts/upgrade_market_stock.py --source data/game.db --backup data/backups/before-market-stock.db --output data/market-stock-test.db
$env:DB_PATH = "data/market-stock-test.db"
python main.py
```

Backup und Ausgabe müssen neue, unterschiedliche Pfade sein. Der ausschließlich
lesende Prüfmodus verlangt weder Backup noch Ausgabe. Die Übernahme verwendet
einen einzigen Zeitstempel: zu diesem Zeitpunkt gültige persönliche Angebote
behalten IDs und Konditionen, erhalten `expires_at = null`; bereits abgelaufene
Angebote und ihre Routenbindungen entfallen. Keine Altangebote werden nachträglich
gemeinsamen Vorlagen zugeordnet. Alle übrigen Tabellen, insbesondere komplette
historische Transportdokumente, werden einschließlich Zeilenidentitäten abgeglichen.
Unbekanntes Schema, widersprüchliche Dokumente, Abgleich-/Integritätsfehler oder
kollidierende Vorratstabellen brechen die Übernahme ab.

Nach Prüfung der Kopie gelten die oben beschriebenen Schritte für gestoppte
Writer und frisches Backup erneut. Eine ältere Testkopie ersetzt niemals einen
inzwischen fortgeschrittenen Live-Spielstand. Diese Anleitung aktiviert nichts
automatisch. Die Alttransport-Reparatur muss bei beschädigten alten Beständen
vor der Schemaübernahme mit der dafür passenden Version abgeschlossen sein.

`market.stock_published` nennt neue Vorlagen und persönliche Angebote samt
Bedarfsversion. Die Reserve wächst nur in Bedarfsstädten; unbenutzte Angebote
bleiben nach Abfahrt bestehen. Fehlende Angebote trotz Reserve können auf
fehlende Anfahrt/Rückwege, abgelaufene Routingnachweise oder nicht mehr passende
Katalogdaten hinweisen. Sie werden nicht durch ungeprüfte Angebote ersetzt.

## Historisch einseitigen Marktbestand prüfen

Ein bereits voller alter Bestand wird im normalen Betrieb nicht gelöscht, nur
weil spätere Versionen die sichtbare Vielfalt besser priorisieren. Deshalb ist
die Korrektur ein ausdrücklicher Offline-Schritt. Zunächst ausschließlich
prüfen:

```powershell
python scripts/repair_market_diversity.py --source data/game.db --check
```

Der Bericht enthält nur geprüfte und betroffene Kontextanzahlen, geplante
Angebotsentfernungen und die Anzahl neu einzureihender Spieler. Benutzer-IDs,
Angebote und Pfade werden nicht ausgegeben. Eine Korrektur wird nur geplant,
wenn ein Stadt-/Modell-/Distanzband bereits voll ist und unbenutzte vorbereitete
Vorlagen die sichtbare Routen-, Waren- oder Zielvielfalt tatsächlich erhöhen.
Ein Markt mit nur einer gültigen Handelsbeziehung bleibt unverändert.

Für einen Spieltest werden vier voneinander verschiedene neue Pfade verlangt:

```powershell
python scripts/repair_market_diversity.py --source data/game.db --backup data/backups/before-market-diversity.db --output data/market-diversity-test.db --archive data/repair-archive/market-diversity-originals.jsonl
$env:DB_PATH = "data/market-diversity-test.db"
python main.py
```

Die Quelle bleibt bytegleich. Entfernt werden ausschließlich unangenommene,
nicht durch Transporte oder Verwendung geschützte persönliche Angebote. Geld,
Fahrzeuge, Transporte, globale Vorlagen, verwendete Vorlagen und globale
Routingnachweise bleiben erhalten. Nur Fortschritt und Coverage betroffener
Spieler werden zurückgesetzt und als `partial` neu eingereiht. Das private
JSONL-Archiv enthält alle entfernten beziehungsweise zurückgesetzten Zeilen
mit SHA-256-Prüfsummen. Die neue Kopie wird tabellenweise reconciled sowie mit
SQLite-Integrität und Fremdschlüsseln geprüft. Bei einem Fehler werden Ausgabe
und Archiv entfernt; das zuvor erstellte Backup bleibt erhalten.

Die Aktivierung folgt anschließend unverändert dem Abschnitt
„Gesonderte Live-Aktivierung“: Writer stoppen, frisches Backup, Bericht prüfen,
Kopie separat starten und erst danach den aktiven Pfad umstellen. Das Kommando
wird weder beim Serverstart noch durch Tests, Commit oder Push automatisch auf
eine Spielerdatenbank angewendet.
