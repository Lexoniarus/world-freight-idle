# Qualitätsbericht: Market v2

Stand: 25.09.2026. Lokale Umsetzung auf `feature/city-market-v2`, ausgehend
von main `75e3d8a`. Python 3.11.9, Node 24, Windows und Microsoft Edge.
Veröffentlichung und Merge sind nicht Teil dieser Umsetzung.

## Produkt und Daten

- Ausschließlich City-UID-Märkte eigener idle Fahrzeuge; keine Viewport- oder
  PayloadBand-Generierung. Alle geeigneten Origins der aktiven Stadt,
  katalogweite NHM-Ziele, getrennte Candidate-/Fahrzeuggewichtung.
- Facility-Coverage und mindestens drei Angebote je verfügbarem Band;
  Retention gültiger fahrbarer V2-Angebote, sechs Stunden Angebotslaufzeit.
- Quote/Dispatch verlangen ein Fahrzeug. Same-City-Reposition, Reservierung,
  Abbuchung, Transport, Offer-Verbrauch und Pruning committen atomar. Refill
  besitzt danach seine eigene Transaktion und kann den Dispatch nicht umkehren.
- World 4.2.0 und Vehicle 2.2.0 werden read-only validiert. Die bereitgestellte
  World-Datei wurde unverändert unter dem kanonischen Namen übernommen.
  Spielschema 1.1.0 und historische Snapshot-Hüllen bleiben unverändert.
- Alle bestehenden OwnedVehicles im lokalen Spielstand wurden read-only
  geprüft: keine fehlenden oder unauflösbaren model_id, keine fehlenden
  Standort-Snapshots. Keine Heuristik und keine Bestandsmigration notwendig.
  Eine konkrete Fahrzeuganzahl ist ausdrücklich kein Architekturvertrag.
- Alle vorhandenen offenen Offers und historischen Transport-Snapshots wurden
  zusätzlich read-only mit den neuen Mappern gelesen: ohne Fehler oder Writes.
  Beide Referenzdateien stimmen nach den Tests mit den eingeführten Git-Blobs
  überein; die Tests haben ihre Inhalte nicht verändert.

## Ausgeführte Prüfungen

`python scripts/quality.py` wurde mit dem Projektinterpreter vollständig
und mit Exitcode 0 ausgeführt. `npm run test:e2e` wurde auf demselben
unveränderten Code-Stand mit Exitcode 0 ausgeführt.

| Prüfung | Tatsächliches Ergebnis |
| --- | --- |
| Python einschließlich Manifest und Architekturtests | 354 bestanden |
| app-Statement-Coverage | 3.852 Statements, 0 ungedeckt, 100 % |
| Ruff und Format (79 Zeichen) | bestanden |
| mypy / Pyright | 97 Quelldateien fehlerfrei / 0 Fehler |
| Frontend-Verhalten | 61 bestanden |
| ESLint, Stylelint, Prettier, checkJs | bestanden |
| Vite-Produktionsbuild und compileall | bestanden |
| Playwright | 14 bestanden, Desktop/Mobil/Reduced Motion |
| git diff --check | bestanden |

Gezielte Gegenproben prüfen getrennte Auswahl, Retention, Historien und Import,
Dispatch-Rollback sowie einen Refill-Schreibfehler nach nachweislichem Commit.
Eine zweite SQLite-Verbindung beobachtet den gestarteten Transport, bevor
der Refill beginnt. Ein späterer Refresh bestätigt unveränderten Transport
und nur einmalige Abbuchung. Katalogausfälle und ungeklärte Altmodelle besitzen
explizite HTTP-Fehlerübersetzung ohne interne Pfade. Pan/Zoom erzeugt im
Browsertest keine Marktanfragen; entfernte Offers und verspätete Antworten
werden verworfen. Tests wurden weder übersprungen noch von Coverage ausgenommen.

