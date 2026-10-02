# Qualitätsbericht: Supabase-Produktionsruntime

Stand: 02.10.2026. Branch `fix/supabase-runtime-current-head`, Basis
`origin/main`. Dieser Abschnitt dokumentiert die aktuelle Abnahme. Alle Berichte
unterhalb der Trennlinie bleiben als historische Nachweise unverändert erhalten.

## Ergebnis und Verantwortlichkeiten

PostgreSQL in Supabase ist die produktive Persistenz für Spielstand, Welt- und
Fahrzeugkatalog. SQLite bleibt auf Tests und ausdrücklich lokale Offline-Arbeit
begrenzt. Der Backend-Adapter besitzt Verbindungen und Transaktionen; Browser und
Supabase-Client greifen nicht direkt auf die privaten Anwendungsschemas zu.

Der Login versucht zuerst Supabase Auth. Nur wenn dort noch kein Passwortkonto
für einen der drei migrierten Altaccounts existiert, verwendet der Browser den
Same-Origin-Endpunkt. Die private Zuordnung in `game.account_emails` löst dabei
die hinterlegte E-Mail auf. Kompakte historische Spieler-IDs bleiben erhalten;
neue Registrierungen laufen ausschließlich über Supabase Auth.

Die Schemas `game`, `world_catalogue` und `vehicle_catalogue` sind für `PUBLIC`,
`anon` und `authenticated` gesperrt. RLS ist als zusätzliche Schutzschicht auf
allen Tabellen aktiv. Der Startup-Check bricht bei einer Tabelle ohne RLS ab.
Die Backend-Rolle behält den für den Adapter erforderlichen Besitz- und
`BYPASSRLS`-Zugriff. Das manuelle Architekturreview bestätigt weiterhin die
Trennung von Domain, Services, Transport und Persistenz sowie die zentrale
Browser-API in `frontend/api.js`.

## Automatisierte Abnahme

`.venv/Scripts/python.exe -X utf8 scripts/quality.py` wurde vollständig mit
Exitcode 0 ausgeführt. Der reale Supervisor-Test bestand separat in 5,51 s. Der
abgedeckte Hauptlauf meldete **612 bestanden, 1 gezielt ausgelassen**, **100,00 %
App-Statement-Coverage** bei **7.179 Statements** und 62 Warnungen aus bestehenden
Testabhängigkeiten beziehungsweise Ressourcen-Cleanup. Zusätzlich bestanden
**120 Frontend-Verhaltenstests**, Ruff, Ruff-Format, mypy für 165 Dateien,
Pyright, ESLint, Stylelint, Prettier, TypeScript/checkJs, Produktionsbuild und
compileall.

`npm run test:e2e` meldete **33 bestanden** in 6,3 Minuten. Desktop-, Tablet- und
Mobilfälle liefen über die isolierte Browser-Settings-Schicht; der Playwright-
Server erhält weder `DATABASE_URL` noch Supabase-Konfiguration und griff nicht
auf Produktionsdaten zu. Kartenregressionsbilder sowie die Live-Aufnahme wurden
visuell geprüft. Ein `WinError 10054` beim absichtlich abgebrochenen Netzwerkfall
ist erwartetes Windows-Socket-Cleanup; der zugehörige Test bestand.

## Live-Verifikation ohne Gameplay-Mutation

Die Remote-Migrationsliste enthält
`20261002114339_harden_private_schemas`. Der Inhalt entspricht der lokalen,
bereits angewendeten Migration; sie wurde nicht erneut ausgeführt. Alle **72 von
72** Anwendungstabellen besitzen RLS. Tabellen- und Funktionsrechte sowie
Schema-Usage für `PUBLIC`, `anon` und `authenticated` sind jeweils **0**. Die drei
gezielten Runtime-FK-Indizes sind vorhanden.

Der produktive Backend-Adapter validierte Schema 1.2.0 und lud **558**
Weltstandorte sowie **14** Fahrzeugmodelle. Ein vorhandener migrierter Account
konnte sich über die Legacy-Brücke anmelden; Karte, Kapital, Reputation und vier
Fahrzeuge wurden geladen und als synchronisiert angezeigt. Der anschließende
Logout bestand. Es wurden keine Käufe, Dispositionen oder sonstigen
Gameplay-Mutationen ausgelöst.

Der Supabase Security Advisor meldet erwartungsgemäß 72 Info-Hinweise
`rls_enabled_no_policy`: Für die vollständig privaten Schemas sind keine
Browser-Policies vorgesehen. Die 31 Hinweise zu Katalog-Fremdschlüsseln, der
fehlende Primärschlüssel der einzelnen Schema-Versionszeile und aktuell ungenutzte
Indizes werden ohne gemessenen Bedarf nicht verändert. Hosting, Recovery,
Backup-/Restore-Abnahme, öffentliche Provider und eine reale iPad-Abnahme bleiben
separate Betriebsarbeit.

---

# Qualitätsbericht: gemeinsamer Vorrat und schnelle Runtime

Stand: 28.09.2026. Branch `feature/frontend-v2`, Basis `d11034f`.
Die folgenden Abschnitte vor der Trennlinie gelten für den aktuellen Gesamtstand.
Ältere Berichte dokumentieren historische Zwischenstände.

## Verhalten und Verantwortlichkeiten

Die Markt-API liefert für das gewählte Fahrzeug höchstens drei tatsächlich
verfügbare Angebote je Entfernungsklasse. Persönliche IDs und Konditionen bleiben
stabil; ein Refresh würfelt nichts neu aus. Der gemeinsame Vorrat ist nach Stadt,
konkretem Modell und Streckentyp organisiert. Der Worker versorgt wartende LKW,
bevorstehende Ankünfte ab 60 Minuten, Reserven von mindestens zehn und die übrigen
Katalogmodelle in dieser Reihenfolge. Eine Vorlage ist einmal je Spieler nutzbar;
andere Spieler behalten ihre Verwendungsmöglichkeit. Verbrauch, Geld und Transport
sind eine gemeinsame Transaktion. Vorbereitete persönliche Reserve rückt ohne
Provideraufruf nach. Ungenutzte Angebote bleiben nach Abfahrt und Zeitablauf erhalten.

Unbegrenzte Angebotslaufzeit verlängert keine Straßenfreigabe: Anfahrt und Lieferung
benötigen weiterhin beide bestätigten Richtungen und aktuelle Nachweise. Alte
Straßen- oder Kataloggrundlagen sperren ein Angebot, ohne dessen Konditionen oder
historische Transporte zu ändern. Persistierte Bedarfsversionen, Checkpoints,
Leases und erneute Zustandsabgleiche schützen Veröffentlichungen.

Die API und der Worker laufen getrennt. Der Browser lädt den Spielstand unabhängig
von Markt, Verkehr, Routengeometrien und jetzt auch dem Kartenrenderer. Eine eigene
Komponente lädt die Karte nach dem ersten Runtime-Render und besitzt ihren gesamten
Lebenszyklus. Farbbilder außerhalb des sichtbaren Panels werden erst bei Bedarf
vorbereitet. Beim Settlement werden validierte unveränderliche Teilstrecken direkt
mit Gesamtfakten verglichen, statt bei jedem Statuswechsel alle Punkte neu zu prüfen.
Eingelesene und neu erzeugte Routensnapshots werden weiterhin vollständig validiert.

Manuelles OOP-/Verantwortlichkeitsreview:
[MARKET_STOCK_REVIEW](docs/MARKET_STOCK_REVIEW.md),
[ADR 0008](docs/adr/0008-shared-market-stock.md) und
[Runtime-Grenzen](docs/adr/0007-runtime-preparation-and-route-projections.md).

## Vollständige Abnahme

Der abschließende vollständige Lauf von `python scripts/quality.py` ist mit
Exitcode 0 bestanden: **589 Python-Tests**, **100,00 % app-Statement-Coverage**
(7.183 von 7.183 Statements), **117 Frontend-Verhaltenstests** sowie Ruff,
Formatierung, mypy, Pyright, ESLint, Stylelint, Prettier, checkJs, Produktionsbuild
und compileall. Die Python-Suite benötigte 31 Minuten 20 Sekunden. Die zwei
Deprecation-Warnungen aus Starlette/httpx und anyio betreffen bestehende
Testabhängigkeiten; keine Tests wurden übersprungen oder als erwarteter Fehler
markiert. Architektur- und Manifestprüfungen sind Teil dieses Gesamtlaufs.
Frühere beziehungsweise unterbrochene Läufe gelten nicht als Abnahme.

