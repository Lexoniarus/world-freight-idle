# Changelog

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
