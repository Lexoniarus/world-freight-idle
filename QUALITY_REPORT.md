# Quality Report – Standards-Reparatur und Gesamt-Review

## Nachtrag: Pylance-Abgleich, 18.09.2026

Die globale VS-Code-Einstellung `strict` wich von der dokumentierten
Nicht-Strict-Grenze ab. Der richtige Projektinterpreter war bereits ausgewählt.
Pyright reproduzierte im Standardmodus 19 Diagnosen; Protokolldeklarationen,
LogRecord-Erweiterungen und Testannahmen wurden korrigiert. Keine pauschalen
Fehlerunterdrückungen. `[tool.pyright]` legt Standardmodus, Python-Version und
Prüfumfang für Pylance und CLI fest. Strict-Konformität wird nicht behauptet.

Erneut ausgeführt: gesamtes Quality Gate einschließlich Pyright 1.1.414
(72 Dateien, 0 Fehler/0 Warnungen), 172 Python-Tests, 1.255 Core-Statements bei
100 % Coverage, 36 Frontendtests, alle Lint-/Format-/Typprüfungen und Build.
Nachweis: `artifacts/pylance-quality.txt`. Pylance hat die Konfiguration laut
lokalem Language-Server-Protokoll neu geladen; die Problems-Ansicht wurde nicht
per UI ausgelesen. Der zuvor ausgeführte Browserlauf bleibt unten historisch
beschrieben; die neue Branch-Abnahme verwendet zusätzlich GitHub Actions.

Architekturreview dieser Änderung: unveränderte Modulgrenzen und DI; explizite
Protokoll-Stubs, gleiche strukturierte Logging-Ausgabe, präzisere Testannahmen.
Keine Änderungen an Profilen, HTTP-Verträgen oder Spielregeln.

Stand: 18.09.2026, Windows, Python 3.11.9, Node 24, Microsoft Edge.
Dieser Bericht ersetzt die vorherige Reparaturabnahme. Er unterscheidet
Werkzeugprüfungen, Architekturreview und tatsächliche Geräteabnahme.

## Ausgeführte Prüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Gemeinsames Gate `python scripts/quality.py` | Bestanden |
| Ruff und Formatprüfung | Bestanden; 72 Dateien |
| mypy einschließlich Profilpflege-CLI | Bestanden; 45 Quelldateien |
| Python-Verhalten, API, Architektur und Manifest | 172 Tests bestanden |
| Core-Statement-Coverage | 100 %, 1.255 Statements, 0 fehlend |
| Funktionstest-Manifest | 145 konkrete benannte Implementierungen zugeordnet |
| Frontend-Unit-, DOM- und Architekturtests | 36 Tests bestanden |
| ESLint, Stylelint, Prettier, checkJs | Bestanden |
| Vite-Produktionsbuild und compileall | Bestanden |
| Playwright / Edge | 9 Szenarien bestanden |

Nachweise: `artifacts/standards-repair-quality.txt` und
`artifacts/standards-repair-browser.txt`. Zwei bestehende Deprecation-Warnungen
von Starlette/httpx bleiben. Coverage bezeichnet Python-Core-Statements;
sie beweist keine vollständige Branch-, Frontend- oder Zustandsabdeckung.

## Behobene Reviewbefunde

1. **Startinitialisierung:** Die öffentliche Service-Methode besitzt nun ihre
   eigene Transaktion. Eine private Methode führt die Schritte darin aus.
   Direkte Aufrufe, bestehende Teilstände, Katalog-/Markt-/Schreibfehler,
   Wiederholung und Reset-Rollback sind getestet. Der Composition Root muss
   die Atomarität nicht mehr selbst gewährleisten.
2. **Lifespan-Cleanup:** Jeder erzeugte HTTP-Client wird unmittelbar in einem
   AsyncExitStack registriert. Tests erzwingen Fehler bei beiden Konstruktoren,
   beim Spiel-/Account-/Auth-Aufbau, im aktiven Scope und beim Schließen jedes
   Clients. Bereits registrierte Ressourcen werden trotzdem geschlossen;
   Fehler bleiben sichtbar.
3. **Profilpflege:** CLI, injizierter ProfileMaintenanceService und Repository-
   Backupadapter sind getrennt. Nutzlastprüfung und Modellübernahme sind
   separate Funktionen. SQL liegt im Repository, konkrete Verdrahtung im
   Composition Root. Die Pflege gehört jetzt zum Core-Manifest und Coverage-Gate;
   das CLI zusätzlich zur Typprüfung.