`npm run test:e2e`: **33 bestanden**, 11,9 Minuten. Desktop, Mobil und Tablet;
Vorratsauswahl, stabiler Refresh, verzögertes Kartenmodul, Anfahrt/Abholung,
Abrechnung nach erneutem Login, mehrere Spieler, Fahrzeugwechsel, Fehleranzeigen
und Kartenregressionen. Zuvor wurden alle neun korrigierten Browserfälle gezielt
erneut bestanden. Browser plugin not available; vorhandene Playwright-Konfiguration
mit Edge auf `http://127.0.0.1:8011` und isolierter Datenbank verwendet.

Die gerenderten Prüfungen bestätigen Seitentitel/URL, nicht leere Inhalte,
fehlende Fehler-Overlays, bedienbare Auswahl/Navigationsaktionen und unveränderte
Spielzustände nach Wiederholung. Desktop- und Mobilaufnahmen wurden zusätzlich
visuell geprüft. Absichtlich abgebrochene HTTP-Verbindungen lösen unter Windows
gelegentlich `WinError 10054` im asyncio-Socket-Cleanup aus; die zugehörigen
Fehler-/Wiederholungsprüfungen bestehen. Dieser Logeintrag wird nicht unterdrückt.

## Leistungsabnahme des aktuellen Stands

Repräsentative isolierte Kopie: drei Spieler, 35 Fahrzeuge, historische reale
Geometrien; Windows 11, Intel Core i5-1235U, 12 logische CPUs, etwa 8 GiB RAM,
Python 3.11.9, Edge/Playwright. Separate API und laufender Fixture-Worker;
keine parallel laufenden Builds oder Testsuiten. Provider und Basiskarten verwenden
lokale Fixtures. Browserprofile starten vor den HTTP-Reihen kalt; das erste Profil
schließt 17 fällige Fahrten durch reguläres Settlement ab.

| Prüfung | Ergebnis |
| --- | --- |
| Erste bedienbare Flotte, drei Browserkontexte | 3.391 / 590 / 572 ms |
| Runtime, 300 Reads | p95 83,72 ms; Maximum 256,67 ms |
| Öffentlicher Verkehr, 300 Reads | p95 73,37 ms; Maximum 128,71 ms |
| Markt, 300 Reads | p95 82,44 ms; Maximum 266,80 ms |
| Health, 300 Reads | p95 11,48 ms; Maximum 41,01 ms |
| Runtime plus Verkehr, JSON vor Kompression | höchstens 92.931 Byte, etwa 91 KiB |
| Wiederholte unveränderte Geometriedownloads | 0 |
| Browserfehler | 0 |
| Gemeinsame Vorlagen während der Probe | 0 → 12; Workerfortschritt bestätigt |
| Quellenprüfsumme | unverändert |

Der Grenzwert von 250 ms gilt wie vereinbart für p95; einzelne höhere Latenzen
sind in der Tabelle sichtbar. Am 28.09.2026 hat der Nutzer den einmaligen
Kaltstart mit 3,39 Sekunden ausdrücklich akzeptiert. Das ursprüngliche
Zwei-Sekunden-Ziel wird für diesen Start mit fälligem Settlement nicht als
erfüllt behauptet. Weitere Spielerstarts, laufende Reads, Datenmenge und
Geometrie-Wiederverwendung erfüllen ihre unveränderten Grenzwerte. Das
Benchmark-Werkzeug protokolliert den ersten Kaltstart separat und prüft die
weiteren Spielerstarts weiterhin gegen zwei Sekunden.

Zeitspuren und Profiling begründeten die Optimierungen an Routenvalidierung,
Karteninitialisierung und Farbkomposition. Eine frühere Messung erzielte 1,33 s;
die aktuelle isolierte Wiederholung ist maßgeblich. Ein zusätzlicher Lauf mit
gleichzeitiger Typprüfung verfehlte die Startgrenze und gilt wegen dieser
abweichenden Messbedingungen nicht als Abnahme. Der aktuelle Messlauf scheiterte
noch an der ursprünglichen Startup-Assertion; nur diese Abweichung wurde danach
ausdrücklich akzeptiert. Alle übrigen Leistungsassertionen waren erfolgreich.
Desktop (1440×900), Mobil (390×844) und Tablet (1024×768) wurden visuell geprüft.
Die Messung belegt weder externe Providerlatenz noch Leistung auf einem echten iPad.
Rohmessung: privates Verzeichnis `benchmark-stock-isolated-final` außerhalb
des Repositorys.

## Einführung und Betriebsgrenze

Die explizite Offline-Übernahme einer isolierten 1.1.0-Kopie nach 1.2.0 hat 42 zum
Stichtag gültige Altangebote mit denselben IDs/Konditionen übernommen und nur den
Ablauf auf null gesetzt. 165 historische Transporte und alle übrigen Tabellen
wurden vollständig abgeglichen. Quelle und Backup bleiben unverändert; Altangebote
wurden nicht nachträglich gemeinsamen Vorlagen zugeordnet.

**Der aktive Spielstand wurde nicht auf 1.2.0 umgestellt.** Vor dem nächsten Start
mit diesem Code ist die dokumentierte Übernahme mit gestoppten Schreibern und
frischem Backup erforderlich. Eine alte Testkopie darf aktuelle Fortschritte nicht
ersetzen. Die bereits gesondert freigegebene Bina-Reparatur bleibt ein früherer
Betriebsschritt. Anleitung: [RUNTIME_OPERATIONS](docs/RUNTIME_OPERATIONS.md).
Spielstände, Archive, Sitzungen, Screenshots und Rohlogs bleiben außerhalb von Git.
Echte iPad-Abnahme und Integration nach `main` bleiben gesondert.

---

# Qualitätsbericht: Runtime, Vorbereitung und Alttransporte

Stand: 27.09.2026. Branch `feature/frontend-v2`, Basis `d11034f`.
Die frühere Beschränkung auf gezielte Tests wurde durch die ausdrückliche
Beauftragung der vollständigen Abnahme ersetzt. Die folgenden historischen
Berichte beschreiben jeweils ihren damaligen Stand.

## Änderung und Verantwortlichkeiten

Der Standardeinstieg betreibt API und Vorbereitung in getrennten überwachten
Prozessen. Persistierter Bedarf, globale Worker-Lease und Publikationsprüfungen
schützen Markt, Flotte und Routingnachweise vor konkurrierenden Änderungen.
SQLite verwendet WAL, FULL-Synchronisierung und 500 ms Lock-Wartezeit.
Die bestehende Prüfung beider Fahrtrichtungen bleibt verbindlich.

Der gemeldete stille Windows-Start wurde mit nativen Konsolenhandles
reproduziert: `CREATE_NO_WINDOW` verursachte `Bad file descriptor` bei der
Kindprozessausgabe. Beide Rollen erben jetzt die vorhandene Konsole; ein
`process.start`-Event und die API-Startmeldungen bleiben sichtbar. Auf einer
frischen Kopie des Spielstands erschien die Serverbereitschaft nach etwa zwei
Sekunden; Health und Login antworteten mit HTTP 200, Ctrl+C beendete die API
geordnet. Absolute Kindprozesspfade und die automatische Auswahl einer
vorhandenen Projekt-`.venv` sichern weitere Startvarianten ab.

Kompakte Runtime- und Verkehrsantworten enthalten keine Routenarrays.
Authentifizierte Geometrieabrufe, ETag/Gzip und ein accountgebundener Cache
entkoppeln das Spiel von der Karte. Eigene Transporte stammen aus dem aktuellen
Runtime-Snapshot; verspäteter öffentlicher Verkehr kann abgeschlossene Fahrten
nicht erneut darstellen. Fehlende Geometrie erzeugt keine Fahrzeugbewegung.

