# Frontend v2 – Map-First-Logistik-Tycoon

Stand: 25.09.2026. Dieser implementierte Stand hat Vorrang vor der unten
archivierten langfristigen Designvision. Keine neuen Depots, Satelliten,
Fahrzeugmodelle, Assets oder Spielregeln gehören zu diesem Ausbau.

> Map first, management second. Die reale Welt bleibt das zentrale Spielbrett.

## Gestaltung und Flächen

Graphit-/Marineflächen und helle Schrift schützen den operativen Kartenraum.
Barlow strukturiert Überschriften, Inter Bedienung und Zahlen; beide lokal.
Zentrale CSS-Tokens unterscheiden Surface, Raised, Overlay, Texte, Accent,
Selection, Success, Warning, Danger, Information und Kartenrollen. Bernstein
kennzeichnet Hauptaktionen. Kartenobjekte verwenden eigene kontrastreiche
Farben, Konturen, Größen, Count-Badges und einen violetten Auswahlhalo.
Status ist zusätzlich beschriftet. OSM bleibt unverändert die reale Basiskarte.

Das kompakte HUD zeigt Kapital, Reputation, Flottenzahl und aktuelle Stadt.
Navigation: Weltkarte, Aufträge, Flotte, Fahrzeugshop, Transporte, Unternehmen,
Rangliste. Der Shop ist ein Flotten-Unterbereich. Rechts öffnet ein `context`-
Drawer (420 px); `management` erweitert bis min(760 px, 60 vw). Unternehmen
startet erweitert. Der Benutzer kann die Breite umschalten. Navigation
verwendet dieselbe MapLibre-Instanz und erhält die Kamera.

Mobil gibt es kompakte, halbe und volle Sheets. Der Griff ist per Klick,
Tastatur oder Ziehen bedienbar. Volle Sheets sperren die Karte mit `inert`
und Pointer-Schutz. Escape schließt Overlays, Rückkehrfokus bleibt erhalten.
Die zusätzliche Navigation liegt unter „Mehr“. Reduced Motion unterdrückt
Übergangsanimationen und verringert Kartenaktualisierungen.

## City Context und Disposition

`CityContextController` verwendet ausschließlich `city_uid`, nie Stadtnamen.
Explizite URL-/Benutzerauswahl einschließlich „Alle Städte“ bleibt beim Polling
erhalten. Eine bekannte Stadt ohne idle Fahrzeug ist weiterhin auswählbar,
besitzt dadurch aber keinen aktiven Markt. Automatische Defaults sind nach UID
deterministisch. Links verwenden `?city=...&vehicle=...`; Browser-Zurück stellt
beides wieder her. Legacy-`hub` wird aus Fahrzeug-, Contract-, dann Transport-
Snapshots oder einem authentifizierten Exact-Lookup aufgelöst. `city` gewinnt.
Nicht auflösbare Links erklären den Fehler und zeigen alle Städte.

Bewusste Stadtwechsel und „Aktuelle Stadt“ rahmen bekannte relevante Positionen.
Polling verschiebt die Kamera nicht. Pan/Zoom erzeugt keine Marktrequests.
Marktlisten und ausgewählte Details besitzen getrennte Zustände und Request-
Invalidierung. Marktbestand ist vor dem ersten Read unbekannt; relevante
Flottenänderungen markieren ihn veraltet. Reads erfolgen bei Nutzung des
Markts/Auftragslayers, Refresh und Disposition. Eligibility stammt ausschließlich
aus `eligible_vehicle_ids`; Fahrzeugwechsel verwirft die fahrzeuggebundene Quote.

Der Markt filtert Stadt, Fahrzeug, Distanzband, Transportklasse, Ziel und Ware.
NHM-Namen bleiben vollständig zugänglich; Klassen erhalten deutsche Labels.
Cargo, konkrete Facility/Adresse und Wirtschaft sind getrennt. Warenwert ist
kein Transporterlös. Exakte Straßenstrecke und Ergebnis erscheinen erst nach
Quote. Visuelle Fahrzeugrows ergänzen eine tastaturbedienbare Auswahlliste.