4. **Zusätzlich reproduzierte Race-Condition:** Ändert Profilpflege ein Modell
   während Routing wartet, konnte Dispatch den alten Kostensatz verwenden.
   Zwei zuvor fehlgeschlagene Regressionen prüfen nun neue Kosten sowie den
   Abbruch bei anschließend unzureichendem Guthaben. Dispatch kalkuliert in
   seiner abschließenden Transaktion mit den aktuellen Fahrzeugwerten neu.
   Guthabenprüfung, Abbuchung und Transport-Snapshot stimmen damit überein.

Profilpflege-Regressionen prüfen außerdem unbekannte und leere Zuordnungen,
doppelte CLI-IDs, ungültige Guthaben, unzureichende Nutzlast, fehlende Spielstände,
Speicher-Rollback, erhaltene fremde Profile und nicht ausgewählte Fahrzeuge.
Backupprüfung liest committed WAL-Daten, schließt uncommitted Werte aus und
verhindert Überschreiben existierender Backups. Bei Backupfehlern wird der
mutierende Service nicht aufgebaut. Alle Pflegeprüfungen nutzen temporäre DBs;
Alex, AlexIPad und andere reale Profile wurden nicht erneut gepflegt.

## Inhaltliches Architekturreview

Abgleich: AGENTS, CODING_STANDARDS, ARCHITECTURE, TESTING, GOAL (21/27–29),
UI DESIGN und Meilensteindokumentation. Geprüft wurden Composition Roots,
HTTP-/Service-/Repository-Grenzen, Provideradapter, Transaktionen, aktive
Frontend-Controller, State, Views, DOM-Helfer, Bildwiederverwendung und Karte.

- Zustandsbehaftete Grenzen besitzen Klassen und explizite Abhängigkeiten.
  Reine Validierungs-, Darstellungs- und Geometriehilfen bleiben funktional.
- Services orchestrieren benannte Aufgaben; SQL und Provider-HTTP liegen in
  ihren Adaptern. Die lokale Pflege führt keine konkrete Store-Erzeugung im
  Service und keine Spielvalidierung im CLI aus.
- Transaktionsgrenzen liegen bei öffentlichen Schreibabläufen; externe Provider-
  Awaits halten keine Schreibtransaktion. Veränderliche Werte werden anschließend
  erneut geprüft. Bereits laufende Transporte behalten gespeicherte Economics.
- Views senden keine Spiel-API-Requests; dynamische Inhalte werden über sichere
  DOM-Bindungen ausgegeben. Veraltete Antworten und Ressourcenfreigabe bleiben
  durch vorhandene Regressionen abgesichert. Der Bildabgleich behält geladene
  Knoten über Polling und Statuswechsel.
- API-JSON und Teile des Spielzustands bleiben dynamisch typisiert. Nicht-Strict-
  checkJs und konkrete SqliteStore-Abhängigkeiten sind dokumentierte Grenzen;
  dies ist kein vollständiger Domain-/Persistenz-Umbau.

Im geprüften Umfang bleiben keine wesentlichen offenen Befunde aus diesem
Review. Diese Aussage ersetzt weder eine unabhängige Sicherheitsprüfung noch
die Abnahme sämtlicher zukünftiger Architektur- und Produktanforderungen.

## Browserprüfung und verbleibende Abnahmegrenzen

Alle neun vorhandenen Szenarien liefen erneut gegen einen isolierten Server:
Spielablauf, Kauf/Disposition, parallele Transporte, Offline-Ankunft und Login,
Fokus/Navigation/Reduced Motion, Provider-/Sessionfehler, zwei getrennte Profile,
Fotoausfall und Erhalt derselben Bildinstanz beim Polling/Transportstart.

Desktop 1440 × 900 und Mobil 390 × 844 wurden anhand aktueller Screenshots visuell
geprüft. Panels und Navigation bleiben bedienbar. Im mobilen Recovery-Screenshot
ist der erwartete kurzlebige Fehler-Toast noch sichtbar. Karten und Fotos werden
in diesem Lauf durch lokale Testbilder ersetzt; kein erneuter öffentlicher
Tile-/Fotoabruf. Frühere reale Fotoprüfungen sind historische Nachweise.

Der aktualisierte Server wurde über python main.py auf 0.0.0.0:8000 neu gestartet.
Die frühere Nutzerbestätigung der iPad-Anmeldeseite bleibt bestehen; eine neue
vollständige physische iPad-/Safari-Spielabnahme wurde nicht durchgeführt.
Docker-Build und entfernter CI-Lauf wurden hier nicht ausgeführt.

UI First, OSM für M1, native ES-Module und main.py bleiben Grundlage. Öffentliche
HTTP-Verträge und Datenbankschema sind unverändert. Unternehmen, eigene Depots,
Satelliten und weitere Wirtschaftssimulation bleiben spätere Arbeit; M1 und
öffentlicher Betrieb sind weiterhin nicht vollständig abgenommen.