Das Offline-Werkzeug repariert ausschließlich das bestätigte Alttransportmuster
in einer neuen Datenbank nach Backup, Archivprüfung und vollständigem Abgleich.
Auf der isolierten Kopie wurden genau ein aktiver und ein abgeschlossener Fall
repariert. Beim betroffenen Profil schloss normales Settlement 17 fällige
Fahrten genau einmal ab. Nach ausdrücklicher Freigabe wurde anschließend der
Live-Stand bei gestoppten Prozessen frisch gesichert und repariert: inzwischen
174 Transporte, weiterhin genau ein aktiver und ein abgeschlossener Schadensfall.
Alle anderen Werte wurden vollständig abgeglichen. Die geprüfte Ausgabe wurde
als `data/game.db` aktiviert; Original samt Sidecars, SQLite-Backup,
Prüfsummenarchiv und Aktivierungsnachweis bleiben privat unter `data/`.
Der Hintergrund-Neustart wurde von der automatischen Ausführungsprüfung
blockiert; der Nutzer startete regulär über `python main.py`. Danach antwortete
Health mit HTTP 200. Binas 17 fällige Transporte wurden normal abgeschlossen;
alle Fahrzeuge blieben erhalten. Zwei anschließende neue Dispatches belegen
den wieder spielbaren Bestand. Der Kontostand wurde im konsistenten Read genau
gegen die 17 Auszahlungen und die Kosten der neuen Dispatches abgeglichen.

Manuelles Review gegen AGENTS und CODING_STANDARDS:
[Verantwortlichkeiten und Nachweise](docs/RUNTIME_ISOLATION_REVIEW.md),
[Architekturentscheidung](docs/adr/0007-runtime-preparation-and-route-projections.md),
[Betrieb und Live-Aktivierung](docs/RUNTIME_OPERATIONS.md).

## Vollständige Prüfungen

Vorlauf nach der Kaltstartoptimierung, vor der Windows-Startkorrektur:
`python scripts/quality.py` vollständig bestanden: 560 Python-Tests,
100,00 % app-Statement-Coverage (6.585 Statements, keine fehlenden Statements),
113 Frontend-Verhaltenstests. Ruff, Formatierung, mypy (151 Dateien), Pyright,
ESLint, Stylelint, Prettier, checkJs, Produktionsbuild und compileall bestanden.
Architektur- und Function-Manifest-Prüfungen sind Teil der Python-Suite.
Zwei bestehende Deprecation-Warnungen stammen aus Starlette/httpx/AnyIO;
sie sind keine Testfehler und wurden nicht unterdrückt.

`npm run test:e2e` auf dem endgültigen Produktionsbuild: 31/31 bestanden
(9,8 Minuten). Desktop, Mobil- und Tabletansichten sowie verspätete Antworten,
Netzwerk-/Speicherfehler, Sessionwechsel, Anfahrt, Dispatch und Ankunft geprüft.
Nach der Windows-Startkorrektur werden die vollständigen Gates erneut geprüft.

## Leistungsabnahme

Messung auf neuen privaten Kopien mit drei Profilen und 35 Fahrzeugen;
Intel Core i5-1235U, 12 logische CPUs, etwa 8 GiB RAM, Windows 11,
Python 3.11.9. API und Fixture-Worker laufen als getrennte Prozesse.
Der Messbefehl und die vollständigen Bedingungen stehen im Reviewbericht.

Ein erster Lauf parallel zu beiden Gesamtsuiten erreichte bei jeweils 300
Reads p95 von 186 ms (Runtime), 158 ms (Verkehr), 137 ms (Markt) und 24 ms
(Health). Runtime plus Verkehr: höchstens 147.901 Byte JSON; keine wiederholten
Geometriedownloads und keine Browserfehler. Der Browserstart verfehlte unter
dieser zusätzlichen Last mit 2,84 Sekunden das Zwei-Sekunden-Ziel.
Die anschließende kalte Dreiprofilprobe identifizierte beim betroffenen Profil
3,16 Sekunden mit 17 fälligen Ankünften. Wiederverwendung der exakt unveränderten,
bereits validierten Transportzeilen und ein früherer Runtime-Abruf beheben diesen
Engpass; keine Validierung, Settlementprüfung oder Geometrie wurde ausgelassen.

Der abschließende Lauf ohne parallele Tests besteht sämtliche Zielwerte:

| Prüfung | Ergebnis |
| --- | --- |
| Erste sichtbare Flotte, drei kalte Browserkontexte | 1.731 / 934 / 1.321 ms |
| Runtime, 300 Reads | p95 84,95 ms |
| Öffentlicher Verkehr, 300 Reads | p95 68,63 ms |
| Markt, 300 Reads | p95 91,67 ms |
| Health, 300 Reads während Vorbereitung | p95 10,84 ms |
| Runtime plus Verkehr, unkomprimiertes JSON | maximal 110.169 Byte (unter 108 KiB) |
| Unveränderte Geometrie erneut geladen | 0 bei zwei Pollingintervallen je Profil |
| Browserfehler / veränderte Quelldatenbank | 0 / nein |

Die Browserproben erfolgen vor den HTTP-Messreihen, einschließlich fälligem
Settlement. Desktop-, Mobil- und Tablet-Screenshots wurden visuell geprüft;
Flotte, Bedienelemente und korrekte historische Routen bleiben darstellbar.
Provider und Basiskarten verwenden deterministische lokale Fixtures; die
Messung behauptet keine externe Netzlatenz oder reale iPad-Leistung.

Echte iPad-Geräteabnahme und Live-Aktivierung sind gesonderte Betriebsschritte.
Desktop-, Mobil- und Tabletansichten werden im lokalen Browser geprüft.
Spielstände, Archive, Sitzungen, Screenshots und Rohmessungen bleiben außerhalb
von Git. Integration nach `main` erfolgt ausschließlich über das Reviewverfahren.

---

# Historischer Qualitätsbericht: befahrbare Standortverbindungen

Stand: 27.09.2026. **Implementiert; gezielte Prüfungen bestanden; vollständige
Suite und Gesamtintegration verbleiben beim Nutzer.** Basis `5d7ff77`,
bestehender Branch `feature/frontend-v2` entsprechend Nutzeranweisung.
Kein Commit, Push, Merge oder Serverneustart für diesen Fix.

## Ergebnis

Jede Anfahrt und Lieferung benötigt bestätigte Truck-Routen in beiden
Richtungen. Alle vier Endpunkte müssen innerhalb 10 Metern der vorgesehenen
Anker liegen. Maximal fünf Kandidaten je Standort innerhalb 1.000 Metern,
25 Paare und 120 Sekunden. Anker und beide Routen werden atomar gespeichert;
Lease-Verlust oder überholte Eingaben verhindern Veröffentlichung.
`truck-connected-v2` ersetzt alte positive und negative Nachweise. Erfolge
gelten höchstens 24 Stunden, definitive Fehler eine Stunde, temporäre Fehler
60 Sekunden. Aktuelle zertifizierte Anker bleiben für unerreichbare Ziele stabil.

## Tatsächlich ausgeführte gezielte Prüfungen

- 99 Tests in 13 gezielt ausgewählten Routing-, Repository-, Markt-,
  Fahrzeugmarkt-, Anfahrt-, Dispatch-, Architektur- und Manifest-Testdateien:
  bestanden. Zusätzlich zwei Konfigurationstests bestanden.
- 100 % Statement-Coverage (597/597) für die acht ausgewiesenen Module:
  Domain-Routing-Anker und -Verbindungen, Locate-Provider, Readiness-Repository,
  Routing-Anker-, Verbindungs-, Readiness- und Dispatch-Planungsservice.
- Ruff und Formatcheck: 22 geänderte Pythondateien bestanden.
- mypy: 13 geänderte Core-Dateien bestanden. Pyright: geänderte Pythondateien,
  0 Fehler und 0 Warnungen. `git diff --check`: bestanden.
- Manuelles Zuständigkeitsreview gegen `AGENTS.md` und `CODING_STANDARDS.md`:
  Provider, Kandidatensuche, Verbindungsprüfung, Readiness und SQL-Publikation
  getrennt; keine Provider-Awaits in Schreibtransaktionen.