Die Flotte gruppiert nach Stadt und stationierten, ausgehenden oder ankommenden
Fahrzeugen. Lokale Fahrten zählen innerhalb der Stadtgruppe einmal. Modell,
Status und Name sind filterbar. Front ist dominant bei idle Fahrzeugen und im
Shop, Side bei aktiven Transporten. Details kombinieren Front/Side. Vorhandene
Map-/Front-/Side-Dateien, Fallbacks, Spielerfarben und stabile Bildknoten bleiben.

## Layer und Kartenlesbarkeit

`layers.js` definiert Darstellung, `layer-presets.js` Ansichtsdefaults,
`LayerStateController` Nutzervorgaben. Welt betont Flotte/Standorte/Routen,
Aufträge idle Fahrzeuge/Aufträge/Preview, Flotte eigene Fahrzeuge/Routen,
Transporte laufende Fahrten, Unternehmen einen ruhigen Kartenmodus und
Rangliste den Mehrspielerverkehr. Shop verwendet Flotte.

Versionierte lokale Overrides gehören zu **`user.id` aus `/auth/me`** und dem
jeweiligen Preset, niemals zum Username. Accountwechsel lädt andere Vorgaben.
„Ansicht zurücksetzen“ löscht nur dieses Preset. Temporäre Auswahl/Preview
besitzt eigene Quellen und ändert weder Overrides noch ausgeblendete Layer.

Zentrale Zoom-Tiers: unter 7 Aggregate, 7 bis unter 12 kompakte Marker,
ab 12 Top-Down-Modellassets. `grouping.js` gruppiert in ca. 48 Bildschirm-Pixeln,
getrennt nach eigenen/fremden Fahrzeugen. Koordinaten bleiben real und World
Wrapping zählt Fahrzeuge nicht doppelt. Ausgewählte eigene Fahrzeuge bleiben
separat. Berechnung maximal viermal pro Sekunde (Reduced Motion: einmal),
unabhängig von Bewegungsframes; versteckte Karten pausieren Updates.
Gruppenklick zoomt bis 17, danach öffnet eine tastaturbedienbare Fahrzeugliste.
Auch ohne Gruppierung bleiben identische Treffer als Liste erreichbar.
„Objekte gruppieren“ ist eine lokale Account-Präferenz.

Aufträge aggregieren unter Zoom 7 nach Stadt, darüber nach Origin-Facility.
Ausgewählte Opportunities und Transportendpunkte besitzen separate Halos;
ausgewählte Routen bleiben unabhängig vom normalen Routenlayer sichtbar.
Facilities stammen aus vorhandenem relevantem Kontext, ohne globalen Download.

## Unternehmen

Die private Managementansicht zeigt aktuellen Unternehmensstatus sowie
belegte Finanzen, Transporte, Kilometer und Tonnen. 7/30/90/all und die Scopes
Unternehmen, historische Origin-Stadt, Fahrzeug-ID, Transportklasse und
Distanzband verwenden serverseitige Analytics. Kein historischer Model-Scope.
SVG-Zeitreihen besitzen beschriftete, unterschiedlich gestrichelte Linien,
Finanzen eine gemeinsame Euro-Skala. Leistung kennzeichnet relative Skalen.
Breakdowns besitzen Ergebnisbalken und Tabellen; jede Zeitreihe hat eine
Tabellenalternative. Lade-/Leer-/Fehlerzustände und Retry sind enthalten.

Importierter Fortschritt ist getrennt von belegter Historie. Laufende Fahrten
sind nur erwartete Ergebnisse. Historische Tageszuordnung ist `arrives_at` in
UTC, nicht der Zeitpunkt des späteren Logins. Details: [API](API.md),
[Architektur](ARCHITECTURE.md), [Tests](TESTING.md).

---

# Historische Designvision vor Frontend v2

