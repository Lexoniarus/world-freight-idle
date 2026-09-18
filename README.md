# World Freight Idle

[GitHub-Repository](https://github.com/Lexoniarus/world-freight-idle) ·
[Quality CI](https://github.com/Lexoniarus/world-freight-idle/actions/workflows/quality.yml)

Browserbasierter Multiplayer-Logistik-Idler mit Python/FastAPI, SQLite und einer
MapLibre-/OpenStreetMap-Weltkarte. **UI First: spielbare Grundlage, M1 noch in
Arbeit.** Die aktuelle Basis ist lokal und automatisiert geprüft; sie ist kein
freigegebener öffentlicher Produktionsdienst.

## Aktueller Stand

- Registrierung, Anmeldung, getrennte persistente Profile und Lieferungsrangliste.
- Aufträge auswählen, Fahrzeug disponieren, parallele Transporte verfolgen,
  Offline-Ankünfte abrechnen und die Flotte erweitern.
- Acht DB-Fahrzeugmodelle mit Kaufpreis, Nutzlast, Reputationsfreigabe und
  Kilometerkosten; Fahrzeugfotos mit Herkunft/Lizenz und Ersatzdarstellung.
- Neue Profile: **175.000 Euro plus kostenloser IVECO S-Way 500 XC13** in Berlin.
  Gekaufte und vergebene Fahrzeugwerte sind gespeicherte Snapshots.
- Permanente Karte, Kontextpanels, mobile Bedienung, Tastatur und Fehlerzustände.

Offen: eigenständige Unternehmen, eigene Depots, gemeinsamer knapper Markt,
Wartung/Energie/Reichweite und Satelliten. Öffentliche Frachtstandorte sind keine
eigenen Depots. Reale Hub-Adressen und Straßenrouten kommen aus OSM/Nominatim/
Valhalla; Firmen, konkrete Aufträge und Wirtschaftswerte sind Spielsimulation.
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
| GAME_TIME_SCALE | 1 = Echtzeit; Beschleunigung nur für lokale Tests |
| COOKIE_SECURE | false für lokales HTTP; true bei HTTPS-Betrieb |
| NOMINATIM_URL / VALHALLA_URL | Konfigurierbare Geocoding-/Routing-Endpunkte |
| HTTP_USER_AGENT | Vor öffentlichen Providerabrufen mit passendem Kontakt setzen |

Der Katalog wird nur lesend geöffnet und unabhängig vom Spielstandpfad gefunden.
Fehlende/defekte Katalogdaten ergeben 503 bei Katalog/Kauf oder erster Startflotte;
bestehende Fahrzeuge bleiben nutzbar. Spielstände und Backups gehören nicht ins Git.
Nur die Referenz-Katalogdatei wird mitgeliefert. Lizenz-/Datenherkunft:
[DATA_SOURCES](docs/DATA_SOURCES.md).

Gezielte lokale Profilpflege: `python scripts/update_test_profile.py --username
NAME --vehicle ID=MODELL` (als eine Befehlszeile). Sie erstellt zuerst ein SQLite-
Backup. Ohne --cash bleibt Guthaben erhalten; IDs und Transport-Snapshots bleiben
bestehen. Keine automatische Migration und kein öffentlicher Pflege-Endpunkt.

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
Formatierung, mypy, Python-Tests, Function-Test-Manifest, **100 % Core-Statement-
Coverage**, Frontendtests, ESLint, Stylelint, Prettier, checkJs und Produktionsbuild.
Browserprüfung verwendet lokal Microsoft Edge. Alternativ Chromium installieren
und PLAYWRIGHT_CHANNEL=chromium setzen; CI verwendet Chromium.

Browsertests starten einen isolierten Server auf Port 8011 mit temporären Daten
und simulierten externen Medien/Providern. Aktuelle ausgeführte Ergebnisse,
Architekturreview und Abnahmegrenzen: [QUALITY_REPORT](QUALITY_REPORT.md).
Die vollständige reale iPad-/Safari-Abnahme bleibt offen.

## Docker und Betrieb

`docker compose up --build` baut das Frontend und liefert den Katalog mit aus;
Compose bindet den Katalog zusätzlich separat nur lesend ein. Docker wurde in
der aktuellen lokalen Abnahme nicht ausgeführt. Individuelle Deployments müssen
den Referenzkatalog ebenfalls mitliefern.

Aktuell: ein Prozess, SQLite und gemeinsame Provider-Limiter. HTTPS, kontrollierter
Reverse Proxy, Betriebsbackups, geeignete Provider und weitere Konten-/Betriebs-
funktionen sind vor öffentlichem Betrieb zu ergänzen: [SECURITY](docs/SECURITY.md).
Das private GitHub-Repository ist als `origin` eingerichtet. GitHub Actions prüft
Pushes und Pull Requests. Squash-Merge und automatisches Löschen gemergter
Arbeitsbranches sind konfiguriert. Serverseitiger Branchschutz ist noch nicht
aktiv: GitHub verlangt dafür beim privaten Repository ein Pro-Upgrade. Lokale
Hooks und verbindliche Reviewregeln gelten weiterhin; sie ersetzen diesen Schutz
nicht. Details: [BRANCHING](docs/BRANCHING.md).

## Dokumentation

- [GOAL](docs/GOAL.md) und [UI DESIGN](<docs/UI DESIGN.md>): Vision und UI-First-Reihenfolge.
- [PRODUCT](docs/PRODUCT.md), [TARGET](docs/TARGET.md), [MILESTONES](docs/MILESTONES.md): Umfang und Abnahme.
- [ARCHITECTURE](docs/ARCHITECTURE.md), [DOMAIN_MODEL](docs/DOMAIN_MODEL.md), [API](docs/API.md): technische Verträge.
- [TESTING](docs/TESTING.md), [QUALITY_REPORT](QUALITY_REPORT.md): Prüfungen und Grenzen.
- [MAP_PROVIDERS](docs/MAP_PROVIDERS.md), [DATA_SOURCES](docs/DATA_SOURCES.md): externe Daten.
- [BRANCHING](docs/BRANCHING.md), [CHANGELOG](CHANGELOG.md): Zusammenarbeit und Änderungen.