Lokale Prüfprotokolle: `artifacts/routing-coverage-tests.txt`,
`artifacts/routing-coverage.txt`, `artifacts/routing-pyright.txt`,
`artifacts/routing-config-tests.txt`. Diese generierten Dateien gehören nicht
ins Git. Tests wurden nicht abgeschwächt; gerichtete Router-Aufrufzahlen wurden
an die verpflichtende Rückwegprüfung angepasst.

## Isolierte Wolfsburger Abnahme

SQLite-Backup vor der Prüfung: `data/backups/game-before-routing-fix-20260927-170052.db`.
Kopie: `artifacts/wolfsburg-acceptance.db`. Der vorhandene LKW von AlexIPad wird
über den realen rund 504 Meter entfernten Anker wieder disponierbar.
Regulärer Marktauftrag nach Schnellecke Wolfsburg: Dispatch, Ankunft und
anschließender regulärer Rückauftrag zum Volkswagenwerk erfolgreich.
Voriger Endpunkt und neuer Start: 0 Meter Abstand. Acht initiale und zwei
abschließende Provideranfragen; Dispatch selbst benötigt keine weiteren HTTPs.
Bei reiner Routingvorbereitung blieben Hashes von Benutzer-, Spieler-,
Fahrzeug- und Transporttabellen der Kopie unverändert. Der Fix hat den echten
Spielstand nicht mutiert; Simulation und Auftragsstarts liefen auf der Kopie.

Ein separater Altbestandfehler ist dokumentiert: Einer von 58 AlexIPad-
Transport-Snapshots im ursprünglichen Backup verletzt bereits die bestehende
Anfahrtsvalidierung. Die Historie wurde nicht umgeschrieben.

## Abnahmegrenze

Keine vollständige Suite, kein vollständiges Quality-Gate und keine neue
Browser-Gesamtabnahme für diesen Fix ausgeführt. Frühere Gesamtprüfungen sind
keine Abnahme dieses Stands. Die vollständige Prüfung und Integration bleiben
wie beauftragt beim Nutzer. Vor späterer Aktivierung nach weiterem Spielbetrieb
ist ein frisches SQLite-Backup zu erstellen.

Details, Wiederprüfungen und Zuständigkeitsreview:
[Änderungs- und Abnahmebericht](docs/CONNECTED_ROUTING_REVIEW.md).

---

# Qualitätsbericht: Reviewkorrekturen und Vehicle-Ready-Markt

Stand: 27.09.2026. **Implemented / targeted tests passed / full acceptance pending.**
Basis: `e49e5fa7e29e64ac3a10c0e7a365ede88ad37c68`, lokal und auf
`origin/feature/frontend-v2` vor Abschluss erneut identisch geprüft.
Direkte Umsetzung auf dem vom Nutzer ausdrücklich vorgegebenen bestehenden
Arbeitsbranch als Ausnahme vom normalen Branchingprozess. Kein ZIP, Push, PR,
Merge, Branchwechsel, Reset oder Rebase. Hooks: `.githooks`.

Lokale Umsetzungscommits mit aktiven Hooks:
`58ca257` (Backend und Python-Regressionen),
`4740c87` (Frontend und Browser-/Node-Regressionen).
Dokumentation folgt im separaten lokalen Abschlusscommit. Kein Push.

## Ergebnis und geschützte Verträge

Alle zehn Reviewpunkte wurden korrigiert: fachlicher Generation-Fingerprint
auch für negative/stale Relationen; vollständiger Worker-Fehlerschutz;
separater injizierter Batch-Service; atomarer eigenständiger Bind;
Cache-Schlüssel nur im Repository; typisierte Analytics samt API-Projektion;
injizierter EconomyAuditService mit Composition Root; aggregierender Cleanup;
öffentliche JSDoc-Verträge; `synchronizeMapSelection` statt `selectTransport`.

Der Fahrzeugmarkt zeigt nur Offers mit dem ausgewählten eigenen idle Fahrzeug
in `eligible_vehicle_ids`. Ohne gültige Auswahl erscheint „Fahrzeug wählen“.
Der gemeinsame Spielerpool bleibt erhalten. Stadt-Coverage wird um teilbare
Coverage je Fahrzeug ergänzt, einschließlich individueller ready Approaches.
Kleine Fahrzeuge erhalten passende Generierungskontexte. Fehlende Coverage wird
diagnostiziert, nicht durch ungeeignete Offers aufgefüllt. Approach-Priorität
verhindert Starvation durch wechselnde Delivery-Auswahlen in begrenzten Batches.
Liste und Kartenmarker verwenden denselben Fahrzeugkontext.

Game-Schema 1.1.0, historische Snapshots, globale Routing-/Lease-Infrastruktur,
Economy, Tarife, Tonnagenverteilung und A → B → C bleiben fachlich unverändert.
Keine Referenz- oder Spieler-Datenbanken geändert. Keine realen Provider-Bulk-
Aufrufe. `static/dist` ist ausschließlich lokaler generierter Build-Output.

## Tatsächlich ausgeführte gezielte Prüfungen

- 108 Tests in den folgenden expliziten Dateien bestanden:
  `test_review_regressions.py`, `test_market_preparation.py`,
  `test_vehicle_market.py`, `test_market_lifecycle.py`, `test_market.py`,
  `test_api.py`, `test_analytics.py`, `test_economy_v2.py`,
  `test_routing_readiness_store.py`, `test_function_contract.py`,
  `test_architecture.py`.
- Im ersten Coverage-Lauf fehlte die Koordinatenvalidierung eines RoutingAttempt.
  Der zusätzliche Valid-/Invalid-Koordinatentest schließt diese Lücke;
  `test_routing_readiness_store.py`: 4 Tests bestanden.
- Nach expliziter SQL-Skalarvalidierung erneut
  `test_analytics.py test_function_contract.py`: 21 Tests bestanden.
- Kumulierte gezielte Statement-Coverage: **574/574 Statements, 100 %** in den
  elf separat gemessenen Modulen (unten). Keine Senkung des Grenzwerts.
  Dies ist ausdrücklich kein Nachweis der gesamten Core-Coverage.
- Ruff check/format: 32 betroffene Python-Dateien bestanden; mypy: 25 betroffene
  Source-Dateien bestanden; Pyright derselben betroffenen Dateien: 0 Fehler,
  0 Warnungen. Audit-CLI ist bereits in allen expliziten Quality-Dateilisten
  enthalten; deren Einträge wurden beibehalten.
- Node: `node --test frontend/frontend-v2.test.mjs frontend/behavior.test.mjs
  frontend/lifecycle.test.mjs frontend/journey.test.mjs`: **52 bestanden**.
- ESLint und Prettier für geänderte Frontend-Dateien sowie checkJs bestanden.
  Keine CSS-Änderung; kein erneuter vollständiger Stylelint-Lauf.
- Vite-Build vollständig vor dem Browserlauf abgeschlossen.
- `npm run test:e2e -- tests/browser/game.spec.js --grep
  "vehicle market shows only eligible|DB vehicle selection changes|city offers survive pan"`:
  **3 bestanden**. Gemockte Provider. Keine parallelen Builds während Playwright.
- `git diff --check`: bestanden nach Entfernung von JSDoc-Leerraum.

Reproduzierbarer gezielter Python-Aufruf (aus dem Repository):

```powershell
.venv/Scripts/python.exe -X utf8 -u -m pytest tests/test_review_regressions.py tests/test_market_preparation.py tests/test_vehicle_market.py tests/test_market_lifecycle.py tests/test_market.py tests/test_api.py tests/test_analytics.py tests/test_economy_v2.py tests/test_routing_readiness_store.py tests/test_function_contract.py tests/test_architecture.py --cov=app.services.preparation_batch --cov=app.services.vehicle_coverage --cov=app.services.market_preparation --cov=app.services.preparation_worker --cov=app.services.economy_audit --cov=app.services.analytics --cov=app.api.v1.analytics_projection --cov=app.repositories.analytics --cov=app.domain.market_preparation --cov=app.domain.routing_readiness --cov=app.repositories.routing_readiness --cov-report=term-missing --cov-fail-under=100
```