> **Verbindliche Entscheidung 18.09.2026: UI First.** Zuerst wird der
> spielbare Frontend-Kern auf dem vorhandenen Backend umgesetzt.
> M1 nutzt MapLibre GL JS mit OSM-Standardkarte: reale Straßen, Orte,
> Gebäude und POIs, freies Pan/Zoom und horizontales World Wrapping.
> Die unten beschriebene Satellitenvision ist ein späterer Ausbau und
> keine M1-Voraussetzung. Ein BasemapProvider trennt Renderer und Quelle;
> später kann ein SatelliteTileProvider ergänzt werden.
> Implementiert: dunkelblauer/goldgelber Tycoon-HUD, lokale Barlow-/Inter-
> Schriften, Kontextpanels, mobile Sheets, eigene Routen-/Fahrzeug-/
> Standort-/Auftragslayer, Standort-Clustering und Registrierung/Login.
> Öffentliche Facilities stammen aus dem WorldCatalogue; Referenzunternehmen
> sind keine Spielerunternehmen. Eigene Depot-/Besitzquellen bleiben leer.
> OSM-POIs sind Karteninhalt, keine automatisch spielbaren Unternehmen.
> Siehe [Kartenarchitektur](adr/0004-map-first-interface.md),
> [Kartenprovider](MAP_PROVIDERS.md) und [Abnahme](TARGET.md).

### Technische Konsolidierung der UI-Basis

Die frühere gestalterische Bindung ist mit Frontend v2 aufgehoben. Views besitzen keine API-Abhängigkeiten;
Navigation und Panels erhalten die vorhandene Karteninstanz. Provider,
Overlay-Daten, Layerdarstellung, Kamera und Fahrzeuganimation sind getrennt.
Timer und Listener werden beim Beenden freigegeben, veraltete Antworten
verworfen und Fokus/Benutzerauswahl bei Aktualisierungen erhalten.
Sichere DOM-Ausgabe und Frontend-Gates gehören zur technischen Abnahme;
Satelliten, eigene Depots und Backend-Wirtschaftsausbau bleiben später.

## 42.1 Grundprinzip

Die Weltkarte ist nicht lediglich eine Visualisierung innerhalb von World Freight Idle.

**Die Weltkarte ist das primäre User Interface des Spiels.**

Nach dem Login soll der Spieler grundsätzlich auf seine reale Spielwelt blicken.

Die grundlegende Interaktion orientiert sich am Bediengefühl moderner Kartendienste:

* frei verschiebbare Karte
* horizontales World Wrapping
* stufenloses beziehungsweise flüssiges Zoomen
* Drag-and-Drop-Navigation
* Mausrad-/Touch-Zoom
* anklickbare Objekte
* kontextabhängige Overlays
* einblendbare Informationspanels

Die Oberfläche soll sich nicht wie eine klassische Management-Website mit einer zusätzlichen Karte anfühlen.

Sie soll sich wie eine **interaktive Logistikwelt mit Management-Funktionen** anfühlen.

---

# 43. Spätere Vision: Satellitenbilder als alternative Basiskarte

Nach M1 kann eine zusätzliche Kartenansicht echte Satelliten- beziehungsweise
Luftbilder verwenden. Für M1 ist die OSM-Standardkarte verbindlich.

Der Spieler sieht damit nicht nur abstrahierte Länderflächen oder schematische Straßen.

Er sieht die reale Umgebung:

* Städte
* Industriegebiete
* Häfen
* Flughäfen
* Autobahnkorridore
* Flüsse
* Gebirge
* Küsten
* Ballungsräume
* landwirtschaftliche Regionen

Dadurch erhält die geografische Position eines Unternehmens, Depots oder Fahrzeugs einen wesentlich stärkeren räumlichen Kontext.

Beispiel:

Ein Depot im Hamburger Hafen wird nicht lediglich als Punkt mit der Beschriftung „Hamburg“ dargestellt.

Der Spieler kann hineinzoomen und erkennt tatsächlich:

