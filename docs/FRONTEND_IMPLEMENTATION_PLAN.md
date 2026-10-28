# Schrittweiser Frontend-Umsetzungsplan

Stand: 28.10.2026. Grundlage ist das bestätigte
[Frontend-Gesamtkonzept](FRONTEND_CONCEPT.md). Der Plan gehört zum Refactor-Plan
und wurde auf ausdrücklichen Wunsch auf `refactor/local-market-pool` dokumentiert.
Die Schritte 1–6 sind **geplant, nicht implementiert oder abgenommen**.

## 0. Dokumentierter Ausgangspunkt

Die Bestandsprüfung erfolgte am Refactor-Stand `8bc7246`:

- Native ES-Module mit `frontend/bootstrap.js` als Composition Root.
- `GameState`, API-Client, Controller, reine Views und Kartendarstellung haben
  getrennte Zuständigkeiten. Navigation erhält die bestehende Karteninstanz.
- HUD, Navigationsleiste, Kontextpanels, Verwaltungsansichten und Firmenfarben
  sind vorhanden. Ihr heutiges Erscheinungsbild ist noch nicht das neue Zielbild.
- `map/provider.js` liefert derzeit OSM-Rasterkacheln. Die Vektorgebäude und
  Höhendaten der getrennten Vorschau sind noch nicht Teil dieses Providers.
- Die Asset-Zuordnung besitzt Front-, Seiten- und Kartenansichten. Der
  Fahrzeugrenderer berücksichtigt bereits Farbe, Animation und Gruppierung.
- Die Unternehmensansicht enthält bestehende Statistik und Einstellungen.
  Ein eigenständiges Spielerunternehmen, eigene Depots, Mitarbeiter und deren
  Fortschritt sind davon getrennte, noch auszubauende Spielfunktionen.

Das Interview und die offenen Fragen sind nun dokumentiert. Es wurden dafür
keine Frontend-, Backend-, Asset- oder Datenänderungen vorgenommen.

## Gemeinsame Arbeits- und Abnahmegrenzen

- Kleine, zusammenhängende Schnitte in den vorhandenen Modulen; kein zweiter
  produktiver Frontendpfad neben der eigentlichen Anwendung.
- Vorschaucode und Demonstrationswerte sind keine Implementierungsbasis.
  Vorhandene echte Daten und Aktionen bleiben maßgeblich.
- Marktregeln, Routing, Quote, Dispatch, Persistenz und öffentliche/private
  Daten ändern sich nicht durch eine reine Darstellungsänderung.
- Views führen keine Requests aus; Spiel-HTTP bleibt in `frontend/api.js`.
  Kartenkacheln und Fahrzeugassets behalten ihre jeweiligen Ladegrenzen.
- Zustandskomponenten besitzen und beenden Listener, Timer und Requests.
  Polling erhält Auswahl, Fokus, Bildknoten und Kartenkamera.
- Vorhandene Tastatur-, Touch-, Mobil- und Reduced-Motion-Bedienung wird erhalten.
- Pro Schnitt werden Verhalten und betroffene Architekturgrenzen geprüft und
  das tatsächliche Ergebnis im Browser beurteilt. Vor Integration gelten das
  gemeinsame Quality Gate, Browserregression und Architektur-/Dokureview.
- Offene Konzeptfragen F01–F11 müssen vor dem betroffenen Schnitt entschieden
  werden. Sie blockieren nicht pauschal die Dokumentation oder jeden früheren
  Schritt. Eine Klärung wird als Entscheidung nachgetragen.

## 1. Echter Spielrahmen und Designsystem

**Grundlage:** `frontend/views/shell.js`, `frontend/style.css`,
`frontend/ui/illustrations.js`, `frontend/controllers/game-sync.js`,
`frontend/navigation.js` und bestehende Firmenpräferenzen.

**Arbeit:**

1. Die bestätigte Rahmen-, Icon-, Reiter- und Farbgestaltung als konsistente
   Regeln und CSS-Tokens auf den echten Spielrahmen übertragen.
2. Die bestehende Navigation vollständig erhalten und in die neue Gestaltung
   einordnen. Ein Vorschau-Menü darf produktive Bereiche nicht verschwinden lassen.
3. Kontostand, laufende Transporte, freie Fahrzeuge und Meldungen kompakt
   darstellen. `player.cash`, `active_transports`, `idle_vehicles` und vorhandene
   Ereignisse liefern die Daten; keine Beispielzähler aus der Vorschau.
4. Verfügbare Firmenfarbe einbeziehen. Noch fehlende Firmen-/Logo-Daten werden
   nicht durch eine zweite Identität im UI ersetzt.

