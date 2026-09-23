# Qualitätsbericht: Dokumentation und Fahrzeugassets

Stand: 23.09.2026. Umfang: `refactor/docs-and-vehicle-assets` gegenüber main
(f82cd51, nach PR #9). Lokale Umgebung: Windows, Python 3.11.9, Node 24,
Microsoft Edge. Frühere Persistenz-Reproduktionen bleiben in PR #9 und der
Git-Historie nachvollziehbar; dieser Bericht beschreibt den aktuellen Change.

## Änderungen und Erhaltungsnachweise

- Unabhängige Inventur vor der Umordnung: 134 SVGs, 14 Katalogmodelle,
  42 tatsächlich verwendete Karten-/Front-/Seitenbilder und 92 weitere Dateien.
  Altpfad, Modell, Rolle, Zielpfad und SHA-256 bleiben versioniert erhalten.
- Alle 134 Dateien bytegleich verschoben. Keine Variante gelöscht, kombiniert
  oder neu gerendert; keine Datenbank oder Katalog-Bildmetadaten geändert.
- Eine unveränderliche Modellzuordnung ersetzt zwei Pfadtabellen. Keine
  Pfadkopien, Weiterleitungs- oder Kompatibilitätsschicht eingeführt.
- Ein bereits falscher DAF-Frontbild-Hash im alten Teilmanifest wurde mit der
  unabhängig erfassten Datei abgeglichen. Die alte Angabe bleibt als historische
  Notiz erhalten; die SVG selbst ist unverändert.
- Hauptdokumente unterscheiden Ist-Stand, Vision und offene Abnahme. Korrigiert
  sind Modellanzahl, Grafikpriorität, lazy Markt und relationale Traffic-Leser.
  Die abgeschlossene Umbauchronik ist ausdrücklich historisch archiviert.

## Ausgeführte Werkzeugprüfungen

| Prüfung | Tatsächliches Ergebnis |
| --- | --- |
| `python scripts/quality.py` | Vollständig bestanden, Exit 0 |
| Ruff / Format | Bestanden, 129 Dateien |
| mypy einschließlich Offline-CLIs | 84 Quelldateien, keine Fehler |
| Pyright | 0 Fehler, 0 Warnungen |
| Python-Verhalten, API, Architektur und Manifest | 278 Tests bestanden |
| Core-Statement-Coverage | 100 %, 3.087 Statements, 0 fehlend |
| Frontend-Verhalten und Architektur | 57 Tests bestanden |
| ESLint, Stylelint, Prettier, checkJs | Bestanden |
| Vite-Produktionsbuild / compileall | Bestanden |
| Browserregression | Alle 11 vorhandenen Szenarien bestanden, Edge, 1,6 Minuten |
| Asset-Inventar | Alle 134 Zielpfade und SHA-256 stimmen; 42 Bildauswahlen unverändert |
| Statische HTTP-Auslieferung | Alle 42 verwendeten SVGs: 200, SVG-MIME und unveränderter Hash; alte/fehlende Pfade: 404 |
| Vite-Entwicklungsproxy | 42 SVG-Pfade einschließlich MIME/Hash und fehlender Pfad geprüft |
| Dokumentationslinks / Git-Diff | Lokale Dateilinks geprüft; keine fehlenden Ziele oder Whitespacefehler |

Neue Python-Core-Funktionen wurden nicht eingeführt; das bestehende Manifest
ist unverändert und wurde vollständig geprüft. Der Resolver besitzt eigene
Gegentests für fehlende/unbekannte IDs, Prototype-Namen und Mutationsversuche.
Python meldet zwei bestehende DeprecationWarnings aus Testabhängigkeiten.

Lokale Nachweise: `artifacts/assets-final-quality.log`,
`artifacts/assets-after-browser.log`, `artifacts/assets-http.log`,
`artifacts/assets-vite-proxy.log`, `artifacts/assets-doc-links.log` und die
Vorher-/Nachher-Aufnahmen unter `artifacts/assets-before` / `assets-after`.
Der Integrationsnachweis entsteht gesondert durch die GitHub-Checks des PRs;
dieser Abschnitt dokumentiert ausschließlich tatsächlich lokale Prüfläufe.

## Visuelles und manuelles Review

Feste Testdaten und lokale Tiles sichern vergleichbare Flotten-/Shopansichten
bei 1440 × 900 und 390 × 844. Alle vier Ansichten wurden visuell geprüft.
Drei Screenshotdateien sind byteidentisch; beim mobilen Shop liegen die
1.166 abweichenden Pixel ausschließlich in der unteren Navigation
(x=110–214, y=781–820), außerhalb der Fahrzeugbilder. Bildflächen sind gleich.
Die Auftragsansicht mit Karte wurde ebenfalls visuell geprüft. Bestehende
Browserfälle prüfen Polling, Panelwechsel, mehrere Transporte, Wiederanmeldung,
Offline-Abrechnung, Fehlerzustände, Bildstabilität und getrennte Testprofile.

Manuelles Änderungsreview: Der Resolver hat ausschließlich die Aufgabe der
Modell-/Pfadauflösung. Views behalten die Bildauswahl; Kartenmodul und Registry
behalten Farbmaske, Orientierung, Rasterisierung, Cache und Cleanup. Keine
neuen Ressourcen, Dienste oder Adapter. Das Backend ist unverändert; SQL-,
Domain- und API-Grenzen werden durch diese Umordnung nicht erweitert.

README, GOAL, UI DESIGN, Produkt, Zielstand, Meilensteine, Architektur, Domain,
Persistenz, API, WorldCatalogue, Datenquellen und Tests wurden gegen die aktive
Implementierung abgeglichen. Quellen-/Lizenzangaben bleiben erhalten; Regeln
für neue Grafiken stehen im Asset-Manifest. M1 bleibt in Arbeit.

## Grenzen und Auslieferung

- Dockerfile-COPY, .dockerignore und Asset-Mount wurden geprüft. Ein tatsächlicher
  Docker-Build wurde mangels installiertem Docker nicht ausgeführt.
- Automatisierte Mobilansichten sind keine reale iPad-/Safari-Abnahme.
  Externe Routing- und Tile-Dienste sind im Browserlauf simuliert.
- Kein Spielserverneustart und keine Änderung an gespeicherten Profilen,
  Spielstanddatenbanken oder Referenzkatalogen durch diesen Change.
- Build und neuer Asset-Ordner müssen gemeinsam ausgeliefert werden. Bereits
  geöffnete Seiten benötigen danach einen Reload. Öffentlicher Produktionsbetrieb
  und vollständige MVP-Abnahme bleiben separate Aufgaben.