* Hafenbecken
* Containerterminals
* Straßen
* Industrieflächen
* Elbe
* umliegende Stadtstruktur

Die reale Welt selbst wird dadurch Teil der visuellen Identität des Spiels.

---

# 44. Map-first UI

Die Hauptansicht besteht grundsätzlich aus:

```text
┌──────────────────────────────────────────────────────────────┐
│ Company │ Cash │ Reputation │ Alerts │ Search │ Account     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                                                              │
│                 SATELLITE WORLD MAP                          │
│                                                              │
│       🚚                   🏭                                │
│                    🚆                                        │
│                                             🚢               │
│             📦                                                │
│                                                              │
│                                                              │
│                                  ┌────────────────────────┐  │
│                                  │ Context Panel          │  │
│                                  │                        │  │
│                                  │ Selected Vehicle       │  │
│                                  │ ETA                    │  │
│                                  │ Cargo                  │  │
│                                  └────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

Die Karte bleibt möglichst permanent sichtbar.

Management-Funktionen erscheinen darüber beziehungsweise daneben als Panels, Drawers und Overlays.

---

# 45. Kein klassisches Seitenmodell als primäre UX

Die Anwendung besitzt weiterhin logische Produktbereiche wie:

* Aufträge
* Flotte
* Depots
* Unternehmen
* Transporte
* Markt
* Rankings

Diese müssen jedoch nicht zwangsläufig als vollständig getrennte Seiten funktionieren.

Die bevorzugte UX lautet:

**Map → Objekt auswählen → Kontext öffnen → Aktion durchführen → Map bleibt erhalten.**

Beispiel:

Der Spieler klickt auf einen Truck.

Daraufhin öffnet sich rechts:

```text
Volvo FH16
TRK-00271

Status
Unterwegs

Cargo
18.4 t Automotive Components

Berlin → Prague

ETA
03:42 h

[Transport öffnen]
[Route anzeigen]
```

Die Karte bleibt im Hintergrund vollständig interaktiv.

---

# 46. Kartenobjekte

Auf der Weltkarte können verschiedene Entitätstypen dargestellt werden.

## Eigene Fahrzeuge

Beispiele:

* 🚚 Truck
* 🚆 Train
* 🚢 Ship
* ✈ Cargo Aircraft

Die Icons bewegen sich während laufender Transporte sichtbar entlang ihrer tatsächlichen Route.

---

## Eigene Depots

Depots werden als permanente Besitzobjekte dargestellt.

Abhängig vom Zoom-Level können sie zusätzliche Informationen anzeigen:

* Kapazität
* freie Stellplätze
* dort stationierte Fahrzeuge
* Wartungsstatus

---

## Unternehmen

Relevante reale Firmenstandorte können als Points of Interest dargestellt werden.

Sie müssen jedoch abhängig vom Zoom-Level gefiltert beziehungsweise geclustert werden.

Die Karte darf nicht mit Millionen Markern überfüllt werden.

---

## Cargo Opportunities

Verfügbare Aufträge können geografisch sichtbar gemacht werden.

Beispiel:

```text
Berlin

📦 7 verfügbare Aufträge
```

Ein Klick beziehungsweise Zoom öffnet einzelne Opportunities.

---

## Infrastruktur

Später darstellbar:

* Häfen
* Cargo Airports
* Bahnhöfe
* Güterterminals
* Containerterminals
* Grenzübergänge
* Service-Center

---

# 47. Zoom-Level-of-Detail

Die Darstellung verändert sich abhängig vom Zoom-Level.

## Weltansicht

Sichtbar:

* eigene globale Flotte
* große Depots
* zentrale Hubs
* aggregierte Transportströme

Nicht sichtbar:

* einzelne lokale Firmen
* lokale Straßen
* kleine Cargo-Aufträge

---

## Europa-/Landesansicht

Sichtbar:

* Depots
* Fahrzeuge
* wichtige Unternehmensstandorte
* größere Auftragscluster
* aktive Routen

---

## Regionalansicht

Sichtbar:

* einzelne Auftraggeber
* Empfänger
* Fahrzeuge
* Depotstandorte
* konkrete Routen

---

## Lokale Ansicht

Sichtbar:

* reale Straßen
* Industriegebiete
* Betriebsstandorte
* detaillierte Fahrzeugpositionen
* einzelne Start-/Zielpunkte

Dieses Level-of-Detail-System ist notwendig für Performance und Übersichtlichkeit.

---

# 48. Echtzeitfahrzeuge auf der Satellitenkarte

Ein laufender Transport wird als bewegtes Objekt dargestellt.

Beispiel:

```text
Berlin
  ●━━━━━━━━━━━━🚚━━━━━━━━━━━━━━━━● Prague