Die beiden Nachläufe verwendeten dieselbe Modulauswahl mit `--cov-append`.
Lokale Logs: `artifacts/review-targeted-python-final.log`,
`review-targeted-coverage-final.log`, `review-targeted-analytics-final.log`,
`review-targeted-frontend-final.log`, `review-targeted-playwright-final.log`.
Artefakte bleiben unversioniert. Zwei bestehende Starlette/HTTPX-/AnyIO-
Deprecation-Warnungen wurden beobachtet; keine Testfehler daraus.

## Wirtschaftsaudit und sichtbarer Befund

Der vollständige lokale Economy-Audit wurde vor/nach dem Refactoring verglichen:
Seed 20260925, 14 Modelle, 163296 Zeilen, 2457 inkompatible Kombinationen,
kleinste Referenzmarge 0,45748730964467005, 16298 negative Cashflow-Szenarien,
davon 4878 typische Beladungen. Negative Ergebnisse bleiben zulässig.
Matrix und Summary sind byteidentisch. Matrix-SHA256:
`30213F9AC3D459E48BC4F525D9A5B3E646C7DC5F60ADC9DBABEA27B4BAFCA344`.
Summary-SHA256:
`9A88DABFFAFE1F644E4D95AC05A4A54CC8B505DFB8EEE81A98FD52DF7655F397`.
Aufruf: `.venv/Scripts/python.exe -X utf8 scripts/audit_economy.py --output artifacts/review-economy-after`.

Der tatsächlich angesehene Desktop-Screenshot
`%TEMP%/world-freight-vehicle-ready-market.png` zeigt das zweite Fahrzeug,
zwei geeignete Angebote, `partial`-Hinweis und nach Korrektur ebenfalls zwei
Aufträge am Kartenmarker. Die erste Sichtprüfung fand dort noch vier Pool-
Angebote; die Map-Projektion wurde daraufhin korrigiert und erneut geprüft.
Kein neuer vollständiger Mobil-/Reduced-Motion-/Renderer-Abnahmelauf.

## Einzelreview und offene Gesamtabnahme

[REVIEW_VEHICLE_READY.md](docs/REVIEW_VEHICLE_READY.md) inventarisiert jede neue
oder geänderte Python-Funktion sowie die Frontend-Methodenverträge mit Zweck,
Schicht, Abhängigkeiten und Seiteneffekten. Keine verdeckte zweite Runtime-DB,
keine HTTP-Aufrufe im Candidate-Service, keine Preise oder Eignungsheuristiken
in Views. Die Coverage- und Batch-Schichten materialisieren keine Offers.

**Full quality suite:**
NOT RUN – explicitly reserved for user

**Full Playwright suite:**
NOT RUN – explicitly reserved for user

Dieser Stand ist nicht als integration-ready oder vollständig abgenommen
bezeichnet. Die vollständige Core-Coverage, gesamte Browserregression und echte
Provider-/Wolfsburg-Betriebsprüfung bleiben offen. Die Gesamtabnahme führt der
Nutzer anschließend nacheinander aus:

```powershell
.venv/Scripts/python.exe -X utf8 scripts/quality.py
npm run test:e2e
git diff --check
```

---

## Historischer Bericht: vorheriger Routing-Readiness-Stand

Die folgenden Ergebnisse gehören zur früheren Implementierung und sind keine
Gesamtabnahme des oben beschriebenen Korrekturstands.

# Qualitätsbericht: Global Routing Readiness

Stand: 27.09.2026. **Implementiert und lokal vollständig geprüft.**
Die lokale Gesamtabnahme ist bestanden. Der Branch-Push ist nachträglich
ausdrücklich freigegeben; PR und Merge bleiben ausgeschlossen. Die weiter
unten stehenden älteren Prüfergebnisse gelten nur für ihren damaligen Stand.

- Current branch head used: `feature/frontend-v2`.
- Base commit: `df40e7c800d21ac4187912fc9a81a6e08e1349bb`.
- Lokaler und Remote-HEAD für den Ausgangsstand erneut identisch geprüft.
- Bewusste nutzerautorisierte Ausnahme vom normalen Branchingprozess: bestehender
  Featurebranch verwendet. Kein Wechsel, Rebase oder Reset. Abschlussform:
  Commit und ausdrücklich freigegebener Branch-Push nach erfolgreicher
  Gesamtabnahme; kein PR oder Merge.
- Hooks bleiben `.githooks`. Referenzkataloge, Spielerbestände und historische
  Snapshots werden nicht verändert oder versioniert.

Changed files: 72 Source-, Test- und Dokumentationsdateien im lokalen Commit;
die folgenden Abschnitte ordnen die Änderungen fachlich zu. Das zuvor erzeugte
ZIP-Archiv und seine Prüfsummendatei wurden entfernt; es gibt kein Drop-in-Paket.

## Geänderte Bereiche und Ergebnis

### A. Routing diagnostics

Globale gerichtete Relationen besitzen ready/deterministic_failure/
transient_failure/stale-Projektionen. RoutingAttempt ist append-only und enthält
Methode, Kandidat, Providerdiagnostik, Zeit und Trace. Verworfene Zwischenversuche
bleiben nachvollziehbar. Verlorene Leases verhindern Publikation.

### B. Anchor repair

Facility → Adresse → höchstens fünf eindeutige reale Locate-Zugänge; finale
Truckvalidierung und Snapgrenze bleiben verbindlich. Globale Anchor-Leases
verhindern parallele Reparaturen desselben Endpunkts. Adress-/Koordinatenänderung
invalidiert den Source-Fingerprint. Providerunverfügbarkeit verschiebt Retries.

### C. OSM fallback

Nur tatsächliche Truck-kompatible korrelierte Locate-Metadaten werden als
Kandidaten verwendet. Keine erfundenen Zugänge, keine Luftlinienroute und kein
Verschieben zur Umgehung von no_path oder distance_limit. Unklarer Endpoint wird
höchstens einmal an beiden Enden erneut validiert.

### D. Routing relation repository

Zusätzliche Infrastruktur-Tabellen in derselben SqliteGameDatabase; Geometry
bleibt im route_cache. Separate OfferRouteReferences mit FK-Cascade. Game-Schema
1.1.0, Offer-Dokumentversion 1 und Transport-Dokumentversion 2 unverändert.
Referenz und Offer werden innerhalb derselben Markt-UoW gespeichert/entfernt.

### E. Route readiness

Aktuelle Fingerprints umfassen Provideridentität, tatsächlich beobachtete
Revision und Facility-/Anchorfakten. Beschädigte/fehlende Payloads sind nicht
ready. Globale Relations-Leases besitzen Ablauf, Erneuerung und Eigentümerfence.
Concurrent Player-Nachfrage teilt dieselbe globale Evidenz. Marktpublikation
enthält ausschließlich Delivery-ready Offers; eligible_vehicle_ids verlangt
zusätzlich vorbereitete Anfahrten. Auch ausschließlich veraltete Approaches
lösen neue Preparation aus. Partial bedeutet fehlende Coverage.

### F. Prewarm / audit

CLI `scripts/audit_routing_readiness.py`: lokales --report, explizites --prewarm,
Defaultbudget 100 tatsächliche Providerrequests einschließlich Locate/Geocoding,
Resume über persistierte Evidenz und gesonderte Freigabe des öffentlichen
Default-Endpunkts. Kein Live-Prewarm ausgeführt.

Tatsächlich ausgeführter lokaler Wolfsburg-Lauf mit temporärer isolierter
Audit-Datenbank und unverändertem Referenzkatalog:
`python scripts/audit_routing_readiness.py --report --city Wolfsburg`.
Ergebnis: 559 Katalogfacilities mit Koordinaten, 602 relevante gerichtete
Relationen für diesen Fokus, 602 unchecked, **0 Providerrequests**. Es gibt in
dieser frischen Audit-Datenbank keine Versuchshistorie. Daraus folgt ausdrücklich
keine Aussage, dass alle Facilities truckfähig oder alle Relationen routbar sind.
Die CLI kann dieselben Berichte mit vorhandener persistierter Evidenz erzeugen;
Wolfsburg erhält keine Sonderregel.

### G. Market integration