**Abnahme:** Ein zusammenhängender echter Spielbildschirm zeigt die bestätigte
Gestaltung mit realen Zuständen, einschließlich Lade-, Leer-, Fehler- und
Verbindungszuständen. Bestehende Navigation und mobile Bedienung funktionieren.
Karte und Wirtschaftsregeln sind in diesem Schnitt unverändert.

**Vorher klären:** F02/F03 zu Produktassets, Schriften und Farbrollen;
F04 soweit die erste responsive Navigation betroffen ist.

## 2. Verwaltungsansichten und gemeinsame Komponenten

**Grundlage:** `frontend/views/fleet.js`, `shop.js`, `contracts.js`,
`transports.js`, `company-dashboard.js`, `ranking.js`; `frontend/ui/data-table.js`,
`components.js`, `vehicle-image.js`; `frontend/panels.js` und
`frontend/controllers/panel-controller.js`.

**Arbeit:** Gemeinsam verwendete Listen, Filter, Aktionen, Rahmen und Reiter
angleichen. Kompakte Bild-/Porträtplätze und vergleichbare Kernwerte mit
anklickbaren Details vorsehen. Bestehende Fahrzeugbilder, Markt- und
Unternehmensdaten weiterverwenden. Größere Managementansichten samt direkter
Rückkehr zur Karte ausarbeiten; Büro-/Akten-/PC-Motive einheitlich einsetzen.

**Abnahme:** Reale Markt-, Kauf-, Flotten-, Transport- und Statistikabläufe
bleiben bedienbar. Auswahl, Filter, Fokus und Kamerakontext überleben Updates
und Navigation. Tabellen und Zahlen sind gut lesbar; keine Platzhalterdaten
für noch fehlende Mitarbeiter- oder Firmenfunktionen.

**Vorher klären:** F04 zur Flächen-/Navigationsaufteilung. Der unverändert
kanonische Assetbestand bleibt Grundlage des visuellen Reviews.

## 3. Kontextgebundene Fahrzeug-Informationsbubble

**Grundlage:** `frontend/map/world-map.js` und seine typisierten
`object-selected`-Ereignisse; `frontend/controllers/map-selection-controller.js`,
`frontend/map/selection.js`, Navigation, Zustands- und Action-Controller.
Eine eigene zustandsbehaftete UI-Komponente für die Bubble ist **vorgeschlagen**,
noch nicht als bestehendes Modul zu verstehen.

**Arbeit:** Die am Lkw verankerte Bubble mit Reitern Fahrer/Fahrzeug/Auftrag
umsetzen. Die UI-Komponente erhält Daten und Aktionseinbindungen aus den
vorhandenen Verantwortlichen; `WorldMap` wird nicht zur Verwaltungszentrale.
Passende Links und Zustandsaktionen verwenden. Animationstakte lösen keine
eigenen fachlichen HTTP-Reads aus.

**Abnahme:** Fahrzeug-/Transportinformationen und Verweise sind korrekt;
Bewegung, Auswahlwechsel und Schließen räumen den Zustand sauber auf.
Ein aktiver Transport bekommt keine unpassende Auftragssuche. Fahrerinformationen
und Fahrerzuweisung werden erst an das echte Mitarbeitermodell gebunden.

**Vorher klären:** F07, insbesondere Feldumfang und Verhalten am Kartenrand
beziehungsweise auf kleinen Bildschirmen.

## 4. Kartenfundament, Heightmap und Materialien

**Grundlage:** `frontend/map/provider.js`, `world-map.js`, `camera.js`,
`layers.js`, `overlay-data.js`, `frontend/layer-presets.js` und
`frontend/controllers/layer-state-controller.js`.

**Reihenfolge innerhalb dieses Schritts:**

1. Vektor- und Höhenquellen samt Nutzung, Abdeckung, Cache- und Fehlerverhalten
   entscheiden und an der Providergrenze anbinden.
2. Reale Vektorgeometrien und einfache 3D-Gebäude integrieren; Auswahl,
   Routen, Presets und Account-Präferenzen weiter erhalten.
3. Gelände aus Höhendaten/Heightmap integrieren. Straße, Gebäude, Fahrzeug
   und Auswahl-/Informationsdarstellung erhalten eine gemeinsame Höhenbasis.
4. Erst auf dieser Basis den generischen Materialbaukasten für Gebäude,
   Dachflächen, Grün, Asphalt und Pflaster produktiv anbinden. Verlässliche
   Datenklassen nutzen und neutrale Fallback-Gestaltung festlegen.
5. Detailgröße, Texturfilterung und Übergänge über die Zoomstufen abstimmen.