```

Die sichtbare Position basiert nicht auf einem künstlichen Frontend-Timer.

Sie wird aus folgenden Daten rekonstruiert:

* gespeicherte reale Route
* tatsächliche Abfahrtszeit
* geplante beziehungsweise dynamisch berechnete Ankunftszeit
* aktueller Zeitpunkt
* optional Geschwindigkeitsprofil und Events

Damit ist der Zustand deterministisch.

Wenn der Spieler den Browser sechs Stunden schließt, wird beim erneuten Öffnen die aktuelle Position unmittelbar korrekt berechnet.

Danach wird die Bewegung wieder flüssig animiert.

---

# 49. Route Overlay

Bei Auswahl eines Fahrzeugs oder Auftrags wird die relevante Route über dem Satellitenbild dargestellt.

Beispiel:

```text
Origin ●━━━━━━━━━━━━━━━━━━● Destination
                    🚚
```

Zusätzlich können später unterschiedliche Routenzustände visualisiert werden:

* bereits gefahren
* verbleibend
* geplante Route
* Umleitung
* Störung
* Leerfahrt
* Cargo-Fahrt

Die eigentliche Routengeometrie stammt aus dem zuständigen RoutingProvider.

---

# 50. Satellitenbilder und Simulationsgeometrie sind getrennte Systeme

Die Satellitenkarte ist die Darstellungsebene.

Sie darf niemals als Grundlage für Simulationsberechnungen dienen.

Insbesondere werden niemals anhand von Bildschirm-Pixeln berechnet:

* Entfernung
* Geschwindigkeit
* Fahrzeugposition
* Fahrzeit
* wirtschaftliche Kosten

Stattdessen nutzt der Game-Core reale geografische Koordinaten und Routingdaten.

Architektur:

```text
                    GAME DOMAIN

Address
   ↓
Coordinates
   ↓
Routing Provider
   ↓
Real Route Geometry
   ↓
Distance / ETA / Route Progress
   ↓
Transport Simulation

                    ↓

                 MAP LAYER

Satellite Tile Provider
        +
Route Geometry
        +
Vehicle Position
        +
Depot Markers
        +
Company Markers
        +
Cargo Markers
```

Damit bleibt die Simulation unabhängig vom verwendeten Kartenanbieter.

---

# 51. Kartenprojektion

Für das primäre interaktive Interface wird eine für moderne Slippy-Maps geeignete Kartenprojektion verwendet.

Priorität besitzen:

* Satelliten-Tile-Kompatibilität
* flüssiges Zoomen
* horizontales Scrollen
* World Wrapping
* hohe Rendering-Performance
* etablierte Browser-Unterstützung

Die Kartenprojektion beeinflusst ausschließlich die Darstellung.

Reale Flächen-, Strecken- und Entfernungsberechnungen erfolgen unabhängig davon anhand geografischer Daten.

Optional kann langfristig zusätzlich eine separate flächentreue strategische Weltansicht angeboten werden.

Diese ersetzt jedoch nicht die operative Satellitenkarte.

---

# 52. World Wrapping

Die Karte soll horizontal kontinuierlich scrollbar sein.

Der Benutzer kann beispielsweise kontinuierlich nach Osten scrollen:

```text
Europe → Asia → Pacific → America → Atlantic → Europe
```

Es existiert für die Bedienung kein notwendiger fester linker oder rechter Weltkartenrand.

Dadurch entsteht das vertraute Verhalten moderner digitaler Karten.

---

# 53. Map Renderer

Der Kartenrenderer muss unabhängig vom Satellitenbildanbieter bleiben.

Bevorzugte Architektur:

```text
Map Renderer
     │
     ├── SatelliteTileProvider
     │
     ├── GameOverlayProvider
     │
     ├── VehicleLayer
     │
     ├── RouteLayer
     │
     ├── DepotLayer
     │
     ├── CompanyLayer
     │
     └── CargoLayer