Candidate-Erzeugung bleibt routerfrei. Preparation ist ein eigener Baustein vor
Coverage/Materialisierung. Startup validiert Kataloge und ersetzt offene Märkte
aller Profile atomar aus bestehender Readiness; kein Provider-Bulk beim Start.
Lifespan besitzt Worker, Tasks und Cleanup. Fairer persistierter Spielerbedarf,
begrenzte Batches und neue Execution-Traces; HTTP-Requestkontext wird nicht geerbt.
Fehlgeschlagene Kandidaten werden übersprungen, erschöpfter Pool separat gemeldet.

### H. Dispatch / Journey

Produktions-Quote lädt vorbereitete Delivery-/Approach-Payloads. Kein ungeprüfter
Providerfallback. Revalidierung vor Commit, A → B → C, Fahrzeuggeschwindigkeit,
Energie, Kosten, Tarife, historische Konditionen und separater Refill bleiben
bestehen. Globale Providerzeit ist keine finale Spielerfahrzeit.

### I. Frontend

Preparationstatus wird gemeinsam mit Offers projiziert. Bestehende Controller
besitzen Polling, Abort und stale-response-Schutz; Views zeigen verständliche
partial/exhausted-Zustände. Browserfixtures verwenden serverseitige Eignung und
explizite Fahrzeugwahl; Fahrzeugwechsel wählt ein für beide geeignetes Angebot.
Keine obsolete globale Stadtauswahl ergänzt.

### J. Documentation

PRODUCT (MVP, Truck-Anker, Markt, Quote/Dispatch), ARCHITECTURE, DOMAIN_MODEL,
API, API_PROVIDERS, DATA_SOURCES, RELATIONAL_STATE, OBSERVABILITY, TESTING,
TARGET und MILESTONES abgeglichen. Neue Einzelreviewliste:
[ROUTING_READINESS_REVIEW.md](docs/ROUTING_READINESS_REVIEW.md).
117 neue/geänderte Core-Callables einschließlich abstrakter Ports einzeln
abgeglichen; Frontendfunktionen separat geprüft. Der neue Audit-Einstiegspunkt
ist zusätzlich in den Ruff-/Format-/mypy-Dateilisten des Quality-Gates enthalten.

## Direkter Branchabschluss: vollständige Gates

Der erste vollständige Lauf ergab 482 bestandene und 11 fehlgeschlagene Tests.
Die Fehler betrafen die neue Preparationstatus-API, unzulässige RouteReference-
Felder in historischen Projektionen sowie bisher sofort erzeugte Testangebote.
Korrigiert wurden die Projektionsgrenze und die betroffenen Testaufbauten;
keine bestehenden Vertragsprüfungen wurden abgeschwächt.

76 gezielte Nachprüfungen in test_api, test_game_import, test_nested_import,
test_multiplayer, test_multiplayer_map, test_vehicle_catalogue und
test_market_preparation bestanden. Ergänzte Gegenchecks prüfen insbesondere
veraltete Delivery-/Approach-Routen und fehlende Referenzen. Die kombinierte
Coverage dieser Diagnosephase beträgt 5413/5413 Statements; der abschließende
vollständige Quality-Lauf prüft dies erneut ohne Coverage-Append.

Der erste vollständige Playwright-Lauf bestand 29/30 Fälle. Der letzte
Registrierungsversuch wurde durch das unveränderte IP-Limit blockiert, weil
alle Testfälle denselben lokalen Client teilten. Der Testaufbau isoliert nun
Auth-Clientadressen pro Fall hinter dem lokalen Testproxy. Der betreffende
Weltkarten-/Stadtmarktfall bestand danach einzeln (1 Test, 11,9 s).
Produktionslimit und API-Throttle-Tests wurden nicht geändert.
Nach dieser Korrektur wurden Quality und E2E erneut vollständig ausgeführt.

| Abschließender Befehl | Tatsächliches Ergebnis |
| --- | --- |
| `.venv/Scripts/python.exe -X utf8 scripts/quality.py` | bestanden; 495 Python-Tests, 5413/5413 Statements = 100 %, 101 Frontendtests; Ruff/Format/mypy/Pyright/ESLint/Stylelint/Prettier/checkJs/Build/compileall bestanden |
| `npm run test:e2e` | 30/30 bestanden, 8,9 Minuten; Build davor vollständig abgeschlossen |
| `git diff --check` | bestanden; keine Whitespacefehler |

Der abschließende Python-Lauf dauerte 601,94 Sekunden. Zwei vorhandene
TestClient-/anyio-DeprecationWarnings sind protokolliert; keine Testfehler.
Lokale Logs: `artifacts/routing-full-quality-accepted.log`,
`artifacts/routing-full-e2e-accepted.log`, `artifacts/routing-diff-check.log`.
Diese bleiben unversioniert. Frühere Diagnose- und Fehlversuche werden durch
diese vollständigen, sauberen Abschlussläufe nicht als erfolgreich umgedeutet.

## Tatsächlich ausgeführte gezielte Prüfungen

Kein Testumfang oder Coverage-Schwellwert wurde abgeschwächt. Zwischenläufe
zeigten fehlende Gegenproben, alte Workerfixtures, einen Importformatfehler und
Browserannahmen zur asynchronen Eignung. Diese wurden korrigiert; nachfolgend
stehen die abschließenden Ergebnisse, nicht die Fehlversuche als Abnahme.

### Einheiten 1–5: Domain, Repository, Provider, Readiness, Worker und Markt

```text
.venv/Scripts/python.exe -m pytest
  tests/test_market_preparation.py
  tests/test_routing_readiness_store.py
  tests/test_request_limiter.py
  tests/test_routing_audit.py
  tests/test_routing_audit_cli.py
  tests/test_anchor_repair_history.py
  tests/test_routing_anchors.py
  tests/test_routing_anchor_provider.py
  tests/test_routing_anchor_repository.py
  tests/test_function_contract.py -q
  --cov=app.domain.routing_readiness
  --cov=app.domain.market_preparation
  --cov=app.domain.readiness_ports
  --cov=app.providers.request_limiter
  --cov=app.providers.valhalla_metadata
  --cov=app.repositories.routing_readiness
  --cov=app.repositories.market_preparation
  --cov=app.repositories.routing_audit
  --cov=app.repositories.routing_anchors
  --cov=app.services.routing_inventory
  --cov=app.services.routing_readiness
  --cov=app.services.market_preparation
  --cov=app.services.preparation_worker
  --cov=app.services.routing_anchors
  --cov=app.providers.routing_anchor
  --cov-report=term-missing --cov-fail-under=100
```

Ergebnis: **56 Tests bestanden; 755/755 Statements (100 %)**. Dies ist die Coverage der ausdrücklich
benannten 15 Routingmodule, keine behauptete vollständige Core-Coverage.
Die Manifestprüfung wurde im selben Lauf ausgeführt.

### Einheiten 5–6: bestehende Markt-/Dispatch-/Economyverträge

```text
.venv/Scripts/python.exe -m pytest
  tests/test_routing.py tests/test_routing_api.py tests/test_geocoding.py
  tests/test_routing_anchor_provider.py tests/test_routing_anchor_repository.py
  tests/test_dispatch_routing_anchors.py tests/test_dispatch_approach.py
  tests/test_market.py tests/test_market_lifecycle.py tests/test_economy_v2.py
  tests/test_initialization_lifecycle.py tests/test_architecture.py
  tests/test_function_contract.py tests/test_routing_audit_cli.py -q --no-cov
```

Ergebnis: **117 Tests bestanden**. Startup-/Shutdown-Fehler,
Dispatch-Rollback/Refill, historische Verträge und bestehende Wirtschaftsformeln
sind in den betroffenen Dateien enthalten. Kein neuer Wirtschaftsaudit mit
Balanceänderungen, da diese nicht zum Routing-Umbau gehören.

### Gezielte statische Prüfungen

- `python -m ruff check <46 geänderte Python-Dateien>`: bestanden.
- `python -m ruff format --check <dieselben Dateien>`: 46 formatiert.
- `python -m mypy <34 geänderte Core-/CLI-Dateien>`: keine Fehler.
- `node node_modules/pyright/index.js <46 geänderte Python-Dateien>`:
  0 Fehler, 0 Warnungen.
- Nach der Approach-Generation-Korrektur: Ruff und mypy auf dem betroffenen
  Service, Pyright auf Service/Testdatei erneut bestanden.
