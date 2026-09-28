# Betrieb: Runtime, Vorbereitung und Offline-Reparatur

Alle Befehle werden aus der Repositorywurzel mit `main.py` ausgeführt.
Ohne aktive virtuelle Umgebung wählt `main.py` die vorhandene Projekt-`.venv`
vor dem Import der Anwendungsabhängigkeiten aus. Er installiert nichts und
überschreibt keine ausdrücklich aktivierte Umgebung. So verwendet auch der
normale Windows-Python-Aufruf die installierten Projektpakete. Der Elternprozess
wartet auf den gestarteten Interpreter und dessen Ctrl+C-Aufräumen.
Kindprozesse erhalten den absoluten Pfad zum Einstiegspunkt; Aufrufe aus einem
anderen Arbeitsordner sind damit möglich. Relative Konfigurationspfade wie
`DB_PATH` bleiben relativ zum aufrufenden Arbeitsordner.
Beide Rollen erben dieselbe Konsole. Sie öffnen kein zusätzliches Fenster;
Startmeldungen und Fehler bleiben sichtbar. `CREATE_NO_WINDOW` wird bewusst
nicht verwendet: Es macht geerbte Windows-Konsolenausgaben ungültig.

```powershell
python main.py
# Alternativ in getrennten Prozessdiensten mit identischer Konfiguration:
python main.py --role runtime
python main.py --role prewarm
```

Der Standard startet und überwacht beide Rollen. Ein beendeter API-Prozess
beendet auch den Worker. Worker-Ausfälle lassen HTTP weiterlaufen und werden
mit begrenztem Backoff neu gestartet. Für kontrolliertes Beenden Ctrl+C bzw.
den Dienstmanager benutzen. Standalone-Rollen müssen beide vom Dienstmanager
beendet werden. Die Datenbank muss auf einem lokalen Dateisystem liegen, das
SQLite-WAL korrekt unterstützt. Kein Kopieren einer aktiven `.db` ohne WAL:
Backups immer über die vorhandene SQLite-Backup-Funktion erstellen.

Mehrere gestartete Worker teilen eine globale Lease (180 Sekunden, Erneuerung
während Arbeit alle 30 Sekunden); nur deren Besitzer führt Providerarbeit aus.
Ein verwaister Besitzer kann nach Ablauf ersetzt werden. Bedarf und fertige
Teilergebnisse bleiben gespeichert. Die API wartet weder beim Start noch beim
Refresh auf vollständige Märkte. `partial` ist ein bedienbarer Zustand.

`market.preparation_failed` / `market.preparation_scheduler_failed` signalisieren
einen erneut eingeplanten Lauf. `process.prewarm_restart` nennt den Backoff.
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
