# Durchgängig befahrbare Standortverbindungen – 27.09.2026

Basis: `5d7ff77`, Umsetzung auf dem vom Nutzer freigegebenen bestehenden
`feature/frontend-v2`. Abgleich mit `AGENTS.md` und `CODING_STANDARDS.md`.
Die vollständige Suite und Gesamtintegration führt der Nutzer aus.

## Fehlerursache und Freigaberegel

In Wolfsburg lieferte Locate einen lokalen Straßenpunkt rund 191 Meter vom
Volkswagenwerk entfernt, von dem Valhalla keinen Weg nach Stendal fand.
Locate war bisher bereits als validierter Anker gespeichert worden. Die letzte
Hinfahrt endete tatsächlich an einem anderen Straßenpunkt rund 504 Meter vom
Werk entfernt. Auch HTTP 200 kann einen vom angefragten Anker abweichenden
Geometrie-Endpunkt enthalten. Ein erfolgreicher Hinweg oder Locate-Treffer
belegt deshalb keinen nutzbaren nächsten Start.

Für jede Lieferung und jede Anfahrt verlangt die Readiness jetzt echte
Truck-Routen A → B und B → A. Alle vier Geometrie-Endpunkte müssen höchstens
10 Meter vom jeweiligen vorgesehenen Anker entfernt liegen. Die Rückrichtung
hat eine eigene vom Provider berechnete Geometrie. Markt, Fahrzeug-Eignung,
Quote und Dispatch behalten das gemeinsame Readiness-Freigabetor. Auch der
direkte Planungspfad verwendet den Verbindungsprüfer und hält den gewählten
Abholanker zwischen Anfahrt und Lieferung fest.

## Begrenzte automatische Reparatur

- Höchstens fünf unterschiedliche Kandidaten je Facility, über alle Suchphasen
  zusammen; bestehender Anker zuerst, anschließend reale Locate-Punkte nach
  Entfernung. Verschachteltes `edges[].edge.access.truck` wird ausgewertet.
- Abstand stets zur ursprünglichen Facility-Koordinate, höchstens 1.000 Meter.
  Auch Adress-Fallback und erneutes Locate dürfen diese Grenze nicht umgehen.
  Fehlt die Facility-Koordinate, ist die aufgelöste Adresse die Suchreferenz.
- Höchstens 25 Kandidatenpaare und 120 Sekunden einschließlich Provider-Limiter.
  Zuerst bestehende Anker erhalten, dann geringste zusätzliche Standortabweichung;
  der vorhandene gecachte Adress-Fallback bleibt nachgeordnet.
- Aktuell zertifizierte Anker bleiben für weitere Ziele stabil. Ein einzelnes
  unerreichbares Ziel verschiebt keinen bereits geprüften Ausgangspunkt.
- Nur ein vollständig erfolgreiches Paar darf Anker ersetzen. Keine künstlichen
  Straßenstücke, umgedrehten Polylinien oder automatischen Fahrzeugversetzungen.

`ROUTING_ANCHOR_MAX_SNAP_M` hat jetzt den Default 1000. Kleinere Grenzen bleiben
möglich; Werte über 1000 werden vom Resolver abgelehnt. Eine ausdrücklich auf
250 gesetzte Prozesskonfiguration muss für die Wolfsburger Reparatur angepasst
werden. `.env.example` dokumentiert nur die Prozessvariablen; sie wird nicht
von `main.py` eingelesen.

## Speicherung, Parallelität und Wiederprüfung

Die additive Tabelle `routing_connection_proofs` bindet beide gerichteten
Routenrevisionen, Anker und `truck-connected-v2` zusammen. Anker, beide
Routenpayloads und gemeinsamer Nachweis werden in einer Transaktion publiziert.
Die gemeinsame Lease des ungeordneten Paars sowie Facility- und gerichtete
Relations-Leases werden in stabiler Reihenfolge erworben und bei Abbruch
freigegeben. HTTP findet außerhalb von Schreibtransaktionen statt.

Nach Provider-Awaits werden Katalog, Provideridentität/-revision und die alten
Anker erneut verglichen. Im Veröffentlichungstransaktionsblock werden außerdem
Lease-Besitz, Anker und beobachtete Providerrevision geprüft. Überholte Resultate
werden verworfen. Numerisch gleiche Koordinaten behalten ihren Fingerprint auch
nach der SQLite-Konvertierung von Integer zu REAL.

Die neue Version verwirft bisherige positive und negative Relationsnachweise.
Alte Locate-Anker sind lediglich Kandidaten. Erfolgreiche Paare verfallen nach
24 Stunden, definitive Fehler nach einer Stunde. Anbieterfehler, Rate Limits,
Timeout und ausgeschöpftes Reparaturbudget werden nach 60 Sekunden erneut
vorbereitbar. Beobachtete Graphänderungen invalidieren sofort. Wiederprüfung
erfolgt nach Nachfrage durch den vorhandenen Worker; kein Weltkatalog-Prewarm.

Öffentliche Spiel-API und gespeicherte Transport-Snapshots bleiben unverändert.
Laufende Fahrten enden auf ihrer gespeicherten Route. Neue Dispositionen brauchen
den neuen Nachweis. Der Gültigkeitszeitraum ist eine begrenzte Providerprüfung,
keine Garantie gegen spätere reale Straßen- oder Graphänderungen.

## Zuständigkeitsreview

