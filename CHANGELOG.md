# Changelog

## Eigentümerklare Testmodule und eindeutige Flotte – 02.11.2026

- Aktive Fahrzeuge erscheinen im Flottenkatalog genau einmal unter
  `Unterwegs`; Abfahrts- und Zielstadt bleiben Filterkriterien, erzeugen aber
  keine doppelten Fahrzeugkarten mehr.
- Die früheren Frontend-Sammelmodule für Core, Lifecycle, Map, Runtime und
  Fahrzeugassets sind entfernt. Geometrie, API, State, Controller, Map-Layer,
  Traffic, Routencache und Bildbindungen besitzen eigene benannte Testmodule.
- Marktbestand ist nach Planung, Vertragsbildung, Publikation und Vorbereitung
  getrennt. Marktworker, Routennachweise und Preparation-Store werden ebenfalls
  unabhängig geprüft.
- Gameplaytests sind nach Initialisierung, Dispatch, Settlement und Queries
  gegliedert; Legacy-Importtests nach Parsing, Reconciliation und CLI-Sicherheit.
- Verhaltenstests verwenden synthetische In-Memory- oder kleine SQL-Kataloge.
  Nur die expliziten Referenzabnahmen öffnen die ausgelieferten Binärkataloge.
- Playwright enthält 14 Browsergrenzen. Backend-Bestandsregeln, Kaufregeln und
  Katalogmengen werden nicht mehr zusätzlich im Browser nachgerechnet.
- Python- und Playwright-Fälle besitzen nun ein hartes Zeitlimit von zehn
  Sekunden. Die vollständige Abnahme bestand mit 591 Python-Tests bei 100 %
  Coverage, 127 Frontendtests und 14 Playwright-Fällen; langsamster Einzelfall
  war der 7,1 Sekunden lange Dispatch-/Settlement-Browserfall.
- Sämtliche Läufe verwendeten lokale SQLite-Testdaten und Fake-Provider; es gab
  keine Supabase- oder Live-Providerzugriffe.

## Kleine synthetische Testpyramide – 31.10.2026

- Domain-, Service- und Gameplaytests verwenden kleine typisierte In-Memory-
  Kataloge statt pro Test den 23-MiB-Weltkatalog zu kopieren.
- Echte Welt- und Fahrzeugkataloge werden nur noch in ausdrücklich benannten
  Repositoryabnahmen geprüft; alle anderen Fixtures heißen `synthetic_*`.
- Repositoryfehler mutieren zwei kleine, lesbare SQL-Kataloge statt Kopien der
  ausgelieferten Binärdateien.
- Python-Tests laufen lokal in rund einer Minute; der langsamste Einzelfall
  bleibt unter zehn Sekunden bei unverändert 100 % Core-Coverage-Ziel.
- `VehicleGroups` trennt Aktivierung, Zoom und Fahrzeugliste; vier kleine DOM-
  Tests prüfen die Klick-/Fokus-/Payloadverträge. Generische Frontendtestmodule
  tragen jetzt Zuständigkeitsnamen.
- Playwright wurde von überlappenden Sammelabläufen auf Browsergrenzen in
  Auth/Navigation, Dispatch, Market, Company, Map und Assets reduziert. Jeder
  lokale Fall blieb im Abnahmelauf unter sieben Sekunden.
- Python-, Frontend- und Browserqualität laufen in CI parallel mit hartem
  20-Minuten-Timeout und ohne automatische Wiederholung.
- Keine Supabase-, Provider- oder öffentlichen Tile-Aufrufe wurden ausgeführt.

## Abschließende OOP-Härtung der lokalen Runtime – 30.10.2026

- Spieler-Lifecycle, Initialisierung, Dispatch und Settlement verlangen immer
  vollständige Marktservices; optionale Test-/Produktionsmodi sind entfernt.
- Dispatch verwendet ausschließlich vorbereitete Routen. Router,
  Anchor-Auflösung und Provider-Fallback gehören nicht mehr zum
  `DispatchPlanningService`.
- `RoutingEvidenceReader` besitzt nur Lesesnapshots und Payload-Zugriff;
  `RoutingPreparationService` besitzt Providerarbeit, Leases und Publikation.
- Gameplay-Use-Cases liegen unter `app/services/gameplay`, Stock-Planung und
  -Publikation unter `app/services/market/stock`, Routing unter
  `app/services/routing`.
- Dispatch löscht nicht länger den übrigen vorbereiteten Pool. Er konsumiert
  genau ein Offer und invalidiert den Bedarf atomar; der Worker füllt später
  auf.