Die Desktop-Angebotskarten, mobilen Angebotsdetails, Quote, Flotte und
Energieansicht wurden zusätzlich anhand der erzeugten Screenshots visuell
geprüft. Kein horizontaler Overflow; Karte, Attribution und Navigation bleiben
zugänglich. Lange NHM-Bezeichnungen brechen innerhalb der scrollbaren Panels um.

Lokale, nicht versionierte Protokolle: `artifacts-quality-final.log`,
`artifacts-e2e-final.log` und `artifacts-readonly-audit.log`. Screenshots liegen
im temporären Verzeichnis unter `world-freight-market-v2-desktop.png`,
`world-freight-market-v2-mobile.png` und den bestehenden Regressionstiteln.
Zwei vorhandene Starlette/httpx-/AnyIO-Deprecation-Warnungen bleiben ohne
Testfehler. Frühere fehlgeschlagene Zwischenläufe sind durch diese vollständigen
Läufe auf dem korrigierten Stand ersetzt.

## Architekturreview

81 neue oder wesentlich geänderte konkrete öffentliche/private Core-Callables
wurden einzeln geprüft: Zweck, Schicht, Abhängigkeiten und Seiteneffekte.
Die vollständige Einzelaufstellung steht in
[MARKET_V2_REVIEW.md](docs/MARKET_V2_REVIEW.md).

Domainwerte sind immutable; OwnedVehicle schützt eigene Zustandsübergänge.
Scope, NHM-Relation, Candidate-Kompatibilität, Coverage, Materialisierung und
Markttransaktion sind getrennte Bausteine. Services erhalten Ports statt SQL-
Verbindungen. MarketGenerator orchestriert ausschließlich. Gemeinsame reine
Kompatibilitätsfunktionen verbinden Candidate, Retention, Quote und Dispatch.
Views nutzen serverseitige Eignungs-IDs. Das explizite Function-Test-Manifest
bleibt Teil des ausführbaren Gates; Zeilenzahl und Coverage ersetzen das Review
nicht. Keine offene Vermischung von Core-Verantwortlichkeiten festgestellt.

## Datenbedingte Coverage-Grenzen

Der gelieferte Referenzstand enthält 559 routbare Facilities in 333 Städten,
284 Unternehmen, 95 verifizierte und 464 ausdrücklich geschätzte Positionen.
Diese Zahlen beschreiben Datenqualität, keine vorgeschriebene Marktgröße.
Eine reale Datenlücke bleibt: Campari Group Sesto San Giovanni Headquarters
besitzt kein ausgehendes NHM-Profil und erhält deshalb keine erfundenen
Origin-Angebote. Für jede operative Transportklasse existiert im ausgelieferten
Fahrzeugkatalog mindestens eine positive Capability; die konkrete Flotte muss
dennoch zur jeweiligen Ware passen.

Der read-only Bestandsaudit prüfte die tatsächlich aktive Stadt Palermo:
1.127 kompatible Candidates, zwei geeignete Origin-Facilities und keine
fehlenden Distanzbänder. Die Berliner Starterflotte deckt ebenfalls alle drei
Bands ab. Das ist keine Zusage vollständiger Coverage für jede mögliche
Stadt-/Flottenkombination: fehlende NHM-Relationen, Fähigkeiten, positive
Scale-Suitability oder Distance-Weights können Bands ausschließen. Solche
Lücken werden als unmet_bands protokolliert und nicht mit erfundenen Angeboten
gefüllt. Fixtures prüfen explizit leere und nur teilweise verfügbare Bands.
Die Generierung berechnet keine globalen Origin-Relationen.

## Grenzen der Abnahme

Browserprüfungen nutzen isolierte Testspielstände, Mock-Routing und lokale
Kacheln. Sie ersetzen weder eine reale iPad-/Safari-Abnahme noch einen
Live-Valhalla-Test. Kein Docker-Build, Deployment, Push oder Merge durchgeführt.
Spieler-DBs, Backups, Screenshots und Prüfprotokolle werden nicht versioniert.
Die bestehende Energie- und historische Transportlogik bleibt abgedeckt.