| Baustein | Verantwortung |
| --- | --- |
| `RoutingCandidate`, `ValidatedConnection`, Identitäten | Immutable interne Werte, Entfernungen und stabile Nachweisbezüge |
| `ValhallaTruckAnchorLocator` | HTTP, Truck-Metadaten, echte Locate-Kandidaten und Providerfehler |
| `RoutingAnchorResolver` | Bestehende Anker priorisieren, Suchreferenz und 1-km-Grenze, nachgeordneter Adress-Fallback; keine Ankerpublikation |
| `RoutingConnectionValidator` | Begrenzte Kombinationen, beide Truck-Routen, vier Endpunktprüfungen und richtungsbezogene Versuchsprotokolle |
| `RoutingReadinessService` | Wiederverwendung/Verfall, Lease-Orchestrierung und Prüfung veränderlicher Eingaben nach Awaits |
| `SqliteRoutingReadinessStore` | SQL, persistente gemeinsame Nachweise und atomare Veröffentlichung mit Schreibschutz |
| `DispatchPlanningService` | Bestehende Readiness nutzen; direkter Pfad nutzt denselben Prüfer mit festgehaltenem Abholanker |

Neue konkrete Core-Callables sind im Function-Test-Manifest erfasst. Die
Verantwortlichkeiten wurden zusätzlich zu den Architekturtests manuell geprüft.

## Abnahme auf isolierter Spielstandkopie

Vor der Prüfung wurde per SQLite-Backup eine konsistente Sicherung erzeugt:
`data/backups/game-before-routing-fix-20260927-170052.db`.
Die isolierte Wiederherstellung liegt unter `artifacts/wolfsburg-acceptance.db`.
Spielerdaten, Backups und Prüfartefakte sind nicht für Git vorgesehen.

Die erste Live-Gegenprobe benötigte acht Provideranfragen. Die abschließende
Paarprüfung nach Vereinheitlichung des Fingerprints benötigte zwei weitere
Routenanfragen (insgesamt zehn):

1. Wolfsburg → Stendal: erster Kandidat scheitert; der echte Kandidat bei
   52.429326 / 10.780732 besteht beide Richtungen (143,915 / 143,496 km).
2. Hashvergleich der Spieler-, Fahrzeug- und Transporttabellen vor/nach reiner
   Routingvorbereitung: identisch. Original-Spielstand nicht verändert.
3. Regulärer Marktaufbau, Quote und Dispatch des vorhandenen AlexIPad-LKW zum
   Schnellecke Wolfsburg Logistics Campus: 6,724 km, Transport aktiv.
4. Ankunft auf der Kopie regulär abgewickelt; anschließendes reguläres Angebot
   und Quote zurück zum Volkswagenwerk erfolgreich. Voriges Routenende und
   nächster Routenstart stimmen überein (0 Meter); keine zusätzliche HTTP-Anfrage
   für Quote oder Dispatch. Der Folgeauftrag zurück zum Volkswagenwerk wurde
   in der abschließenden Prüfung auch regulär gestartet (Status `active`).

Lokale Belege: `artifacts/wolfsburg-live-result.json` und
`artifacts/wolfsburg-live-output.txt` sowie
`artifacts/wolfsburg-followup-result.json`. Die versionierte Fixture
`tests/fixtures/wolfsburg-routing.json` enthält ausschließlich Providerantworten,
keine Spielerkonten oder Spielstände. Sie erlaubt Offline-Reproduktion.

## Gezielte Prüfungen und verbleibende Gesamtabnahme

Routing-, Repository-, Markt-, Fahrzeugmarkt-, Anfahrt- und Dispatchtests prüfen
unter anderem fehlende Rückwege, vier verschobene Endpunkte, Kandidatenwechsel
nach HTTP 200, alte positive/negative Caches, TTLs, parallele Gegenrichtungen,
Abbruch, Lease-Verlust, Transaktionsrollback, wechselnde Eingaben und stabile
zertifizierte Anker. Architektur und Function-Test-Manifest gehören zum gezielten
Lauf; Typprüfung, Lint, Format und Coverage beziehen sich auf betroffene Dateien.
Abschluss: 99 gezielte Tests plus zwei Konfigurationstests bestanden;
597/597 Statements in den acht ausgewiesenen Routing-/Dispatchmodulen
abgedeckt. Ruff und Format für 22 geänderte Pythondateien, mypy für 13
geänderte Core-Dateien und Pyright ohne Fehler. `git diff --check` bestanden.
Details stehen im aktuellen `QUALITY_REPORT.md`.

Keine vollständige Suite, kein vollständiges Quality-Gate und keine neue
Browser-Gesamtabnahme wurden für diesen Fix ausgeführt oder behauptet. Diese
Gesamtintegration bleibt vereinbarungsgemäß beim Nutzer. Der laufende Server
und der echte Spielstand wurden nicht auf den Fix umgestellt; nach Übernahme
bereitet der vorhandene Worker nachgefragte Verbindungen unter der neuen Regel
vor. Vor späterer Aktivierung ist bei zwischenzeitlichem Spielbetrieb ein
frisches SQLite-Backup erforderlich.


## Separater Nebenbefund im vorhandenen Altbestand

Beim zusätzlichen Lesen der gesamten AlexIPad-Transporthistorie wurde ein
bereits vorhandener Snapshot mit verschiedenen Start-/Abhol-Facilities und
fehlender Anfahrt abgelehnt (`Distinct pickup requires an approach route.`).
Der Befund ist auf dem vor dem Fix erstellten, nur lesend geöffneten Backup
reproduzierbar: einer von 58 historischen Transportdatensätzen. Die betreffende
Domainvalidierung wurde in diesem Fix nicht geändert. Historie und Snapshot
bleiben unangetastet; der normale Dispatch-/Ankunftspfad der Kopie funktioniert.
Eine gesonderte historische Datenprüfung ist nicht Teil der Routingreparatur.