- Worker-Tests prüfen den öffentlichen Lifecycle statt privater Task-/Event-
  Attribute. Direkte SQLite-Testverbindungen werden zuverlässig geschlossen.
- README, Produkt-, Ziel-, Meilenstein-, UI- und Architekturdokumentation nennen
  einheitlich Schema 1.2.0, WorldCatalogue 4.2.0, den Lifespan-Worker und den
  bedarfsgesteuerten Refill. Die frühere Zwei-Prozess-Entscheidung bleibt nur
  noch ausdrücklich als aufgehobene Historie erhalten.
- Sämtliche Prüfungen bleiben lokal; es gab keine Supabase- oder
  Live-Providerzugriffe.

## Zuständigkeitsrefactor der lokalen Runtime – 28.10.2026

- Die lokale `GameRuntime` besitzt immer Preparation-Store und
  Routing-Readiness; der frühere halb konfigurierte Testmodus ist entfernt.
- `PlayerMarketRouteService` liest und bindet ausschließlich vorhandene
  Routenfakten. Providerarbeit liegt getrennt im
  `MarketRoutePreparationService` und wird nur vom Stock-Worker aufgerufen.
- Wiederverwendbare Testaufbauten liegen unter `tests/support`; ausführbare
  Testmodule importieren einander nicht mehr als versteckte Bibliothek.
- `MapInteractions` besitzt Hit-Testing, Hover-Popup und MapLibre-Listener
  samt Cleanup. `WorldMap` bleibt Renderer- und Composition-Orchestrator.
- Dispatch-Eignung ist eine reine Prüfung; die Standortauflösung liegt in einem
  eigenen injizierten Service und mutiert keine Fahrzeuge während der Prüfung.
- Routing-Relationen, Anker und Verbindungsevidenz werden pro Planungsrunde
  mengenbasiert gelesen statt je Candidate erneut aus SQLite abgefragt.
- Gemeinsame Vorlagen und persönlicher Spielerbestand besitzen getrennte
  Repository-Ports und konkrete SQLite-Adapter.
- Der synchrone Marktgenerator, request-seitige Publikationsvorbereitung und
  die mehrdeutige `refresh_market`-Kompatibilität wurden entfernt. HTTP-Reads
  lesen nur publizierten Bestand; Refresh invalidiert ausdrücklich den Job.
- `MarketComponents` benennt die verbleibende Composition-Grenze ohne eine
  nicht vorhandene Generierungszuständigkeit vorzutäuschen.
- Spielerbedarf, Routenfakten und Stock-Abhängigkeiten sind in
  `PlayerMarketDemandService`, `PlayerMarketRouteService` und
  `PlayerMarketStockContext` getrennt. Der Composition Root bündelt sie nur.
- `StockSnapshotReader` besitzt autoritativen Read, Bedarfsprojektion und
  Readiness-Snapshot; `StockPublicationService` besitzt nur Plan und Commit.
- `GameService` ist eine schmale Fassade. Initialisierung, Dispatch und
  Settlement liegen in drei injizierten Services mit eigenen Gegenproben.
- Kartenobjektauswahl und Navigation sind durch einen eigenen Controller
  getrennt; Frontend-Viewzustände besitzen konkrete JSDoc-Slices statt `any`.
- Referenzunternehmen heißen in Domain und API-internen Typen ausdrücklich
  `ReferenceCompany`; Spielerfirma, Depots und Mitarbeiter bleiben getrennte
  kommende Aggregate.
- Überholte Mischtests für entfernte Kompatibilitätspfade wurden durch
  fokussierte Gegenproben der echten Worker-, Stock- und Readiness-Grenzen
  ersetzt. Es wurden keine Supabase- oder Live-Providerzugriffe ausgeführt.
- Browsertests schalten Fahrtzeit über eine isolierte Testuhr fort. Passive
  15- bis 55-Sekunden-Warteannahmen wurden durch explizite Synchronisierung
  ersetzt. Überladene Mehrfahrzeug-, Karten-, Energie- und Offline-Fälle sind
  nach beobachtbarer Verantwortung getrennt; echte Integrationslaufzeit wird
  ausgewiesen statt durch höhere Timeouts oder direkte Test-SQL kaschiert.

## Lokaler bedarfsgesteuerter Frachtpool – 27.10.2026

- Supabase-/PostgreSQL-Laufzeit verworfen; `python main.py` startet wieder eine
  lokale SQLite-Runtime mit genau einem Lifespan-Worker.
