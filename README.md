# World Freight Idle

[GitHub-Repository](https://github.com/Lexoniarus/world-freight-idle) ·
[Quality CI](https://github.com/Lexoniarus/world-freight-idle/actions/workflows/quality.yml)

Browserbasierter Multiplayer-Logistik-Idler mit Python/FastAPI, SQLite und einer
MapLibre-/OpenStreetMap-Weltkarte. **UI First: spielbare Grundlage, M1 noch in
Arbeit.** Die aktuelle Basis ist lokal und automatisiert geprüft; sie ist kein
freigegebener öffentlicher Produktionsdienst.
<img width="1897" height="887" alt="image" src="https://github.com/user-attachments/assets/cf9b7716-34a4-4ae0-9021-593feef781e8" />


## Aktueller Stand

- Registrierung, Anmeldung, getrennte persistente Profile und Lieferungsrangliste.
- Aufträge auswählen, Fahrzeug disponieren, parallele Transporte verfolgen,
  Offline-Ankünfte abrechnen und die Flotte erweitern.
- 14 DB-Fahrzeugmodelle mit Kaufpreis, Nutzlast, Reputationsfreigabe und
  Kilometerkosten sowie Energieprofilen und Höchstgeschwindigkeit; lokale
  Karten-, Front- und Seitenbilder für alle Modelle.
  Katalogfotos mit Herkunft/Lizenz bleiben Ersatz für Modelle ohne lokale Grafik.
- Neue Profile: **175.000 Euro plus kostenloser IVECO S-Way 500 XC13** in Berlin.
  Gekaufte und vergebene Fahrzeugwerte sind gespeicherte Snapshots.
- Persistenter Tank-/Batterieinhalt, konstanter Verbrauch und automatische
  Tank-/Ladepausen mit 10 % Reserve. Keine zusätzlichen Kraftstoffgebühren.
- Permanente Karte, Kontextpanels, mobile Bedienung, Tastatur und Fehlerzustände.

Offen: eigenständige Spielerunternehmen, eigene Depots, gemeinsamer knapper Markt,
Wartung, Stationssuche, Ladeverläufe und Satelliten. Öffentliche Frachtstandorte sind keine
eigenen Depots. Reale Referenzunternehmen, Facilities, dokumentierte Güter und
Koordinaten kommen aus dem separaten read-only WorldCatalogue. 559 Facilities
verwenden verifizierte oder ausdrücklich für die Simulation geschätzte
Koordinaten. Market v2 aktiviert Stadtmärkte eigener idle Fahrzeuge anhand
von NHM-, Distanz-, Scale- und Capability-Profilen.
Valhalla erhält gespeicherte Koordinaten; Geschäftsbeziehungen, Mengen,
Einzelaufträge und Wirtschaftswerte bleiben simuliert.
Es gibt keinen erfundenen Ersatz für ausgefallene Straßenrouten.

## Lokal starten

Die **Repositorywurzel enthält main.py, app/, frontend/ und package.json**.
Alle folgenden Befehle werden dort ausgeführt. Benötigt: Python >= 3.11,
Node.js 24, npm und Git. Node wird für Tests und Build benötigt; zur Laufzeit
liefert FastAPI die zuvor gebauten Dateien aus.

Windows / PowerShell:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
npm ci
npm run build
git config --local core.hooksPath .githooks
./.venv/Scripts/python.exe main.py
```

Linux/macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
npm ci
npm run build
git config --local core.hooksPath .githooks
python main.py
```

Danach [Anmeldung öffnen](http://127.0.0.1:8000/login). Mit aktivierter virtueller
Umgebung genügt überall `python main.py`. Nach Frontendänderungen neu bauen.
Für den reinen Python-Spielbetrieb genügt requirements.txt statt requirements-dev.txt.

Der Server bindet standardmäßig an `0.0.0.0:8000`. Im selben WLAN die LAN-IP des
Serverrechners verwenden; die Firewall muss Python dafür erlauben. HOST=127.0.0.1
beschränkt den Zugriff auf den eigenen Rechner.

## Konfiguration und Daten

[.env.example](.env.example) dokumentiert Prozess-Umgebungsvariablen;
**.env-Dateien werden nicht automatisch geladen**. PowerShell-Beispiel:

```powershell
$env:HOST = "127.0.0.1"
./.venv/Scripts/python.exe main.py
```

| Variable | Standard / Zweck |
| --- | --- |
| HOST / PORT | 0.0.0.0 / 8000 |
| DATA_DIR / DB_PATH | data/ bzw. data/game.db; private Spielstände |
| VEHICLE_CATALOGUE_PATH | Mitgelieferter data/world_freight_vehicle_catalog.sqlite3 |
| WORLD_CATALOGUE_PATH | Mitgelieferter data/world_freight_company_facility_mvp.sqlite3, Schema 4.2.0 |
| GAME_TIME_SCALE | 1 = Echtzeit; Beschleunigung nur für lokale Tests |
| COOKIE_SECURE | false für lokales HTTP; true bei HTTPS-Betrieb |
| VALHALLA_URL | Routing gespeicherter Facility-Koordinaten |
| NOMINATIM_URL | Ausschließlich Offline-Import/Enrichment, kein Spielserver-Lookup |
| HTTP_USER_AGENT | Vor öffentlichen Providerabrufen mit passendem Kontakt setzen |

Der Katalog wird nur lesend geöffnet und unabhängig vom Spielstandpfad gefunden.
Fehlende/defekte Katalogdaten ergeben 503 bei Katalog/Kauf oder erster Startflotte;
bestehende Fahrzeuge bleiben nutzbar. Spielstände und Backups gehören nicht ins Git.
Nur die beiden Referenz-Katalogdateien werden mitgeliefert. Lizenz-/Datenherkunft:
[DATA_SOURCES](docs/DATA_SOURCES.md).

Gezielte lokale Profilpflege: `python scripts/update_test_profile.py --username
NAME --vehicle ID=MODELL` (als eine Befehlszeile). Sie erstellt zuerst ein SQLite-
Backup. Ohne --cash bleibt Guthaben erhalten; IDs und Transport-Snapshots bleiben
bestehen. Modellwechsel sind nur im Stand möglich und erhalten den Füllgrad.
Keine automatische Migration und kein öffentlicher Pflege-Endpunkt.

## Relationale Spielstände und Offline-Übernahme

Der Server verwendet ausschließlich das relationale Schema 1.1.0. Alte KV-
Datenbanken werden beim Start abgewiesen. Neue leere Datenbanken benötigen
keine Migration. Für Altbestände den Server stoppen und zuerst prüfen:

```sh
python scripts/import_legacy_game.py --source OLD.db --check
python scripts/import_legacy_game.py --source OLD.db --backup BACKUP.db --output NEW.db
```

Das Werkzeug schreibt nur eine neue Datei und gleicht Konten, Spielwerte,
Fahrzeuge und historische Transporte ab. Keine automatische Aktivierung.
Nach erfolgreicher Prüfung kann NEW.db als game.db aktiviert werden; das Backup
bleibt erhalten. Sessions/Caches werden nicht übernommen, neue Anmeldung ist
nötig. Die drei lokalen Testkonten wurden am 23.09.2026 so übernommen.
Details: [Persistenz](docs/RELATIONAL_STATE.md), [Tests](docs/TESTING.md).

## Entwicklung, Branches und Qualität

Verbindlich: [Branchplan](docs/BRANCHING.md),
[Coding Standards](docs/CODING_STANDARDS.md) und [AGENTS.md](AGENTS.md).
`main` ist die stabile Integrationsbasis; jede Änderung erfolgt auf einem kurzen
Arbeitsbranch. Kein permanenter develop-Branch, keine direkten main-Commits.

```sh
git switch main
git switch -c feature/kurze-beschreibung
```

Vor Integration mit aktivierter Python-Umgebung:

```sh
python scripts/quality.py
npm run test:e2e
```

Ohne Aktivierung unter Windows den Python-Befehl durch
`./.venv/Scripts/python.exe scripts/quality.py` ersetzen. Das Gate umfasst Ruff,
Formatierung, mypy, Pyright, Python-Tests, Function-Test-Manifest, **100 % Core-Statement-
Coverage**, Frontendtests, ESLint, Stylelint, Prettier, checkJs und Produktionsbuild.
Browserprüfung verwendet lokal Microsoft Edge. Alternativ Chromium installieren
und PLAYWRIGHT_CHANNEL=chromium setzen; CI verwendet Chromium.

Browsertests starten einen isolierten Server auf Port 8011 mit temporären Daten
und simulierten externen Medien/Providern. Aktuelle ausgeführte Ergebnisse,
Architekturreview und Abnahmegrenzen: [QUALITY_REPORT](QUALITY_REPORT.md).
Die vollständige reale iPad-/Safari-Abnahme bleibt offen.

## VS Code und Pylance

Den Repositoryordner mit pyproject.toml öffnen und über **Python: Select
Interpreter** die lokale `.venv` auswählen. Pylance übernimmt den festgelegten
`standard`-Modus aus `[tool.pyright]`; globale Strict-Einstellungen werden nur für
dieses Projekt überschrieben. Python-Typprüfung separat: `npm run typecheck:python`.
Falls alte Meldungen stehen bleiben: **Developer: Reload Window** ausführen.
Die Projektkonfiguration schaltet die Typprüfung nicht ab; Pyright und mypy sind
beide Teil des Quality Gates.

## Docker und Betrieb

`docker compose up --build` baut das Frontend und liefert beide Kataloge
und `assets/vehicles/` mit aus;
Compose bindet beide Kataloge zusätzlich separat nur lesend ein. Docker wurde in
der aktuellen lokalen Abnahme nicht ausgeführt. Individuelle Deployments müssen
beide Referenzkataloge sowie Assets und zugehörigen Frontend-Build mitliefern.
Nach einer Asset-Pfadänderung benötigen offene Seiten einen Reload.

Aktuell: ein Prozess, SQLite und gemeinsame Provider-Limiter. HTTPS, kontrollierter
Reverse Proxy, Betriebsbackups, geeignete Provider und weitere Konten-/Betriebs-
funktionen sind vor öffentlichem Betrieb zu ergänzen: [SECURITY](docs/SECURITY.md).
Das GitHub-Repository ist als `origin` eingerichtet und derzeit öffentlich.
GitHub Actions prüft
Pushes und Pull Requests. Squash-Merge und automatisches Löschen gemergter
Arbeitsbranches sind konfiguriert. Serverseitiger Branchschutz ist noch nicht
aktiv. Die frühere Tarifbeschränkung galt für den damaligen privaten Zustand.
Lokale Hooks und verbindliche Reviewregeln gelten weiterhin; sie ersetzen diesen Schutz
nicht. Details: [BRANCHING](docs/BRANCHING.md).

## Dokumentation

- [GOAL](docs/GOAL.md) und [UI DESIGN](<docs/UI DESIGN.md>): Vision und UI-First-Reihenfolge.
- [PRODUCT](docs/PRODUCT.md), [TARGET](docs/TARGET.md), [MILESTONES](docs/MILESTONES.md): Umfang und Abnahme.
- [ARCHITECTURE](docs/ARCHITECTURE.md), [DOMAIN_MODEL](docs/DOMAIN_MODEL.md), [API](docs/API.md): technische Verträge.
- [TESTING](docs/TESTING.md), [QUALITY_REPORT](QUALITY_REPORT.md): Prüfungen und Grenzen.
- [MAP_PROVIDERS](docs/MAP_PROVIDERS.md), [DATA_SOURCES](docs/DATA_SOURCES.md): externe Daten.
- [RELATIONAL_STATE](docs/RELATIONAL_STATE.md), [WORLD_CATALOGUE](docs/WORLD_CATALOGUE.md): aktuelle Persistenz und Referenzwelt.
- [Asset-Manifest](assets/MANIFEST.md): Modellordner, Verwendung und Prüfsummen.
- [Archivierte Refactor-Chronik](docs/archive/REFACTOR_EXECUTION.md): historische Zwischenstände.
- [BRANCHING](docs/BRANCHING.md), [CHANGELOG](CHANGELOG.md): Zusammenarbeit und Änderungen.

Jeder routbare Standort bietet passende Auftragsmengen für alle vorhandenen
Fahrzeug-Nutzlastklassen; Details: [WorldCatalogue](docs/WORLD_CATALOGUE.md).


### Bestehenden relationalen Spielstand auf Energie umstellen

Server vor der Ausführung stoppen. Quelle, Backup und Ziel müssen getrennte
Dateien sein; vorhandene Ziele werden nicht überschrieben:

```sh
python scripts/upgrade_vehicle_energy.py --source data/game.db --check
python scripts/upgrade_vehicle_energy.py --source data/game.db --backup data/backups/pre-energy.db --output data/game-energy.db
```

Erst nach erfolgreichem Abgleich die neue Datei als `game.db` aktivieren und mit
`python main.py` starten. Konten, Sessions und bisherige Kaufwerte bleiben
unverändert; vorhandene Transporte erhalten keine nachträglichen Pausen oder
Energieabzüge. Bei unbekannten Modellen bricht die Übernahme ab. Kein automatisches
Upgrade beim Serverstart. Details: [Persistenz](docs/RELATIONAL_STATE.md).


### Tatsächliche Abholanfahrt

Aufträge starten am Fahrzeugstandort und führen über die Abholung zum Lieferziel.
Anfahrt zählt zu Zeit, Energie und Kosten; Frachterlös nur zur Frachtstrecke.
Details: [Routenarchitektur](docs/ARCHITECTURE.md) und
[Funktionsreview](docs/DISPATCH_APPROACH_REVIEW.md).

## Frontend-v2: aktuelle Wirtschaftsregeln

Mengen bevorzugen hohe Auslastung innerhalb der World-Profile. NHM-Mindestfracht
und tatsächliche Wartung/Energieeinkäufe sind getrennt gespeichert. Beim
Start werden offene Märkte aller Profile atomar für eigene idle-Städte neu
aufgebaut. Firmenfarben sind accountbezogen persistent; Kartenfahrzeuge
und Analytics besitzen konsistente Darstellung. Details: [Economy v2](docs/ECONOMY_V2.md).


Nach diesem Update den Spielserver neu starten: Der Start validiert beide
Kataloge und ersetzt offene Angebote atomar mit neuen Tarif-Snapshots.
Bereits laufende und abgeschlossene Transporte behalten ihre Konditionen.