**Abnahme:** Tatsächliche Geografie und vorhandene Spielobjekte bleiben korrekt.
Eine geeignete Region mit erkennbarem Relief belegt die Heightmap, ein flacher
Berliner Ausschnitt allein reicht dafür nicht. Es gibt keine doppelten
Gebäudeoberflächen, erfundenen Gebäudeklassen oder schwebenden Kartenobjekte.
Materialien treten aus der Entfernung zurück und werden in der Nähe detaillierter.
Verwendete Quellen, Attribution, Kosten- und Fehlerverhalten sind dokumentiert.

**Vorher klären:** F09/F10. Eine farbige Daten-Heatmap ist kein Bestandteil
der hier bestätigten Heightmap-Anforderung.

## 5. Räumliche Darstellung eines Fahrzeugs, danach weitere Modelle

**Grundlage:** `frontend/vehicle-assets.js`, `vehicle-color-assets.js`,
`vehicle-paint.js`, `frontend/map/vehicle-assets.js`, `vehicle-animator.js`,
`vehicle-footprint.js`, `vehicle-groups.js` und die vorhandenen Modellassets.

**Arbeit:** Zuerst ein Modell mit vereinfachter räumlicher Form und vorhandenen
Ansichten sauber aufbauen. Texturübergänge, fehlende Ansichten und Firmenfarbe
polieren; Darstellungsdaten pro Modell von Bewegung und Spiellogik trennen.
Trefferflächen, Gruppierung und Auswahl an die sichtbare räumliche Ausdehnung
über Zoom, Neigung und Drehung anpassen. Erst nach Abnahme auf weitere Modelle
ausrollen; die vorhandenen Fahrzeugbilder nicht pauschal neu gestalten.

**Abnahme:** Echte Route, Position und Bewegungsrichtung stimmen. Geometrie
steht auf dem Gelände, Ansichten und Lackierung passen zusammen, Auswahl und
Überlappungsgruppierung bleiben nachvollziehbar. Leistung und Ressourcenabbau
sind im tatsächlichen Kartenbetrieb geprüft. Der ursprüngliche Testentwurf
ist ein Richtungsnachweis, kein fertiges produktives Modell.

**Vorher klären:** F11 und die Renderer-/Assetentscheidung im Architekturreview.

## 6. Firma, Zentrale, Depots und Mitarbeiter als echte Spielfunktionen

**Grundlage:** Bestehende Unternehmensansicht/Analytics und die geplanten
Grenzen für `PlayerCompany`, Depots und Beschäftigungsverhältnisse.
Die auf dem Refactor-Branch vorbereitete Dispatch-Freigabe ist bei der
Mitarbeiterintegration zu berücksichtigen.

**Arbeit:** Firmenbesitz und Depotzuordnung fachlich umsetzen; daran das
sichtbare Wachstum der Zentrale und anschließend Mitarbeiterverwaltung,
Eigenschaften, Entwicklung, feste Porträts, Ränge und Abzeichen anbinden.
Marktangebot und personelle Dispatch-Freigabe behalten getrennte Aufgaben.

**Abnahme:** Die Oberfläche verwendet persistente, autorisierte Spielzustände.
Öffentliche Referenzunternehmen und Facilities werden nicht zu eigenen Firmen
oder Depots umgedeutet. Mitarbeiterregeln werden im Core umgesetzt und geprüft,
nicht nur als deaktivierte oder scheinbar wirksame UI-Schaltflächen dargestellt.

**Vorher klären:** F01/F05/F06, einschließlich ihrer Milestone-Zuordnung.
Die Entscheidung, Mitarbeiter früh erleben zu wollen, ist keine stillschweigende
Abnahme eines bereits vorhandenen Mitarbeitersystems.

## Meldungen, Animation und Audio im Ablauf

Das sichtbare Meldungsgrundsystem gehört zu Schritt 1. Absenderporträts werden
bei den betroffenen Ansichten ergänzt, sobald ihre Daten und Assets feststehen.
Dezente Übergänge sowie abschaltbare Musik, Umgebung und Aktionsgeräusche
werden als eigene kleine Schnitte an echte Ereignisse angeschlossen.
F08 wird vor diesen Schnitten geklärt; eine Audioimplementierung ist keine
Voraussetzung dafür, zuerst den echten Spielrahmen fertigzustellen.

## Nächster Umsetzungsschnitt

Nach den für Schritt 1 nötigen Entscheidungen beginnt die Arbeit am echten
Spielrahmen und HUD. Die bestehende Karte bleibt dabei zunächst erhalten.
Weitere isolierte Stadt-/Texturbeispiele ersetzen diesen Schritt nicht.
Diese Dokumentationsänderung selbst enthält keinen Frontend-Ausbau.