- GET, Runtime-Polling und Kartennavigation erzeugen keine Marktjobs oder
  Provideraufrufe. Fachliche Writes wecken den Worker ereignisgesteuert.
- Vorbereitung gilt nur konkreten idle Fahrzeugen und ab Dispatch deren
  Zielstädten. Weltweiter Katalog-Preload, 60-Minuten-Schwelle und periodisches
  Wiederöffnen fertiger Jobs entfernt.
- Erfolgreiche Routenrelationen bleiben für denselben Fingerprint dauerhaft
  wiederverwendbar. Fehlende Geometrie wird erst beim exakten Load abgewiesen.
- Deterministische gewichtete Marktbedingungen bei weiterhin eindeutigen IDs;
  pro Runde genau ein Angebot und Vielfalt vor Wiederholung.
- Gemeinsame Vorlagen in ein eigenes Repository extrahiert; Legacy-Batch,
  Startup-Rebuild, globale Worker-Lease und Prozesssupervisor entfernt.
- Frontend-HTTP läuft über `GameApiClient`; der Scheduler pollt keinen Markt.
  `DispatchEligibilityService` bildet den Seam für den späteren Mitarbeiter-
  und Fahrerbedarf, ohne diesen vorzeitig zu implementieren.
- Marktlisten und Refresh verlangen jetzt ein konkretes eigenes idle Fahrzeug.
  Ohne gültigen Scope sendet der Browser keine Anfrage und meldet keinen
  angeblichen Refresh-Erfolg; der HTTP-Vertrag antwortet ohne `vehicle_id` 422.
- `ContractFactory` trennt Ziehung, Konditionen und Snapshot-Erzeugung.
  `StockPublicationService` trennt autoritativen Read, Projektion,
  Publikationsplan und gefencten Commit, ohne neue SQL- oder Providerpfade.
- Marktbedarf weckt den Lifespan-Worker erst nach erfolgreichem äußeren
  Datenbank-Commit und threadsicher im besitzenden Eventloop; Rollbacks
  erzeugen keine Phantomarbeit und ein frühes Wake-up geht nicht verloren.
- Flottenfilter reagieren unmittelbar auf Eingaben. Der Browser-Gegentest für
  Energiepausen synchronisiert den tatsächlichen Serverzustand an der
  Client-/Server-Zeitgrenze, ohne die Energiesemantik abzuschwächen.

## Befahrbare Standortverbindungen – 27.09.2026

- Jede Anfahrt und Lieferung benötigt echte Truck-Routen in beiden Richtungen
  mit passenden Endpunkten. Anker und beide Routen werden atomar freigegeben.
- Automatische Reparatur mit maximal fünf Kandidaten je Standort innerhalb
  1.000 Metern, 25 Kombinationen und 120 Sekunden; bereits geprüfte Anker bleiben
  für einzelne unerreichbare Ziele stabil.
- Versionierte Nachweise ersetzen alte positive und negative Routingcaches.
  Wiederprüfung nach 24 Stunden, bei definitiven Fehlern nach einer Stunde,
  bei vorübergehenden Störungen nach 60 Sekunden.
- Wolfsburger LKW auf isolierter Spielstandkopie regulär disponiert; Ankunft
  und nächster Auftragsstart geprüft. Backup vorhanden, echter Spielstand
  unverändert. Gezielte Prüfungen und noch offene vollständige Suite:
  [Änderungs- und Abnahmebericht](docs/CONNECTED_ROUTING_REVIEW.md).

## Fahrzeugenergie und automatische Pausen – 23.09.2026

- Angereicherten Katalog 2.1.0 mit allen 14 Energieprofilen angebunden;
  technische Quellen und Bildmetadaten bleiben erhalten.
- Persistente Restmengen, 10 % Reserve, automatische Tank-/Ladepausen und
  Höchstgeschwindigkeit. Unveränderte Providerdaten und Kilometerkosten.
- Unveränderliche Fahrtpläne steuern eigene und öffentliche Kartenbewegung;
  während Pausen bleiben Fahrzeuge stehen. Private Energieinhalte bleiben privat.
- Flotte, Shop, Auftragsdetails und Transporte zeigen Energie und Pausen;
  bestehende Bildknoten und lokale Assets bleiben erhalten.
- Schema 1.1.0 mit explizitem Offline-Upgrade nach Backup in eine neue Datei.
  Bestehende Fahrten behalten Zeiten, Route und Auszahlungen ohne Energieabzug.
  Konten, Sessions und bisherige Kaufwerte bleiben erhalten.
