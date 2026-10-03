# ADR 0007: Runtime, Vorbereitung und Routengeometrien trennen

Status: umgesetzt auf `feature/frontend-v2`; vollständige Abnahme im
[Runtime-Review](../RUNTIME_ISOLATION_REVIEW.md).

## Problem

Die Vorbereitung erzeugte große Kandidatenpools im API-Prozess und teilweise
unter einer SQLite-Schreibsperre. Startup und Spieleraktionen warteten dadurch
auf Arbeit für andere Spieler. Wiederkehrende Frontend-Abfragen luden dieselben
historischen Geometrien mehrfach. Ein ungültiger optionaler Anfahrtsplan in
Alttransporten verhinderte außerdem das Laden eines betroffenen Spielstands.

## Entscheidung

`python main.py` überwacht zwei Prozesse. `--role runtime` startet ausschließlich
HTTP, `--role prewarm` ausschließlich die nachfragegesteuerte Vorbereitung.
Ein ausgefallener Worker startet mit 1 bis maximal 30 Sekunden Backoff erneut;
die API bleibt erreichbar. EOF der Supervisor-Pipe fordert geordneten Shutdown
an, anschließend gelten begrenzte Terminate-/Kill-Fristen. Docker benutzt
weiterhin den Standardeinstieg.

Beide Prozesse benutzen dieselbe relationale Datenbank. Produktiv ist dies
PostgreSQL/Supabase; SQLite bleibt auf Tests und Offline-Werkzeuge beschränkt.
PostgreSQL verwendet native psycopg-Transaktionskontexte, read-only
Repeatable-Read-Snapshots und den bestehenden Advisory Lock für Schreib-UoWs.
Finanzielle Aktionen werden bei Datenbankfehlern nicht automatisch wiederholt.

Runtime-Aktionen schreiben nur einen dauerhaften Vorbereitungsbedarf. Wiederholte
Reads erhalten dieselbe Generation; relevante Änderungen invalidieren sie in
der Spielertransaktion. Listen lesen veröffentlichte Offers und persistierte
Coverage-Diagnosen. Refresh antwortet sofort mit nutzbaren Offers und Status.
Quote und Dispatch haben in der Produktionsverdrahtung keinen Provider-Fallback.

Der Worker bildet Kandidaten außerhalb von Schreibtransaktionen, nutzt Indizes
für Facilities und Trades und liest Routingnachweise in einer gemeinsamen
Lesetransaktion mit lokalem Memo. Pro Spieler und Runde wird höchstens eine
neue Standortverbindung geprüft. Flotte, Offers, Katalog, Generation, Provider-,
Anker- und Routenrevisionen sowie Lease-Besitz sichern die Veröffentlichung.
Eine globale erneuerbare Worker-Lease schützt Providerarbeit; Paar- und
Standort-Leases schützen weiterhin deren atomare Ergebnisse. Auch explizites
CLI-Prewarm muss die globale Lease halten.

Die Zweiwegregel bleibt unverändert: fünf Kandidaten je Standort, höchstens
1.000 Meter vom Original, zehn Meter Endpunkttoleranz, 25 Kombinationen und
120 Sekunden Budget. Nachweise gelten maximal 24 Stunden; definitive Fehler
werden nach einer Stunde, vorübergehende Fehler nach 60 Sekunden erneut fällig.
Abgeschlossene Bedarfsläufe werden spätestens nach 60 Sekunden auf veränderte
Nachweise/Angebotsablauf geprüft. Es gibt keinen synchronen Weltkatalog-Preload.
Wenn kein Spielerbedarf offen ist, bereitet derselbe Worker opportunistisch
genau einen globalen Stadt-/Modell-/Band-Kontext und ein bidirektionales
Routenpaar pro Runde vor. Neuer Spielerbedarf verdrängt die nächste globale
Runde; ein bereits begonnenes Paar darf atomar beendet werden.

Typisierte SQLite-Leseports projizieren kompakte aktive Transporte ohne
Koordinatenarrays. Authentifizierte Geometrieabrufe laden genau einen
historischen Snapshot; öffentliche Sichtbarkeit wird auch vor HTTP 304 geprüft.
Die Referenz enthält Besitzer, Transport und Projektionsversion. Ein Array plus
Abschnittsindizes vermeidet Duplikate. ETag und Gzip ergänzen den Browsercache.

Der Browser veröffentlicht Runtime zuerst und lädt Markt, Verkehr und Geometrien
unabhängig. Ein accountgebundener Cache coalesziert Downloads, priorisiert
ausgewählte/eigene Routen und begrenzt Parallelität auf vier sowie Inhalt auf
200 Einträge. Geometrie-Updates berühren die Karte; unveränderte Panelinhalte
werden nicht neu aufgebaut. Ohne Route wird keine Bewegung extrapoliert.

Auch das Kartenmodul und seine WebGL-Initialisierung folgen erst nach der ersten
Darstellung des Runtime-Zustands. `DeferredMap` besitzt den asynchronen
Lebenszyklus und hält jeweils den neuesten Darstellungszustand, während der
Renderer lädt. Controller kennen nur den typisierten `GameMap`-Vertrag und ein
Ready-Ereignis; sie greifen nicht auf native Karten- oder Kameraobjekte zu.
Abmeldung verwirft ausstehende Erstellung und entfernt verspätete Renderer.
Ein Kartenladefehler lässt Flotte, Filter und Spielaktionen verfügbar.
Fahrzeugfarbbilder im Panel werden erst bei Sichtbarkeit vorbereitet; der
Bildcontroller besitzt den Observer und gibt entfernte Bildbindungen frei.

Beim Settlement werden bereits validierte unveränderliche Teilstrecken direkt
mit den gespeicherten Gesamtfakten verglichen. Dadurch entfallen erneute
Geometrieerzeugung und Punktvalidierung bei jedem Statuswechsel; alle neuen und
eingelesenen `RouteSnapshot`-Werte durchlaufen weiterhin ihre vollständige
Eingangsvalidierung.

## Historische Reparatur und Folgen

Kein Legacy-Mapping im Laufzeitmodell. Das Offline-Werkzeug akzeptiert nur das
bestätigte Muster: unterschiedliche Start-/Abholfacility derselben Stadt,
fehlende Anfahrt, Lieferroute exakt gleich Gesamtroute, sonst vollständig
valider Transport. Es entfernt ausschließlich den ungültigen optionalen Plan.
Neue Dispatches behalten sämtliche strengen Prüfungen.

Readonly-Quelle, erfolgreiches SQLite-Backup, neue Ausgabe, Originaldokumente
mit Prüfsummen und vollständiger Quellen-/Zielabgleich sind zwingend. Normales
Settlement rechnet fällige Transporte genau einmal ab. Die Aktivierung einer
reparierten Kopie bleibt ein getrennter Betriebsschritt mit gestoppten Schreibern.

Die Prozessgrenze benötigt gemeinsamen relationalen Datenbankzugriff. Die
globale Worker-Lease verhindert parallele Providerarbeit auch über Prozesse.
Der SQLite-Einzelwriter bleibt nur für Test- und Offline-Betrieb relevant.
Automatisierte Tablet-Browsertests ersetzen keine echte iPad-Abnahme.
