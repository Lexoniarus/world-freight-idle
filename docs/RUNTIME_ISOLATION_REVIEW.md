# Runtime-Trennung: Änderungen, Verantwortlichkeiten und Abnahme

Stand: 27.09.2026, Branch `feature/frontend-v2`, auf Basis des vorhandenen
Routing-Fixes `d11034f`. Grundlage: AGENTS, CODING_STANDARDS, ADR 0006 und
[ADR 0007](adr/0007-runtime-preparation-and-route-projections.md).

## Verantwortungsreview

| Grenze | Verantwortung / Prüfung |
| --- | --- |
| `launcher` / `main.py` | Prozesse, Rollen, Signale, Neustart und Ressourcenfreigabe; keine Spielregeln |
| `GameService` / `FleetService` | Initialisierung, Kauf, Dispatch, Settlement und atomare Bedarfsänderung |
| `MarketLifecycleService` | Veröffentlichte Offers lesen; Worker-Planung außerhalb des Writers; Revisionen vor Veröffentlichung prüfen |
| `MarketPreparationBatchService` | Konsistenter Plan und höchstens eine neue Verbindung pro Runde; keine Prozessverwaltung |
| `PreparationLease` / Worker | Globale Providerberechtigung, Heartbeat, faire Jobwahl, Trace und Fehlerfristen |
| Routingdienste / Repositories | Unveränderte Hin-/Rückwegvalidierung; atomare, gefencete Paare/Anker |
| `RuntimeReader` / SQLite-Adapter | Typisierte skalare Projektion, keine Geometrie-Deserialisierung beim Polling |
| Runtime-API | HTTP, Authentifizierung, öffentliche Sichtbarkeit, Referenzen, ETag und JSON-Projektion |
| `GameState` / `RouteCache` | Unabhängige Ladeströme; coaleszierte, begrenzte und accountgebundene Routendownloads |
| Karten-/Panelcontroller | Relevante Zustandsänderungen darstellen; ausgewählte Geometrie priorisieren; kein Providerzugriff |
| Reparatur-CLI / Repository | Explizite Eingaben und Backup / readonly Prüfung, eng begrenzte Transformation, Archiv und Vollvergleich |

Manuell geprüft: keine zweite Runtime-Persistenz, keine SQL- oder Providerimporte
im Domainmodell, keine Kandidatenbildung unter einem Writer im Produktionspfad,
keine Provider-Awaits in Spielertransaktionen. Historische Koordinaten bleiben unverändert. Private
Kosten und Energie werden nicht in öffentliche Verkehrsantworten aufgenommen.
Die Parameter des Routing-Fixes bleiben unverändert (5 / 1.000 m / 10 m /
25 / 120 s; Wiederprüfung 24 h / 1 h / 60 s).

## Reparaturprobe

Die erste Offline-Probe erfolgte auf einer privaten SQLite-Kopie mit 164
Transporten: genau ein aktiver und ein abgeschlossener Transport entsprachen
dem bekannten Muster. Beide wurden repariert; alle anderen Werte und Tabellen
stimmten im Vollvergleich überein. Originaldokumente sind mit SHA256 archiviert.
Diese erste Probe veränderte den echten Spielstand nicht.

Eine weitere Kopie wurde mit normalem Spiel-Settlement gelesen. Beim betroffenen
Profil wurden 17 fällige Fahrten einmalig abgeschlossen. Ein zweiter Read änderte
Guthaben und abgeschlossene Anzahl nicht erneut. Andere Profile blieben lesbar.
Neue Dispatches benötigen weiterhin vorbereitete Hin- und Rückwege.

Nach ausdrücklicher Nutzerfreigabe erfolgte zusätzlich die Live-Aktivierung.
API und Worker wurden beendet; das danach erstellte frische Backup enthielt
bereits 174 Transporte. Wieder entsprachen genau zwei Fälle dem bekannten
Muster. Nach vollständigem Abgleich wurde die geprüfte Ausgabe als
`data/game.db` übernommen, die Originaldatei samt Sidecars separat archiviert.
Damit bleiben auch die nach der ersten Probe hinzugekommenen Transporte
erhalten. SQLite-Backup, JSONL-Originalarchiv, Prüfsummen und Aktivierungsbericht
stehen ausschließlich im ignorierten Datenverzeichnis. Der Nutzer startete
regulär neu, nachdem die automatische Ausführungsprüfung den Hintergrundstart
blockiert hatte. Die API antwortet mit HTTP 200. Der aktive Spielstand bestätigt
17 normale Abschlüsse sowie bereits zwei neue Dispositionen des betroffenen
Profils. Guthabendifferenz, Auszahlungen und neue Dispatchkosten stimmen exakt
überein; die 17 vorhandenen Fahrzeuge bleiben erhalten.

Ein kalter Browserabruf deckte wiederholte Validierung derselben historischen
Geometrien während Settlement auf. Das spielergebundene Repository behält nun
höchstens 64 unveränderliche, validierte Transportobjekte innerhalb seines
Lebenszyklus. Jeder Zugriff liest die Datenbank erneut; nur bei vollständiger
Gleichheit aller Spalten einschließlich des Originaldokuments wird das Objekt
wiederverwendet. Geänderte Spalten oder Dokumente werden erneut validiert;
Settlement und Schutz abgeschlossener Historie bleiben atomar. Der Browser
startet seinen koaleszierten Runtime-Abruf bereits während des Kartenaufbaus.

