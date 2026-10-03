# Changelog

## Deterministischer und vielfältiger Frachtmarkt – 03.10.2026

- Gewichtete Kandidatenauswahl, Generierungsfahrzeug und Beladung werden aus
  einem versionierten SHA-256-Kontext reproduzierbar abgeleitet; neue Angebote
  behalten eindeutige UUIDs.
- Eine geprüfte Verbindung veröffentlicht sofort einen Auftrag. Weitere Runden
  bevorzugen neue Relation, Fracht und Zielstadt und wiederholen erst nach
  struktureller Erschöpfung.
- Erfolgreiche Publikation entfernt Checkpoints atomar. Abgelaufene Evidenz wird
  für vorhandenen Bestand revalidiert, ohne dabei Duplikate anzulegen.
- Stadt-/Modell-Templates werden mengenbasiert und eng gescopt gelesen; nach
  Providerarbeit entfällt der zweite vollständige Marktsnapshot. Phasendauern
  sind strukturiert und ohne Kontokennung beobachtbar.
- Ein ausschließlich manuelles Wartungskommando prüft oder bereinigt frühere
  ungenutzte Duplikate transaktional mit privatem SHA-256-Archiv. Startup und
  HTTP führen keine automatische Bereinigung aus.

## Priorisierte globale Marktvorbereitung – 03.10.2026

- Spielergebundene Vorbereitung verarbeitet nur konkrete Idle-Fahrzeuge und
  die gespeicherten Zielstädte aller aktiven Transporte ab Dispatch.
- Die bestehende fünfstufige Planung priorisiert sichtbaren Idle-/Zielbestand
  und beide Reserven. Erst ohne `partial`en Spielerbedarf bereitet ein schmaler
  globaler Batch eine Stadt-/Modell-/Band-Kombination vor.
- Globale Runden erzeugen ausschließlich wiederverwendbare Delivery-Vorlagen;
  echte Anfahrten bleiben konkretem Fahrzeugbedarf vorbehalten.
- Routingrelationen, Anker, Verbindungsevidenz und Payload-Verfügbarkeit werden
  pro Runde mengenbasiert gelesen. PostgreSQL verwendet native psycopg-
  Transaktionskontexte ohne kollidierendes implizites und explizites `BEGIN`.
- Die lesende Supabase-Abnahme misst 11 ms für 246 Anker und 54 ms für 133
  Routenpayloads. Die globale Bandzählung benötigt bei 1.761 Vorlagen rund
  0,74 s und bleibt deshalb ausdrücklich auf die verdrängbare Priorität 3 begrenzt.
- Der Stadtmarkt lädt und erneuert nur mit gültigem Idle-Fahrzeugscope. Die UI
  meldet Angebote, Vorbereitung, erschöpfte Coverage und Leermarkt wahrheitsgemäß.

## Supabase-Produktionsruntime – 02.10.2026

- Produktive Spielstände und beide Referenzkataloge verwenden private
  PostgreSQL-Schemas auf Supabase; SQLite bleibt Tests und Offline-Werkzeugen
  vorbehalten.
- Bestehende drei Spielkonten bleiben über eine eng begrenzte same-origin
  Loginbrücke erreichbar. E-Mail-Zuordnung, scrypt-Passwort und historische
  kompakte UUID verweisen weiterhin auf denselben Spielstand; Neuregistrierungen
  bleiben bei Supabase Auth.
- PostgreSQL-Kompatibilität für Login-Limits sowie migrierte Zeit- und
  Energiewerte stabilisiert. Echte fachliche Abweichungen werden weiterhin
  abgelehnt.
- Python- und Browsertests sind von `.env`, Live-Supabase und produktiven
  Datenbanken isoliert. Fehlende lokale Kataloge werden für einen frischen
  Checkout deterministisch als ignorierte synthetische Fixtures erzeugt.
- Private Schemas entziehen `PUBLIC`, `anon` und `authenticated` alle Rechte.
  72 Tabellen besitzen RLS; der Start lehnt fehlende RLS-Härtung ab. Drei
  gemessene Runtime-Fremdschlüsselpfade erhalten gezielte Indizes.
- Prüfungen und verbleibende Betriebsgrenzen: [Qualitätsbericht](QUALITY_REPORT.md)
  und [Supabase-Laufzeit](docs/SUPABASE_RUNTIME.md).

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