- Gezielte ESLint-/Prettier-Prüfung der geänderten Frontenddateien und
  `npm run typecheck`: bestanden.

### Einheit 7: Frontend und ausgewählte Browserfälle

```text
node --test --test-name-pattern
  'partial and exhausted|list and detail reads|offer filters'
  frontend/frontend-v2.test.mjs
npm run build
npx playwright test tests/browser/game.spec.js --grep
  'desktop: registration, map, quote|DB vehicle selection changes costs|company livery persists across map'
```

Ergebnis: **3 Node-Tests**, Vite-Build und **4 benannte Playwright-Fälle**
bestanden. Nach dem finalen Frontend-Build zusätzlich:

```text
npx playwright test tests/browser/game.spec.js --grep
  'company livery persists across map'
```

**2 Desktop-/Mobilfälle bestanden (31,2 s)**. Build und Browserläufe liefen
nacheinander. Die abschließende Approach-Generation-Korrektur ist separat durch
Backendregressionen geprüft; die Browserfälle wurden danach nicht wiederholt.

### Tatsächlich betrachtete Screenshots

- `world-freight-livery-desktop.png`: zehn beschriftete Farbswatches, Auswahl
  sichtbar, übereinstimmende Front-/Seiten-/Top-Down-Lackierung, lesbare Panels.
- `world-freight-livery-mobile.png`: Palette umgebrochen und bedienbar,
  Front-/Seitenvorschau konsistent. Untere Top-Down-Vorschau außerhalb dieses
  Ausschnitts; dafür kein weitergehender visueller Nachweis behauptet.
- `world-freight-dispatch.png`: explizite Fahrzeugwahl, Startaktion aktiv,
  400 km Anfahrt + 400 km Lieferung = 800 km. Das ist eine Mockroute.

Im vollständigen Browserlauf zusätzlich tatsächlich geöffnet und angesehen:
`artifacts/assets-current/fleet-desktop.png`, `shop-mobile.png` sowie die
Temp-Screenshots `world-freight-energy-mobile.png`,
`world-freight-approach-desktop.png`, `world-freight-costs-purchases-mobile.png`
und `world-freight-vehicle-city-market.png`. Befunde: konsistente Assets und
Lackierung, lesbare mobile Panels, sichtbare Ladephase, tatsächlicher Start vor
Abholung, nachvollziehbare Kostenkomponenten (80 + 62 + 243 = 385 Euro),
fahrzeugbezogener Stadtmarkt mit sichtbarer Ungeeignet-Kennzeichnung.

Die Bilder wurden geöffnet und angesehen. Grid-Tiles und gerade Mockgeometrie
belegen UI-Verhalten, keine reale Provider-/Wolfsburg-Routbarkeit. Screenshots,
Logs und isolierte Audit-Datenbanken sind unversionierte Prüfartefakte.

## Lokale Gesamtabnahme und verbleibende Betriebsprüfungen

**Full quality suite:**
PASSED – vollständig ausgeführt

**Full Playwright suite:**
PASSED – vollständig ausgeführt

`git diff --check` wurde nach den vollständigen Gates ausgeführt und bestanden.
Der lokale Stand ist vollständig geprüft; reale Providerprüfungen bleiben
als getrennte Betriebsprüfung offen.

Known limitations:

- Reale Valhalla-/Nominatim-Antworten wurden automatisiert gemockt. Es wurde kein
  globaler öffentlicher Prewarm und keine tatsächliche Wolfsburg-Routenprüfung
  ausgeführt.
- Graphwechsel werden nur anhand tatsächlich gelieferter bekannter Header
  erkannt. Ohne Providerrevision gibt es keine erfundene Invalidierung; ein
  unangekündigter Graphwechsel ist dann nicht automatisch sichtbar.
- Provider-Limiter gelten pro Runtimeinstanz. Mehrere OS-Prozesse benötigen
  gemeinsame externe Drosselung oder eigenen Dienst. Globale SQLite-Leases
  deduplizieren Relationen pro Datenbank, nicht die gesamte Provider-Rate.
- Die aktuelle lokale Audit-Datenbank enthält keine bestehenden
  Providerfehlerhistorien; der Bericht kennzeichnet ungeprüfte Relationen.

Manual real-provider checks still recommended:

1. Eigenen Valhalla-Endpunkt konfigurieren, begrenzten Wolfsburg-Prewarm ausführen
   und mit --report Endpointmethoden, Versuche und gerichtete Ergebnisse prüfen.
2. Reale no_path-, distance_limit-, 429/Retry-After- und unavailable-Fälle prüfen;
   keine Reparatur bei deterministischem No-path oder Providerstörung erwarten.
3. Restart während Vorbereitung, anschließende Recovery und bereits fertige
   Angebote mit tatsächlich bekannten Graphrevisionen prüfen.
4. Produktionsbetrieb zusätzlich mit der eigenen Providerinstanz beobachten.

Source, Tests und Dokumentation werden direkt auf `feature/frontend-v2`
committed. `static/dist` bleibt lokaler generierter Build-Output. Keine
Spieler-Datenbanken, Secrets oder Testartefakte werden gestagt.

**Branch push explicitly authorized. No PR. No merge.**

---

# Historischer Qualitätsbericht (unverändert, frühere Implementierung)

# Qualitätsbericht: Frontend-v2 und Wirtschaft

Stand: 25.09.2026, geprüfte Implementierung `05b4f08` auf dem lokalen Branch
`feature/frontend-v2`. Ausgangsbasis
`548336f` einschließlich aller drei Anfahrtscommits blieb erhalten. Die
vorhandene Abholdokumentation wurde separat als `742e14b` gesichert.
Hooks sind aktiv. Keine Veröffentlichung, kein PR, kein Merge.

## Implementiertes Ergebnis

- Beta(3,1)-Beladung innerhalb unveränderter NHM-/Distanzgrenzen; unabhängige
  gewichtete Auswahl des Generierungsfahrzeugs und keine exklusive Bindung.
- Direkter Katalog-Wartungssatz, 80 € Grundkosten und tatsächlich geplante
  Energieeinkäufe. Decimal/HALF_UP, exakte Addition gerundeter Komponenten.
- Immutable NHM-Mindesttarife, Kostensnapshots und transparente Quotes.
  Fahrzeugwechsel verändert weder Tonnage noch Angebotstarif.
- Global atomarer Startup-Rebuild für bestehende Profile und eigene idle-
  Städte; beide Referenzkataloge validiert/gecacht. Keine Routingaufrufe und
  keine historische Rekonstruktion. Fehler verhindert Serverfreigabe.
- Markt-Stadtauswahl ohne Ziele oder enroute-Checkpoints; ungültige Auswahl
  inklusive URL wird zurückgesetzt. Kein Marktrefresh bei Pan/Zoom.
- Persistente Account-Farben mit zehn validierten Werten und unverändertem
  Fallback; eigene/öffentliche Darstellung, Front/Seite/Map, Gruppenassets,
  selektive Facility-Unterdrückung und verständliche Analyticsnamen.
- A → B → C, kontinuierliche Energie, Standortcheckpoint, atomarer Dispatch
  und gesonderter post-commit Refill bleiben erhalten.

## Tatsächlich ausgeführte Prüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Erster vollständiger `python scripts/quality.py` | bestanden: 423 Python-Tests, 4384 Statements, 100 %, 87 Frontendtests; Ruff/Format/mypy/Pyright/ESLint/Stylelint/Prettier/checkJs/Build/compileall |
| Gezielte Cache-/Manifestprüfung nach letztem Planabgleich | 2 bestanden; fehlgeschlagener Read, Retry, parallele immutable Wiederverwendung |
| Abschließender vollständiger Quality-Gate mit Vehicle-Cache | bestanden: 424 Python-Tests, 4401 Statements, 100 % Coverage; 87 Frontendtests; sämtliche Format-/Typ-/Lint-/Build-Gates bestanden |
| Browserregression vor ergänzter Kostenvisualisierung | 22 bestanden, 7,2 Minuten |
| Abschließendes `npm run test:e2e` einschließlich Kostenvisualisierung | 24 bestanden, 8,8 Minuten |
| `python scripts/audit_economy.py` | 163.296 Zeilen, alle 14 Modelle, Seed 20260925; keine Spielerzugriffe |
| `git diff --cached --check` und Hooks | bestanden; keine Prüfartefakte oder Spieler-DBs gestagt |
| Referenz-/Assetintegrität | beide kanonischen DB-Blobs unverändert gegenüber 548336f; SVG-Inventarprüfungen bestanden |
| Einzelreview | 54 direkt geänderte konkrete Python-Callables plus 2 indirekt betroffene Katalogmapper, 5 abstrakte Portmethoden und 61 Browserfunktionen/-methoden einzeln geprüft |