```

Der Renderer darf nicht direkt an einen einzelnen Satellitenanbieter gekoppelt sein.

---

# 54. SatelliteTileProvider

Für Satellitenbilder wird ein eigenes Provider-Interface definiert.

Konzeptionell:

```text
SatelliteTileProvider

get_style()
get_tile_metadata()
get_attribution()
get_max_zoom()
get_usage_constraints()
```

Mögliche Implementierungen:

```text
MapTilerSatelliteProvider

MapboxSatelliteProvider

SelfHostedSatelliteProvider
```

Damit kann ein Anbieter später ausgetauscht werden, ohne die Game-UI neu zu entwickeln.

---

# 55. Daten- und Lizenzstrategie

Satellitenbilder besitzen eine andere rechtliche Situation als OpenStreetMap-Geometriedaten.

Deshalb müssen für jeden Kartenprovider mindestens dokumentiert werden:

* Anbieter
* Quelle der Bilddaten
* Lizenz
* notwendige Attribution
* kommerzielle Nutzungsrechte
* Request-Limits
* Kostenmodell
* Cache-Regeln
* erlaubte Speicherung
* erlaubte Weiterverarbeitung

Diese Informationen werden zentral in `DATA_SOURCES.md` beziehungsweise einer eigenen `MAP_PROVIDERS.md` dokumentiert.

Die Wahl des Produktionsproviders erfolgt daher nicht ausschließlich anhand der Bildqualität.

---

# 56. Map Technology

Für die Browserdarstellung wird bevorzugt ein WebGL-basierter Map Renderer eingesetzt.

Ein geeigneter Kandidat ist MapLibre GL JS.

Der Kartenrenderer muss mindestens unterstützen:

* Raster Tile Sources
* Vector Overlays
* GeoJSON
* Marker
* Linien
* Echtzeitaktualisierung
* Zoom
* Pan
* World Wrapping
* Layering
* Event Handling

Die eigentlichen Satellitenbilder werden über einen austauschbaren Tile Provider bereitgestellt.

---

# 57. Entwicklungsprovider und Produktionsprovider

Map-Rendering und Bildquelle werden bewusst getrennt.

Dadurch kann während Entwicklung beispielsweise ein günstiger oder offen verfügbarer Satellitenlayer eingesetzt werden.

Für Produktion kann später ein höher aufgelöster kommerzieller Provider verwendet werden.

Beispiel:

```text
Development

MapLibre
   ↓
Open / Development Satellite Tiles


Production

MapLibre
   ↓