- Prüfungen, tatsächliche Bestandsübernahme und Abnahmegrenzen:
  [Qualitätsbericht](QUALITY_REPORT.md).

## Dokumentation und Fahrzeugassets – 23.09.2026

- Alle 134 SVGs bytegleich nach den 14 Katalogmodellen geordnet; 42 aktive
  Ansichten und 92 zusätzliche Dateien mit unabhängiger Inventur abgesichert.
- Eine immutable Modellzuordnung ersetzt zwei Pfadtabellen. Bildauswahl,
  Fallbacks, Spielerfarben, Rasterisierung und stabile Bildknoten bleiben erhalten.
- Hauptdokumente beschreiben aktuellen Markt, relationale Laufzeit, Grafiknutzung
  und offene Produktziele; abgeschlossene Refactor-Chronik ins Archiv verschoben.
- Build und Assets müssen gemeinsam ausgeliefert werden; offene Seiten danach
  neu laden. Keine Schema-/Profildatenänderung, kein Serverneustart.
- Ausgeführte Prüfungen und Einschränkungen: [Qualitätsbericht](QUALITY_REPORT.md).

## Persistenz-Review-Fixes – 23.09.2026

- Aktive und fällige Transporte werden vor dem Laden der Snapshots in SQL
  gefiltert; abgeschlossene Historie belastet normale Spielabfragen nicht mehr.
- Die Startprüfung erkennt unwirksame gleichnamige Transport-Guards und
  abweichende Primär-/Fremdschlüssel, ohne bestehende Dateien zu reparieren.
- Der Offline-Importer weist unbekannte verschachtelte Felder und fehlerhafte
  Container mit sicheren Feldpfaden zurück; bekannte Metadaten bleiben erhalten.
- Keine Änderung an API-Verträgen, Schema 1.0.0 oder vorhandenen Profilen.

## Domain und relationale Persistenz – 23.09.2026

- Eine typisierte Laufzeit hinter GameStateRepository/GameUnitOfWork; KV-Spielpfad
  und obsolete Domainmodelle entfernt. Öffentliche API-Projektionen bleiben kompatibel.
- Historische Transport-/Standortsnapshots, atomare Disposition und einmaliges
  Settlement; eigene relationale Ports für Accounts, Cache, Rangliste und Verkehr.
- WorldCatalogue 4.0.0 mit gespeicherten Stadt-UUIDs, Country/City/Address/Coordinates,
  getrennten NHM-Produkten/-Profilen und unveränderlichen World-Scopes.
- Offline-Import mit Backup, neuer Zieldatei, Abgleich und Rollback. Drei Testkonten
  übernommen; der kontolose Demostand bleibt ausdrücklich nur im Backup.
- Übergangscode und temporäre Umbauwerkzeuge entfernt; Docker schließt Backups aus.
- Ist-Dokumentation, ADR, Architekturtests und Gegentests konsolidiert.
  Ausgeführte Prüfungen und Abnahmegrenzen stehen in QUALITY_REPORT.md.

## Pylance-Abgleich

- Gemeinsamer Pylance-/Pyright-Standardmodus für Anwendung, Tests und Skripte.
- Pyright 1.1.414 in Lockfile und Quality Gate; 19 bisherige Standard-Diagnosen behoben.
- Explizite Protokolldeklarationen, dynamische Log-Felder und präzisere Testannahmen.

## GitHub-Anbindung

- Privates Repository Lexoniarus/world-freight-idle als origin eingerichtet.
- Quality CI und PR-Workflow aktiviert; nur Squash-Merge mit automatischer Branch-Bereinigung.
- Fehlenden serverseitigen Branchschutz wegen GitHub-Tarifgrenze ausdrücklich dokumentiert.

## Standards-Bereinigung – 18.09.2026

- Kleine Frontend-Composition-Root; getrennte Aktionen, Views, Router und Synchronisierung.
- Definierter Lebenszyklus für Timer, Listener, Animation und Anfragen.
- Kartenprojektionen, Layer, Kamera und Fahrzeuganimation getrennt; Provider injiziert.
- Dynamische DOM-Texte statt HTML-Interpolation; Fokus und Auswahl bleiben erhalten.
- Veraltete D3-/Mehrseiten-Dateien entfernt, aktive Helfer/Tests migriert.
- Backend-Service-Verdrahtung konsolidiert; unabhängige Ports und normalisierte Providerfehler.
- ESLint, Stylelint, Prettier, JSDoc/checkJs und Architektur-/Regressionstests im Quality Gate.
- Keine Datenmigration, API-Vertragsänderung oder zusätzliche Wirtschaftsmechanik.

