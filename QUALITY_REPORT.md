# Qualitätsbericht: Drei Persistenz-Review-Fixes

Stand: 23.09.2026. Umfang: `fix/domain-persistence-review` gegenüber
`main` nach PR #8. Umgebung: Windows, Python 3.11.9, Node 24, Microsoft Edge.
Dieser Bericht ersetzt die frühere pauschale Abschlussbewertung. Historische
Refactor- und Migrationsnachweise bleiben in PR #8 und der Git-Historie erhalten.

## Reproduzierte und reparierte Befunde

1. Ein Dashboard-Aufruf deserialisierte bei 100 abgeschlossenen Transporten
   200 Transportdatensätze innerhalb von Schreibtransaktionen. Repository-Abfragen
   filtern jetzt Besitzer, aktiven Status und Fälligkeit vor der Deserialisierung.
   Der Regressionstest bestätigt null geladene Transporte bei reiner Historie.
2. Die Startprüfung akzeptierte einen gewöhnlichen Index mit dem Namen des
   erforderlichen Unique-Index. Sie vergleicht jetzt Primär-/Fremdschlüssel und
   tatsächliche Guard-Definitionen. Manipulierte Indizes/Trigger werden abgewiesen;
   Formatierung darf variieren, Literalinhalte werden nicht verändert.
3. Unbekannte Unternehmensfelder wurden beim Offline-Import verworfen.
   Verschachtelte Firmen, Quellen, Waren, NHM-Profile und GeoJSON werden nun vor
   dem Mapping geprüft. Beide Importmodi brechen mit einem sicheren Feldpfad ab;
   unbekannte Feldwerte erscheinen nicht in Diagnosen. Bekannte optionale
   Metadaten werden bewahrt. Widersprüchliche Stadt-/Standortangaben werden
   zurückgewiesen, statt sie still durch Referenzwerte zu ersetzen.

## Ausgeführte Werkzeugprüfungen

| Prüfung | Tatsächliches Ergebnis |
| --- | --- |
| `python scripts/quality.py` | Vollständig bestanden, Exit 0 |
| Ruff / Format | Bestanden, 129 Dateien |
| mypy einschließlich Pflege-/Import-CLIs | 84 Quelldateien, keine Fehler |
| Pyright | 0 Fehler, 0 Warnungen |
| Python-Verhalten, API, Architektur und Manifest | 277 Tests bestanden |
| Core-Statement-Coverage | 100 %, 3.087 Statements, 0 fehlend |
| Frontend-Verhalten und Architektur | 54 Tests bestanden |
| ESLint, Stylelint, Prettier, checkJs | Bestanden |
| Vite-Produktionsbuild / compileall | Bestanden |
| Browserregression | 10 Szenarien bestanden, Edge, 1,9 Minuten |
| Git-Diff-Whitespace | Keine Fehler |

Lokale Nachweise: `artifacts/review-final-quality.log`,
`artifacts/review-e2e.log`, `artifacts/review-transport-tests.log`,
`artifacts/review-schema-tests.log` und `artifacts/review-order-repro.log`.

Der erste Gesamtlauf deckte zusätzlich eine Abhängigkeit der neuen Log-Tests
vom zuvor gesetzten Log-Level und einen nicht mehr erreichten Gegenfall der
Importprüfung auf. Die Log-Tests setzen ihren Capture-Level nun ausdrücklich;
ein eigener Korruptionsfall prüft den Abfahrtsort aktiver Transporte nach der
Validierung beider Standortprojektionen. Der anschließende gezielte Lauf mit
vorgeschalteten API-Tests bestand alle 26 Tests.

Die Coverage-Aussage gilt für Statements, nicht für vollständige Branch- oder
Pfadabdeckung. Die zwei bekannten Testclient-Deprecation-Warnungen wurden nicht
unterdrückt.

## Manuelles Architektur- und Dokumentationsreview

- SQL und Deserialisierung bleiben im vorhandenen SQLite-Repository.
  Services benutzen typisierte aktive/fällige Abfragen; der bisherige private
  Durchreicher für aktive Transporte ist entfernt. Vollständige Inventare bleiben
  für explizite Offline-Abgleiche beziehungsweise Profilpflege verfügbar.
- Settlement bleibt atomar. Der bestehende Ankunftsindex wird im Regressionstest
  über den Query-Plan nachgewiesen. Historische Datensätze werden nicht gelöscht.
- Schema-Vergleich und Ressourcenbesitz bleiben im SQLite-Adapter. Die temporäre
  In-Memory-Referenz verwendet die vorhandene Schema-Definition und wird auch bei
  Ablehnung geschlossen. Bestehende Dateien werden nicht automatisch repariert.
- Importvalidierung und Mapping bleiben im Offline-Repository. Kleine benannte
  Funktionen prüfen Quellen, Waren, Arrays und Geometrien. Es gibt keine neue
  Laufzeitschicht, keinen zweiten Mapper und kein Validierungsframework.
- Neue Core-Funktionen besitzen Verhaltenstests, Gegenfälle und Manifest-Einträge.
  Architektur-, Testdokumentation und Changelog beschreiben den geänderten Stand.

Für diese drei Befunde bestehen nach dem inhaltlichen Review keine weiteren
wesentlichen offenen Punkte. Dies ist das Review des implementierenden Agenten,
keine unabhängige externe Architekturfreigabe und keine globale Fehlerfreiheit.

## Browserprüfung und Grenzen

Alle zehn vorhandenen Playwright-Szenarien bestanden unter Edge in 1,9 Minuten.
Sie prüfen unter anderem Registrierung/Anmeldung, Kauf, parallele Transporte,
Offline-Ankunft, getrennte Profile, Rangliste, Mehrspielerkarte, Bildstabilität,
Deep Links, Fehlerfälle, Fokus und mobile Panels. Desktop 1440 × 900 und Mobil
390 × 844 wurden automatisiert geprüft; aktuelle Desktop-/Mobil-Screenshots
wurden zusätzlich visuell angesehen. Keine neue Layoutregression festgestellt.

Die Tests verwenden separate temporäre Datenbanken, Mock-Routing und lokale
Tiles. Es gab keine erneute Profilmigration und keinen Schreibzugriff dieses
Fixablaufs auf die aktive game.db, Profile oder Backups. Der bestehende Server
auf Port 8000 wurde nicht neu gestartet. API-Verträge und Schema 1.0.0 bleiben
unverändert. Reale iPad-Abnahme, öffentliche Providerverfügbarkeit und Docker
wurden in diesem Fix nicht erneut geprüft. Integration nur nach grüner CI.