Commercial High-Resolution Satellite Provider
```

Die Anwendung selbst muss dafür nicht umgebaut werden.

---

# 58. Satellite Map Performance

Da die Satellitenkarte dauerhaft sichtbar ist, gehört Map-Performance zu den zentralen Produktanforderungen.

Zu berücksichtigen sind:

* Tile-Caching
* Requestzahl
* Zoom-Level
* sichtbare Marker
* Marker-Clustering
* GeoJSON-Größe
* Anzahl gleichzeitig animierter Fahrzeuge
* Rendering-Frequenz
* Browser-GPU-Nutzung

Nicht jedes Fahrzeug weltweit muss in jedem Frame einzeln animiert werden.

Darstellung und Simulation bleiben getrennt.

---

# 59. Fahrzeugdarstellung abhängig vom Zoom

Ein Fahrzeug muss nicht auf jeder Zoomstufe dasselbe Icon besitzen.

Beispiel:

## Weit herausgezoomt

```text
●
```

## Regional

```text
🚚
```

## Nah

```text
[Truck Sprite]
```

Optional können später unterschiedliche Fahrzeugmodelle visuell unterschieden werden.

---

# 60. Map Interaction als Gameplay

Die Karte soll nicht nur Informationen darstellen.

Sie soll selbst ein wichtiges Eingabemedium sein.

Langfristige Beispiele:

**Depot auswählen**

→ Karte öffnen
→ Standort untersuchen
→ Grundstück beziehungsweise Region auswählen
→ kaufen

**Auftrag suchen**

→ Region ansehen
→ Cargo-Marker auswählen
→ Auftrag öffnen

**Fahrzeug verwalten**

→ Fahrzeug anklicken
→ Status öffnen
→ Route prüfen

**Expansion**

→ andere Stadt untersuchen
→ lokale Nachfrage ansehen
→ potenzielles Depot evaluieren

Dadurch wird geografisches Erkunden unmittelbar zum Gameplay.

---

# 61. UI-Philosophie

Die grundlegende Designregel lautet:

> **Map first, management second.**

Die Karte soll möglichst selten vollständig verlassen werden.

Komplexe Managementansichten dürfen eigene Views besitzen, sollen aber jederzeit schnell zur geografischen Welt zurückführen.

Die Spielwelt ist der primäre Navigationsraum.

---

# 62. Emotionales Ziel der Karte

Die Karte soll beim Spieler das Gefühl erzeugen:

> „Das ist nicht irgendeine abstrahierte Game-Map. Mein Unternehmen operiert dort draußen in der echten Welt.“

Wenn ein Truck Hamburg verlässt, soll der Spieler auf dem Satellitenbild tatsächlich die Elbe und den Hafen erkennen können.

Wenn ein Fahrzeug die Alpen überquert, soll geografisch sichtbar sein, dass es die Alpen überquert.

Wenn ein Schiff Rotterdam verlässt, soll der Spieler den realen Hafen und die Nordsee sehen.

Damit wird die reale Erde selbst zu einem zentralen Teil des Spielerlebnisses.

---

# 63. Aktualisierte North-Star-Definition (langfristiges Zielbild)

**World Freight Idle ist ein map-first, browserbasierter Multiplayer-Logistik-Tycoon, dessen primäre Benutzeroberfläche eine interaktive Satellitenkarte der realen Welt bildet. Spieler bauen darauf persistente Transportnetzwerke auf, kaufen Fahrzeuge und Depots, bedienen datengetriebene Frachtaufträge und verfolgen ihre Transporte in Echtzeit entlang realer Verkehrswege.**

## Umsetzungsabgleich: Fahrzeugkatalog und Kalkulation

Der bestehende Shop zeigt 14 DB-Modelle mit Spielpreis, Nutzlast,
Kilometerkosten und Reputationsfreigabe. Gesperrte oder nicht bezahlbare
Angebote benennen ihren Grund. Alle 14 Modelle verwenden in Shop, Flotte und
Transportdetails dieselben lokalen Front- und Seitenbilder. Auf der Karte
erscheint die zugehörige Draufsicht mit Spielerfarbe und Fahrtrichtung.
Für Modelle ohne lokale Grafik folgen verifizierte Katalogfotos mit Urheber,
Quelle, Lizenz und Modellfamilienhinweis; ohne Foto beziehungsweise bei dessen
Ladefehler bleibt die bestehende Ersatzillustration. Die Pfade liegen gemeinsam
in `frontend/vehicle-assets.js`; Darstellung und Ladeverhalten bleiben getrennt.
Siehe [Asset-Manifest](../assets/MANIFEST.md).
Ein Fahrzeugwechsel verwirft die alte Quote. Transportstart erfordert eine
aktuelle Kalkulation für genau das gewählte Fahrzeug. Kamera, Panelposition,
Tastaturfokus und mobile Bedienung bleiben erhalten. Neue Spielstände erhalten
175.000 € und den kostenlosen DB-IVECO S-Way 500 XC13. Altbestände werden
nur bei ausdrücklich beauftragter Profilpflege oder einem Offline-Schemaupgrade
umgestellt; das Energie-Upgrade bewahrt dabei bisherige Kaufwerte.
Konstanter Verbrauch, Energieanzeige und automatische Pausen sind umgesetzt;
Wartung, Stationssuche und Ladekurven folgen später. UI First, OSM für M1, Satelliten,
Unternehmen und eigene Depots nach der Frontend-Abnahme bleiben verbindlich.

Geladene Fahrzeugbilder bleiben bei Spielstands- und Statusaktualisierungen
sichtbar. Der Polling-Zyklus darf sie nicht erneut in den Ladezustand versetzen.

## Facility-Referenzen in der bestehenden Oberfläche

Die Facility-API /api/v1/map/facilities stellt stabile UUIDs bereit. Der
Browser lädt beim Start keinen globalen Facility-Bestand: Marker entstehen
aus eigener Flotte, aktiven Transporten und dem bedarfsabhängigen Auftragsmarkt;
Legacy-Hub-Links werden über explizite Aliase erkannt. Clustering, World
Wrapping, Kamera, Panels und Fokusverhalten bleiben erhalten. Auftragstexte
unterscheiden reale Standorte/Referenzunternehmen von simulierten Beziehungen,
Mengen und Einzelaufträgen. Fehlende Nachweise erzeugen einen Hinweis;
Fahrzeug-/Transportsnapshots bleiben bei Katalogausfall darstellbar.
Siehe [WORLD_CATALOGUE.md](WORLD_CATALOGUE.md).

Aufträge werden je routbarer Facility und belegter Nutzlastklasse aus dem
Fahrzeugkatalog ergänzt. Auch kleine Transporter und bestehende Fahrzeuge
erhalten geeignete Mengen; `payload_band` ist simuliert, reale Warenbelege
bleiben getrennt. Mengenregeln und Kompatibilität: [WorldCatalogue](WORLD_CATALOGUE.md).


## Aktuelle technische Grundlage

Typisierte Entities, relationale SQLite-Spielpersistenz (Schema 1.1.0) und
WorldCatalogue 4.0.0 bilden die einzige Laufzeit. Historische Snapshots bleiben
bei Katalogupdates erhalten. Details beschreiben [Architektur](ARCHITECTURE.md),
[Domainmodell](DOMAIN_MODEL.md) und [Persistenz](RELATIONAL_STATE.md).
Die abgeschlossene Umbauchronik liegt im [Archiv](archive/REFACTOR_EXECUTION.md).
Aktuelle Prüfungen und Grenzen stehen im [Qualitätsbericht](../QUALITY_REPORT.md).
Dieser technische Stand ersetzt weder die vollständige MVP- noch reale iPad-Abnahme.


### Energieoberfläche der ersten Simulation

Shop und Flotte zeigen Kapazität, Einheit, Verbrauch, Höchstgeschwindigkeit und
Tank-/Ladedauer. Eigene Fahrzeuge besitzen eine beschriftete kompakte Anzeige.
Auftragsdetails nennen die gesamte Spielzeit inklusive Halten. Transportphasen
sind „Unterwegs“, „Tankt“ oder „Lädt“; kurze Restpausen erscheinen in Sekunden.
Karte und Panels interpolieren denselben gespeicherten Fahrtplan. Während eines
Halts stehen Marker und Streckenfortschritt. Energie wird am Pausenende aufgefüllt.
Text-/Meterupdates behalten vorhandene Bildknoten; Polling, Spielerfarben,
World Wrapping und Kameraposition bleiben erhalten. Fremde Fahrzeuge veröffentlichen
nur die notwendigen Bewegungsintervalle, keine privaten Energieinhalte.