## 0.3.0 – UI First, 18.09.2026

- Permanente MapLibre-/OSM-Weltkarte mit World Wrapping und Kontextpanels.
- Tycoon-Gestaltung, lokale Barlow-/Inter-Schriften und Fahrzeugillustrationen.
- Aufträge, Disposition, Shop, Flotte, Tracking und Rangliste auf dem vorhandenen Core.
- Mobile Sheets, Tastaturfokus, Reduced Motion, explizite Lade-/Fehlerzustände.
- Getrennte Kartenlayer, Standort-Clustering, parallele Fahrzeuganimation.
- Provider-Abstraktion; Satellitenbilder später, keine Anbieterbindung.
- Authentifizierte Standortprojektion mit Cache und Teilfehlern.
- Vite-Build, MapLibre-Worker, Docker-Build-Stufe und erweitertes Quality Gate.
- UI-/Produkt-/Architektur-/Meilensteindokumentation auf UI First abgeglichen.

## 0.2.0 – 18.09.2026

- Registrierung, Login/Logout und serverseitige, widerrufbare Sitzungen.
- Getrennte persistente Spielstände pro Benutzer, CSRF- und Login-Schutz.
- Fahrzeugshop mit zwei generischen Modellen und serverseitigen Preisen.
- Mehrere parallele Transporte; atomare Käufe, Starts und Offline-Auszahlungen.
- Gemeinsame Lieferungsrangliste mit Berücksichtigung von Offline-Ankünften.
- Einstieg über main.py, Windows-taugliches Python-Quality-Gate, Ruff und CI.
- API-, Nebenläufigkeits- und Frontendtests erweitert.
- Öffentlicher Reset-Endpunkt entfernt.
- GOAL.md mit Ist-Stand abgeglichen, Markdown bereinigt; Unternehmens- und
  Depotmodell weiterhin als offene M1-Arbeit ausgewiesen.

Bestehende unbenannte Einzelspielerstände werden nicht automatisch einem
Benutzer zugeordnet. Neue Benutzer erhalten einen unabhängigen Startzustand.

## 2026-09-18 – Stabilisierung und Fahrzeugkatalog

- Acht DB-Angebote, Reputationsfreigaben, Kauf-Snapshots und fahrzeugbezogene Kilometerkosten.
- Neue Spielstände starten mit 175.000 €; Altbestand bleibt erhalten.
- Providerdaten-/Cachevalidierung, frische Synchronisierung nach unsicheren
  Schreibantworten und Kamera über Weltkopien korrigiert.
- Rekursives Funktionstest-Manifest, Importgrenzen und JSDoc-Verträge ergänzt.

## 2026-09-18 – Fahrzeugfotos, WLAN und Startflotte

- Verifizierte Katalogfotos mit Herkunft, Lizenz und sichtbarem Fehlerersatz.
- Unveränderte Bildknoten bleiben über Panelaktualisierungen erhalten.
- Kostenloser DB-IVECO als Startfahrzeug; DB-Spielwerte als Snapshot.
- WLAN-Bindung über main.py; HOST bleibt konfigurierbar.
- Explizite Profilpflege mit Backup, bewahrten IDs und Transport-Snapshots.
- Regressionen für zwei getrennte Profile, Bildausfall und Polling ergänzt.


## 2026-09-18 – Atomarität, Cleanup und gekapselte Profilpflege

- Direkte Spielinitialisierung und Reset rollen Fehler vollständig zurück.
- AsyncExitStack schließt bereits erstellte Clients auch bei Aufbau-/Cleanupfehlern.
- Profilpflege-Service, injizierte Store-Factory und eigener Backupadapter.
- CLI weist doppelte/ungültige Zuordnungen ab und mutiert erst nach Backup.
- Fahrzeugkosten werden nach Routing innerhalb der Starttransaktion neu geprüft.
- Neue Fehler-/Architekturtests; Profilpflege-CLI in mypy aufgenommen.

## 2026-09-18 – Git-Basis und verbindlicher Branchplan

- Lokale Versionsverwaltung mit stabilem main und kurzen Arbeitsbranches.
- Erweiterte Ignore-Regeln, Text-/Binärattribute, lokale Commit-Guards und CI-Branchcheck.
- README auf den aktuellen UI-First-Stand konsolidiert, PR-Vorlage ergänzt.
- Remotes, serverseitiger Branchschutz und Releases bleiben separat einzurichten.