Die finalen lokalen Logs heißen `artifacts-economy-quality-final.log`,
`artifacts-economy-e2e-final-verified.log`, `artifacts-economy-frontend-final.log`
und `artifacts-economy-audit.log`. Zwischenläufe waren keine Abnahme:
veraltete Aggregatkostenerwartungen und historische Importfixtures wurden
korrigiert. Browserregressionen fanden eine verlorene Dispatch-Navigation
bei Stadtparameterbereinigung und eine zu früh freigegebene Blob-URL.
Beide besitzen jetzt gezielte Gegentests. Der Map-Atlas verarbeitet bereits
kolorierte Quellen genau einmal. Ein weiterer Browser-Zwischenlauf wurde
nicht als Abnahme gewertet: Ein parallel gestarteter Vite-Neubuild entfernte
kurzzeitig `static/dist/index.html` und verursachte einen HTTP-500 beim
Anmeldeseitenaufruf (23/24 bestanden). Der vollständige Browserlauf wurde
auf dem anschließend fertig gebauten Bundle wiederholt.

Die zwei Python-Warnungen betreffen bestehende Starlette/httpx- und
anyio-Deprecations. Keine Ausnahme vom 100-%-Statement-Gate wurde eingeführt.
Playwright verwendet Edge, lokalen isolierten Spielzustand, FakeRouter und
lokale Tile-Fixtures; es ist kein Live-Valhalla-/OSM-Verfügbarkeitstest.

## Wirtschaftsaudit

Die Matrix umfasst 14 Modelle × 484 operative NHM-Profile × 3 Bänder.
2.457 inkompatible Modell/NHM/Band-Kombinationen sind explizit markiert.
17.871 kompatible Kombinationen ergeben je neun Szenarien: niedrige,
typisch neu generierte und hohe Beladung, jeweils mit 0/10/50 km Anfahrt
und 100/50/10 % Startfüllung. Die typische Beladung nutzt den Median aus
101 Seed-Draws und exakt dieselbe Domainverteilung wie die Factory.

- Normierte Lastverteilung: 20.000 Draws je repräsentativem Intervall und
  Kapazität; Grenzen, Reproduzierbarkeit, Mittelwert 0,74–0,76, Median
  0,78–0,81, obere Hälfte 86–89 %, unteres Viertel 1–2,2 % getestet.
- Mindestwert der Referenzmarge in der Matrix: **45,75 %**. Diese Zahl gilt
  für die untersuchten 75/375/1000 km, nicht als Gewinnversprechen.
- **16.298** negative tatsächliche Cashflow-Szenarien; **4.878** davon mit
  typischer Beladung. Sie werden nicht durch Tonnagen-/Tarifnachbesserung
  versteckt. Tank-/Ladekäufe und Anfahrt unterscheiden sich bewusst von
  der Referenzbewertung verbrauchter Energie der Frachtstrecke.

| Modell | Scale | Inkompatible Kombinationen | Kleinste Referenzmarge | Negative typische Cashflows | Median typische Tons |
| --- | --- | ---: | ---: | ---: | ---: |
| `vw_crafter_35_130kw` | van | 453 | 49.42 % | 0 | 0.84 |
| `mercedes_sprinter_317_cdi` | van | 453 | 49.15 % | 0 | 0.80 |
| `iveco_daily_35s18` | van | 453 | 48.57 % | 0 | 0.87 |
| `mercedes_atego_818_l` | light_distribution | 366 | 46.50 % | 0 | 1.48 |
| `mercedes_atego_1224_l` | medium_distribution | 366 | 45.75 % | 362 | 3.79 |
| `man_tgl_12_250` | medium_distribution | 366 | 45.92 % | 362 | 3.93 |
| `iveco_sway_500` | heavy | 0 | 51.21 % | 704 | 18.93 |
| `renault_t_high_520` | heavy | 0 | 51.08 % | 616 | 18.91 |
| `man_tgx_520` | heavy | 0 | 51.15 % | 625 | 19.01 |
| `daf_xg_plus_480` | heavy | 0 | 51.38 % | 578 | 18.95 |
| `mercedes_actros_l_380` | heavy | 0 | 51.08 % | 620 | 18.82 |
| `volvo_fh_aero_500_isave` | heavy | 0 | 51.25 % | 620 | 18.84 |
| `scania_r460_gas` | heavy | 0 | 51.76 % | 391 | 18.41 |
| `mercedes_eactros_600` | heavy | 0 | 51.66 % | 0 | 17.21 |


CSV/JSON liegen lokal unter `artifacts/economy/` und werden nicht versioniert.
Die Tabelle ersetzt keine gesamte Marktverteilung: Profile und Szenarien
sind systematisch enumeriert, nicht nach realer Spielerhäufigkeit gewichtet.

## Architektur- und Dokumentationsabgleich

[Einzelreview](docs/FRONTEND_ECONOMY_REVIEW.md) benennt pro Callable Zweck,
Schicht, Abhängigkeiten und Seiteneffekte. Kostenresolver, Tarif-, Mengen-
und Kostenfunktionen, Startup-Service, Preference-Service und Read-Modelle
halten getrennte Grenzen. SQL bleibt in Repositories; keine Views mit
Requests oder parallele Client-Eignungs-/Preisregeln. Der GameService
materialisiert gespeicherte Quote-Ergebnisse und delegiert Berechnungen.

Aktualisiert: README, Produkt, Ziel, Milestones, Architektur, Domain, API,
Persistenz, World-/Datenquellen, UI, Tests, Observability und Security.
[ECONOMY_V2.md](docs/ECONOMY_V2.md) dokumentiert verbindliche Formeln,
Rundung, Cache-Revisionsverhalten, Historie und Auditmethodik. Frühere
Anfahrtsabnahme bleibt im Git-Verlauf und in DISPATCH_APPROACH_REVIEW.md.

## Visuelle Prüfung und verbleibende Datenlücken

Desktop (1440×900), Tablet und Mobil (390×844), Reduced Motion, Stadt-/Europa-
Zoom, Flotte/Shop, Firmenfarben, Analytics sowie Abhol-/Lieferphasen wurden
an den erzeugten Screenshots geprüft. Kostenansichten kleiner und großer
Aufträge sowie mehrerer Ladehalte wurden zusätzlich aufgenommen und visuell
geprüft: Einzelkomponenten/Summen lesbar, keine horizontale Überbreite.

Die Front-/Seiten-SVGs enthalten Rasterbilder ohne Lackiermaske. Der
implementierte SVG-Tint erhält Transparenz/Schattierung, betrifft jedoch das
gesamte Fahrzeug. Map-Assets nutzen ihre vorhandene Farbmaske. Quelldateien
bleiben unverändert; eine selektive Kabinenlackierung ist datenbedingt nicht
vorhanden. Fehlende Assets erhalten einen Fahrzeugfallback.

Alle 14 Modelle haben direkte Wartungswerte; hierfür besteht keine Datenlücke.
Der World-Katalog enthält 559 routbare Facilities, davon 95 verifizierte
und 464 ausdrücklich geschätzte Standorte. Die Berliner Testflotte erreicht
alle drei Distanzbänder mit mindestens drei Angeboten. Für inaktive Städte
wurden entsprechend der Architektur keine globalen Origin-Berechnungen
angestellt; nicht erzeugbare Bands bleiben explizite Coverage-Diagnosen.
Die 2.457 inkompatiblen Auditkombinationen werden nicht künstlich ergänzt.

Spieler-DBs, Backups, Screenshots und Prüfartefakte sind nicht Bestandteil
der Commits. Beide kanonischen Referenz-DBs stimmen bytegenau mit dem
Ausgangsstand überein.