## Testumfang

Der gemeldete stille Start wurde zusätzlich mit einer echten Windows-Konsole
reproduziert: `CREATE_NO_WINDOW` ließ die geerbte Ausgabe mit `Bad file
descriptor` scheitern. Ohne dieses Flag wird dieselbe Konsole verwendet und
die Ausgabe funktioniert. Der Starter gibt ein eigenes `process.start`-Event
aus; API-Startmeldungen und Fehler werden wieder sichtbar.

Der Start wurde zusätzlich über das globale Windows-Python aus der
Repositorywurzel, über den äußeren lokalen Starter und aus einem fremden
Arbeitsordner mit isolierten Datenbanken geprüft: Health und Login jeweils
HTTP 200, geordnetes Prozessende jeweils Exit 0. Ein automatisierter Test
startet beide echten Prozesse aus einem fremden Arbeitsordner und prüft deren
Freigabe. Gegentests erhalten explizite virtuelle Umgebungen und decken den
fehlenden lokalen Interpreter sowie begrenztes Shutdown ab.

Neue Verhaltenstests und explizite Gegentests stehen in `test_process_isolation`,
`test_preparation_isolation`, `test_runtime_views` und `test_transport_repair`.
Sie decken Lease-Verlust, doppelte Initialisierung/Worker, Shutdown-Fehler,
veraltete Publikation, readonly Transaktionen, koaleszierten Bedarf, kompakte
Projektion, fremde abgelaufene Routen, HTTP 304 ohne Geometrie-Lesen,
unbekannte Reparaturschäden, Archiv-/Tabellenabweichungen und wiederholtes
Settlement ab. Neue konkrete Core-Callables sind dem Manifest zugeordnet.

Frontend-Gegenproben prüfen Priorität, vier parallele Abrufe, 200 Cacheeinträge,
verspätete Antworten, Accountwechsel, unabhängige Verkehrsfehler und fehlende
Geometrie. Browserfälle verwenden einen separaten Worker mit deterministischen
Providern. Vor jedem unabhängigen Browserfall wird alter Testkonten-Bedarf
gefencet und pausiert; der öffentliche API-Vertrag enthält diesen Testhelfer nicht.

Die ursprünglichen Routingregressionen, einschließlich Wolfsburg und Folgefahrt,
bleiben Teil der vollständigen Suite. Die bereits dokumentierte begrenzte
Live-Gegenprobe des Routing-Fixes wird nicht als neuer Live-Test ausgegeben.

## Messbedingungen und Ergebnisnachweis

Lokale Hardware: Intel Core i5-1235U, 12 logische CPUs, etwa 8 GiB RAM,
Windows, Python 3.11.9. Der reproduzierbare Lauf benutzt eine neue private Kopie
mit drei Profilen und bis zu 35 Fahrzeugen, tatsächliche historische Snapshots,
separate Runtime-/Workerprozesse und deterministische Providerantworten.

```powershell
python -m tests.runtime_benchmark PFAD_ZUR_REPARIERTEN_KOPIE NEUES_PRIVATES_MESSVERZEICHNIS
```

Je Ressource werden 100 Reads pro Profil gemessen. JSON-Größe wird vor
Kompression geprüft. Zuerst lädt jedes der drei Profile in einem frischen
Browserkontext mit kaltem Spielerzustand, einschließlich fälligem Settlement.
Gemessen wird vom Seitenaufruf bis zur sichtbaren Flotte; danach folgen zwei
Pollingintervalle zur Prüfung unveränderter Geometriedownloads. Lokale
Tile-Fixtures vermeiden externe Medienlatenz. Anschließend werden die HTTP-
Messreihen ausgeführt. Screenshots, Sitzungen und Spielstände verbleiben privat.
Ein echter iPad-Test ist weiterhin eine gesonderte Geräteabnahme.

Die ersten isolierten Servicemessungen ergaben etwa 33 ms p95 für kompakte
Reads; dieselbe Kandidatenplanung mit 33.345 Kandidaten sank von rund 11–12
auf 2,1 Sekunden. Diese Einzelmessungen ersetzen nicht die HTTP-/Browserabnahme.
Ein früherer Zwischenstand bestand das vollständige Quality-Gate mit 559
Python-Tests, 100,00 % app-Statement-Coverage und 113 Frontend-Verhaltenstests
sowie 31/31 Browsertests. Diese Zahlen sind historisch; nach der Erweiterung
um den gemeinsamen Vorrat und die nachgeladene Karte gelten ausschließlich
die aktuellen vollständigen Prüfungen und Lastresultate im
[Qualitätsbericht](../QUALITY_REPORT.md).

Live-Aktivierung und Rückfallverfahren: [Betriebsanleitung](RUNTIME_OPERATIONS.md).
Commit/Push aktivieren weder eine reparierte Datenbank noch eine Integration
nach `main`; dafür gilt weiterhin das dokumentierte Reviewverfahren.
