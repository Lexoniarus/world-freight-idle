# Qualitätsbericht: Fahrzeugenergie und automatische Pausen

Stand: 23.09.2026. Umfang: `feature/vehicle-energy` gegenüber main b068191
(nach PR #10). Lokale Umgebung: Windows, Python 3.11.9, Node 24 und
Microsoft Edge. Keine reale iPad-/Safari-Abnahme und kein Docker-Build.

## Verhalten und Erhaltung

- Alle 14 Modelle aus dem angereicherten Katalogschema 2.1.0 verwenden
  validierte Energieprofile. Nutzerquellen und Bildmetadaten bleiben erhalten.
- OwnedVehicle kapselt Kauf-Snapshot und persistenten Energiecheckpoint.
  JourneyPlan berechnet Verbrauch, Geschwindigkeit, Reserve und mehrere Halte.
  Pausenende füllt vollständig auf; Zielankunft mit Reserve erzeugt keinen Halt.
- ActiveTransport besitzt den historischen Plan. Settlement speichert
  Endfüllstand, Standort, Auszahlung und Status atomar und genau einmal.
- Valhalla-Daten, bisherige Kilometerkosten und Auszahlungen bleiben erhalten.
  Es gibt keine zusätzlichen Kraftstoffgebühren oder reale Stationssuche.
- Flotte, Shop und Transporte zeigen Energie. Karte und Panels interpolieren
  denselben Serverplan. Die öffentliche Projektion enthält ausschließlich
  Bewegung, Phasen und Zeitintervalle, keine privaten Energiemengen.
- Bestehende Assets, Bildauswahl, Farbmasken und Bildknoten bleiben erhalten.
  `git diff b068191 -- assets` enthält keine Änderungen.

## Werkzeugprüfungen

Vollständiges Quality Gate und Browserregression auf dem Implementierungsstand
b484ac2 sind in [GitHub Actions](https://github.com/Lexoniarus/world-freight-idle/actions/runs/35891338391)
bestanden:

Auch der abschließende lokale Lauf `python scripts/quality.py` ist vollständig
bestanden: 317 Python-Tests, 100 % Core-Statement-Coverage und sämtliche
Frontend-/Build-Prüfungen. Frühere fehlgeschlagene Zwischenläufe sind damit
durch einen vollständigen Lauf auf dem korrigierten Stand ersetzt.

| Prüfung | Ergebnis |
| --- | --- |
| Python, Manifest, Architektur-/Gegentests | 317 bestanden |
| Core-Statement-Coverage | 3488 Statements, 0 ungedeckt, 100 % |
| Ruff und Format | bestanden |
| mypy / Pyright | 88 Quelldateien fehlerfrei / 0 Fehler |
| Frontendverhalten | 60 Tests bestanden |
| ESLint, Stylelint, Prettier, checkJs | bestanden |
| Vite-Produktionsbuild | bestanden |
| Browser | 13 bestanden, lokal Edge und CI Chromium |

Weitere Nachweise:

- 60 Frontendtests; ESLint, Stylelint, Prettier, checkJs und Vite-Produktionsbuild.
- 13 Desktop-/Mobil-Browserszenarien vollständig bestanden (1440 × 900,
  390 × 844), darunter Laden/Weiterfahrt, Logout/Offline-Ankunft und Restenergie.
- Python-/JavaScript-Zeitachsen verwenden eine gemeinsame Fixture für exakte
  Fahrt-/Pausengrenzen. Eigene und fremde Fahrzeuge stehen während der Pause
  an derselben Streckenposition.
- Gezielte Regressionen für konkurrierende Disposition, Rollback, Katalogausfall,
  abweichende Energiecheckpoints und fehlerhafte Importdokumente.

Lokale Prüfprotokolle liegen unter `artifacts/vehicle-energy-quality-complete.log`
und `artifacts/vehicle-energy-e2e-final.log`, außerhalb von Git.
Der vollständige CI-Auszug liegt lokal in `artifacts/energy-ci-verified.log`.

## Architektur- und Änderungsreview

Manuell geprüft: Domain-Invarianten, Funktionsverantwortung, DI,
Transaktionsgrenzen, API-/Persistenzmapping, Datenschutz der öffentlichen
Projektion und Frontend-Ressourcenbesitz.

- Reine Planung liest weder Systemzeit noch SQL. Services orchestrieren;
  SQL und Dokumentmapping bleiben in bestehenden Repositories.
- Routing läuft außerhalb der Schreibtransaktion. Angebot und Fahrzeugwerte
  werden anschließend erneut gelesen; die Disposition plant unter Schreibsperre
  abschließend neu. Keine Schreibzugriffe pro Animationstakt.
- Keine zusätzliche Adapterhierarchie oder parallele Alt-/Neulaufzeit.
  Alte Schemata sind ausschließlich in expliziten Offline-Werkzeugen bekannt.
- Die neue Anzeige benutzt vorhandene Taktgeber. DOM-Texte und Meterwerte werden
  aktualisiert, ohne Bilder neu anzulegen. Bestehendes Cleanup bleibt erhalten.
- Im Review korrigiert: erneute Angebotsprüfung nach Routing, Ablehnung falscher
  Snapshot-Container/Versionstypen und unbekannter Fahrtplanfelder. Gegentests
  sichern diese Befunde und die öffentliche Feld-Whitelist ab.

Desktop- und Mobil-Screenshots mit isolierten Testdaten wurden visuell geprüft.
Browsertests simulieren Routing und Tiles. Sie ersetzen keinen Nachweis echter
Tankstellen, externer Verfügbarkeit oder einer realen iPad-Bedienung.

## Bestandsübernahme und Betrieb

Nach bestandenem vollständigem CI-Quality-Gate und lokaler Browserregression
wurde der Spielserver gestoppt und Schema 1.0.0 explizit nach 1.1.0 übernommen.
SQLite-Backup, read-only Quellprüfung, neue Zieldatei, Integritäts-/Fremdschlüssel-
prüfung und vollständiger Datensatzvergleich waren erfolgreich. Ein zusätzlicher
unabhängiger Vergleich bestätigte sämtliche alten Spalten und Snapshotdaten:

- 3 Konten und Spielerstände, 21 Fahrzeuge, 9 offene Angebote, 21 Transporte.
- 18 aktive und 3 bereits abgerechnete Transporte; unveränderte Zeiten, Routen,
  Standorte, IDs, Kaufwerte, Guthaben, Reputation und wirtschaftliche Fakten.
- 1 vorhandene Session, Passwort-Hashes und Auth-Daten unverändert bewahrt.
- Alle Fahrzeuge einmalig mit vollem Energieinhalt; Alttransporte ungemessen.

Die geprüfte Datei wurde als `data/game.db` aktiviert. SQLite-Backup und
unveränderte Originaldatei bleiben unter `data/backups/` außerhalb von Git.
Alle drei Profile, Fahrzeuge und Transporte wurden über die neuen Repositories
vollständig gelesen. `python main.py` läuft wieder auf `0.0.0.0:8000`;
Loginseite und Health-Endpunkt antworten mit HTTP 200. Echte Profilpasswörter
wurden weder benötigt noch geändert. Bereits offene Browserseiten neu laden.
Vorhandene Sessions werden beim Energie-Upgrade bewahrt; der getrennte
KV-Altformatimport hat weiterhin seine ausdrücklich andere Session-Regel.

## Dokumentationsabgleich und Grenzen

README, GOAL, UI DESIGN, Produkt, Zielstand, Meilensteine, Architektur, Domain,
Persistenz, API, Datenquellen, Tests und Beobachtbarkeit sind mit der Umsetzung
abgeglichen. Technische Katalogwerte bleiben von Spielannahmen unterscheidbar.
M1 und öffentlicher Produktionsbetrieb sind damit nicht vollständig abgenommen.
Wetter, Beladungseinflüsse, Wartung, Ladeverläufe und Stations-APIs bleiben offen.
Ein tatsächlicher Docker-Build wurde mangels installiertem Docker nicht ausgeführt.
