# Changelog

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
