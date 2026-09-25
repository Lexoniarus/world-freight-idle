# Karten-, Asset- und Fokusregressionsreview

Ausgangspunkt: `c962696`, Branch `feature/frontend-v2`, 25.09.2026.
Die Nachschärfung während der Umsetzung ist verbindlich: Gruppierung nur bei
überlappenden dargestellten Assetflächen, ohne Zoomschwelle und ohne festen
Mittelpunkt-Radius. Die Lackflächen wurden vom Nutzer im aktuellen Stand
als vorläufig passend bestätigt; Quellen bleiben unverändert.

## Einzelreview

Jeder Eintrag wurde auf Zweck, Schicht, Abhängigkeiten und Seiteneffekte
geprüft. Prüfgegenstand sind die neuen und wesentlich geänderten konkreten
Funktionen; bloße Zeilenzahl und grüne Tools ersetzen diesen Review nicht.
Kein Python-Core-Callable wurde eingeführt oder fachlich geändert.

### Asset-Komposition und Cache

| Callable | Schicht | Zweck | Abhängigkeiten | Seiteneffekte / Grenze |
| --- | --- | --- | --- | --- |
| `getVehiclePaintDescriptor` | Asset-Read-Modell | Original, Maske und Nordausrichtung verbinden | statische Modellzuordnung | rein; keine Pfadheuristik für unbekannte Modelle |
| `normalizeVehicleColor` | Darstellung | sichere Hex-Farbe normalisieren | Hex-Vertrag und vorhandener Fallback | rein; aus Kartenmodul in gemeinsames Modul verschoben |
| `paintPixels` | Darstellungsmathematik | nur maskierte RGB-Werte multiplizieren | Original-, Maskenpuffer und Farbe | neuer Puffer; Alpha und geschützte RGB unverändert |
| `originalVehicleSvg` | Asset-Adapter | ungetöntes eingebettetes Original extrahieren | bekanntes Raster-SVG-Format | rein; nur PNG-Daten und numerische Abmessungen übernehmen |
| `readPixels` | Browser-Adapter | SVG an Originalabmessungen dekodieren | Image, Canvas, Object-URL | temporäre URL immer in finally freigeben |
| `composeVehiclePaint` | Asset-Orchestrierung | Original, Maske und Färbung zusammenführen | Extraktion, Decoder, reine Pixelregel | Canvas-Ausgabe; keine HTTP- oder Cacheverantwortung |
| `VehicleColorAssets.constructor` | Asset-Service | Cache- und Lebenszykluszustand anlegen | injizierter Loader und Composer | nur lokaler Zustand |
| `VehicleColorAssets.source` | Asset-Service | identische Farbkompositionen zusammenführen | Deskriptor, Quellen-Cache, Composer | Promise-Cache; Fehler ermöglichen Retry |
| `VehicleColorAssets.readSource` | Asset-Service | Originale und Masken einmal lesen | injizierter Loader | Quellen-Cache; fehlerhafte Reads entfernen |
| `VehicleColorAssets.destroy` | Asset-Service | eigene Cache-/URL-Ressourcen freigeben | Varianten und Quellen | keine weiteren Reads; Leases berücksichtigen Disposal |
| `VehicleIconRegistry.constructor` | Karten-Adapter | Atlas-Abhängigkeiten und Besitz verdrahten | Map, Loader, Rasterizer, optionaler gemeinsamer Asset-Service | eigener Service nur ohne injizierten Besitzer |
| `VehicleIconRegistry.loadAndRegister` | Karten-Adapter | eine fertige Variante im Atlas registrieren | gemeinsame Komposition, Rasterizer, Bounds-Messung | MapLibre-Bild; Fehler explizit geloggt, kein Tönungsfallback |
| `VehicleIconRegistry.destroy` | Karten-Adapter | eigene Atlasbilder und optionalen Service freigeben | MapLibre, registrierte IDs | injizierten gemeinsamen Service nicht entsorgen |

### Überlappung und Renderer

| Callable | Schicht | Zweck | Abhängigkeiten | Seiteneffekte / Grenze |
| --- | --- | --- | --- | --- |
| `vehicleIconScale` | Geometriemathematik | Renderer-Skalierung aus gemeinsamen Stops interpolieren | Zoom und identische Layer-Stops | rein; keine Gruppierungsschwelle |
| `spriteBounds` | Geometriemathematik | sichtbare Alpha-Ausdehnung relativ zum Anker bestimmen | fertiges ImageData, Atlas-Pixelratio 2 | rein; transparente Randflächen zählen nicht |
| `vehicleFootprint` | Geometriemathematik | Assetrechteck in Bildschirmkoordinaten drehen/skalierten | Bounds, Position, Bearing, Kartenrotation | rein; idle bleibt viewport-ausgerichtet |
| `footprintsOverlap` | Geometriemathematik | gedrehte Rechtecke auf Überschneidung prüfen | Separating-Axis-Projektionen | rein; bloßer Randkontakt gruppiert nicht |
| `groupVehicles` | Kartenprojektion | status-/eigentümergetrennte Überschneidungsgruppen bilden | Projektion, Footprints, stabile Identität | rein; Eingabekoordinaten unverändert, Auswahl ausgenommen |
| `addOverlayLayers` | Karten-Adapter | Sources und Darstellungsregeln registrieren | MapLibre, gemeinsame Skalierungsstops | Layerwrites; keine Gruppierungs- oder Fahrtlogik |
| `OverlayData.constructor` | Karten-Read-Modell | Snapshot- und Iconmetadaten besitzen | lokale Maps/Sets | nur Initialisierung |
| `OverlayData.setVehicleIcons` | Karten-Read-Modell | verfügbare Icon-IDs und Bounds übernehmen | Registry-Projektion | lokaler Zustand |
| `OverlayData.hubFeatures` | Kartenprojektion | Facilities unter sichtbaren idle Representatives ausblenden | gerenderte eigene Features, Facility-Snapshots | rein; Quellen, Aufträge und Weltkatalog bleiben erhalten |
| `OverlayData.vehicleFeatures` | Kartenprojektion | eigene idle Fahrzeuge samt Frontasset projizieren | Snapshots und Iconmetadaten | rein; keine Marktentscheidung |
| `OverlayData.trafficFeatures` | Kartenprojektion | öffentliche Bewegung mit Bearing und Status projizieren | bestehende Journey-Interpolation und öffentliche Snapshots | rein; keine privaten Wirtschaftsdaten ergänzt |
| `VehicleGroups.constructor` | Gruppen-Präsentation | Badge-/Gruppenzustand besitzen | Map, Navigation, Motion-Präferenz | keine eigene Assetpipeline mehr |
| `VehicleGroups.update` | Gruppen-Präsentation | gedrosselte Mitgliedschaften und Badge-Lebenszyklen abgleichen | reine Gruppierung, MapLibre Marker | Orchestrierung; Representative verbleibt im normalen Renderer |
| `VehicleGroups.updatePoses` | Gruppen-Präsentation | Badge an aktuelle Representative-Koordinate binden | aktuelle Features, Marker | Positionsupdates auch ohne Neugruppierung |
| `VehicleGroups.renderVisual` | Gruppen-Präsentation | Count und zugängliche Representative-Metadaten zeigen | explizites erstes stabiles Mitglied | DOM; weder Bildauswahl noch Rotation |
| `VehicleGroups.destroy` | Gruppen-Präsentation | Marker und Popup entsorgen | eigene Marker/Popup | keine fremden Bild-Leases |
| `WorldMap.constructor` | Karten-Composition | Kartenkomponenten verdrahten | OverlayData, Registry, Gruppen und Kamera | Initialisierung; Zustandsgrenzen bleiben getrennt |
| `WorldMap.bindMapEvents` | Karten-Lifecycle | Kartenevents an Darstellungsaktionen binden | MapLibre, bestehende Interaktionsmethoden | Listener; move aktualisiert Darstellung, keine Marktrequests |
| `WorldMap.update` | Karten-Orchestrierung | neuen Snapshot an Darstellungsbesitzer verteilen | OverlayData und Layeradapter | keine Kamerabewegung |
| `WorldMap.syncVehicleIcons` | Karten-Orchestrierung | fertige Atlasmetadaten ins Read-Modell übernehmen | Registry, OverlayData | async Disposal-Schutz; keine Navigation |
| `WorldMap.drawTraffic` | Karten-Orchestrierung | aktuelle Bewegungsfeatures und Auswahl veröffentlichen | Read-Modell, Gruppen, Source-Adapter | kein Pricing, Routing oder Kamerafokus |
| `WorldMap.updateFacilityProjection` | Karten-Adapter | nur geänderte Facility-Projektionen veröffentlichen | fertige Feature-Auswahl | Signaturcache verhindert identische Workerwrites je Frame |
| `WorldMap.toggle` | Karten-Präsentation | Layer-Sichtbarkeit anwenden und neu projizieren | Layerpräferenzen und bestehender Draw-Pfad | kein Snapshot- oder Katalogeingriff |

### Preferences und Navigation

| Callable | Schicht | Zweck | Abhängigkeiten | Seiteneffekte / Grenze |
| --- | --- | --- | --- | --- |
| `PreferencesController.constructor` | UI-Service | bestätigte und gewünschte Farbe besitzen | Request, Panel, Map, Notify, Document | lokaler Zustand und Request-Lifetime |
| `PreferencesController.start` | UI-Lifecycle | Palette-/Retry-Aktionen und Sichtbarkeitsrefresh binden | injiziertes Document | abbrechbare Listener |
| `PreferencesController.refresh` | UI-Service | aktuellsten Palette-Read veröffentlichen | LatestRequest und bestehende API | Loading/Error/Ready; keine Writes |
| `PreferencesController.save` | UI-Service | optimistische Auswahl und Write-Queue koordinieren | serverseitig geladene Palette, persist | keine parallelen Writes; neuester Wunsch wird beibehalten |
| `PreferencesController.persist` | UI-Service | genau eine Preference schreiben und bestätigen | bestehende API, Lifetime | Fehler der letzten Auswahl setzt bestätigte Farbe zurück |
| `PreferencesController.publish` | UI-Projektion | eine Farbe an Darstellungseigentümer verteilen | Panel, Map, Document | keine Requests oder Asset-Kompositionslogik |
| `PreferencesController.destroy` | UI-Lifecycle | Reads, Writes und Listener invalidieren | eigene AbortController | späte Ergebnisse können nicht mehr publizieren |
| `renderCompanyPreferences` | View | Ladezustand, Retry und Palette darstellen | typisiertes Panel-Read-Modell | nur DOM; keine Requests |
| `fleetGroups` | Read-Modell | Flotte nach vorhandener Stadt-/Fahrtrichtungssicht gliedern | Snapshot | unverändert aus View verschoben; keine Kamera |
| `selectFleetGroups` | Read-Modell | sichtbare Flottenfilter gemeinsam auswerten | URL, Snapshot, Stadt | rein; View und Fokus erhalten identische Auswahl |
| `renderFleet` | View | gemeinsam selektierte Flotte darstellen | fleet-selection und UI-Renderer | keine eigene zweite Filterdefinition |
| `coordinates` | Fokusprojektion | endliche Snapshot-Koordinaten projizieren | Locationwerte | rein; keine Standort-Erfindung |
| `vehiclePosition` | Fokusprojektion | aktuellen Fahrzeugpunkt bestimmen | gespeicherter Transport, Journey-Interpolation | rein; kein Routenfit im Fahrzeugdetail |
| `transportCoordinates` | Fokusprojektion | gesamte Route und aktuelle Pose zusammenstellen | gespeicherte Route und Checkpoints | rein; keine Routinganfrage |
| `focusCoordinates` | Fokusprojektion | Navigationsziel in zu rahmende Punkte übersetzen | URL, Selektoren, Read-Modelle | rein; null bedeutet ausstehendes Auftragsdetail |
| `MapFocusController.constructor` | Navigations-Service | Fokusabsicht und erfüllten Schlüssel besitzen | State, View, Map | lokaler Zustand |
| `MapFocusController.start` | Navigations-Lifecycle | fehlende Daten und Map-Readiness beobachten | State/Map Events | Listener; kein dauerndes Tracking |
| `MapFocusController.cancel` | Navigations-Service | vorherige verzögerte Absicht verwerfen | eigener Pending-Zustand | keine Kamerabewegung |
| `MapFocusController.select` | Navigations-Service | echten URL-/Filterwechsel vormerken | normalisierter URL-Schlüssel | bereits erfüllter Fokus wird nicht wiederholt |
| `MapFocusController.flush` | Navigations-Service | bereite Absicht einmal konsumieren | reine Fokusprojektion, Kamera-Port | ein Kamerabefehl; leere Auswahl bleibt ohne Bewegung |
| `MapFocusController.quote` | Navigations-Service | aktuelle benutzerinitiierte Quote rahmen | vom GameActions-Request geprüfte Antwort | ersetzt ausstehendes Endpunkt-Framing |
| `MapFocusController.destroy` | Navigations-Lifecycle | Absicht und Eventbindungen freigeben | eigene Listener | keine Fremdkomponente entsorgen |
| `CityContextController.selectRoute` | Stadt-Service | Stadtkontext auflösen und URL synchronisieren | bestehender Requestpfad | automatischer Kameraseiteneffekt entfernt |
| `GameActions.constructor` | Use-Case-Orchestrierung | Fokus-Port ergänzend injizieren | bestehende Ports | nur Verdrahtung |
| `GameActions.calculateQuote` | Use-Case-Orchestrierung | aktuelle Quote an Preview und Fokus publizieren | LatestRequest, Fahrzeugwahl, API | veraltete Antworten bleiben ausgeschlossen |
| `GameApplication.constructor` | Composition/Lifecycle | Fokuskomponente übernehmen | injizierte Komponenten | keine Fachregeln |
| `GameApplication.start` | Composition/Lifecycle | Fokus nach State-Synchronisation aktivieren | Komponenten-Lifecycles | Initialnavigation bleibt gemeinsamer Pfad |
| `GameApplication.navigateTo` | Navigations-Orchestrierung | Auswahl und einmaligen Fokus zusammenführen | bestehende navigationVersion | späte Stadtantworten bleiben ohne Fokuswirkung |
| `GameApplication.destroy` | Composition/Lifecycle | Fokus vor Kartenabbau entsorgen | Komponenten-Lifecycles | keine zusätzlichen Requests |
| `createGameApplication` | Composition Root | Fokusservice an App und Actions verdrahten | vorhandener State, View und Map | keine Regeln in Bootstrap ergänzt |

## Einzelreview: nachträgliche Fahrzeugkontext-Präzisierung

| Callable | Schicht und Zweck | Abhängigkeiten | Seiteneffekte / Befund |
| --- | --- | --- | --- |
| `vehicleCity` | Reine Snapshotprojektion | gespeicherter Standort | keine; keine Stadt aus Fahrtziel |
| `marketVehicle` | Reine Kontextauflösung | State, URL, Initialflag | keine Mutation des States; stabile ID-Reihenfolge, kein Polling-Ersatz |
| `CityContextController.constructor` | Lifecycle/Verdrahtung | State, View, Request, Notify | eigener Request-Lifecycle; Kameraabhängigkeit entfernt |
| `CityContextController.update` | Kontextabgleich | Snapshot und aktuelle Route | View/URL aktualisieren, keine Kamera oder Spielmutation |
| `CityContextController.writeCity` | URL-Übersetzung | aufgelöster Kontext | History ersetzen; leerer Kontext entfernt Parameter |
| `CityContextController.selectRoute` | Kontext-Orchestrierung | Lookup und reine Fahrzeugauflösung | vorherige Stadt wird nicht global vererbt; obsolete Requests verworfen |
| `ManagementInput.constructor` | Verdrahtung | UI-Ports | ungenutzte Stadtabhängigkeit entfernt |
| `ManagementInput.change` | UI→URL-Übersetzung | Formulare, Navigation | Fahrzeugwechsel verwirft bisherigen Stadtfilter |
| `ManagementInput.click` | UI-Aktionsdispatch | vorhandene Ports | globaler Stadtfokus entfernt |
| `renderShell` | View | Nutzer, Navigation | DOM; globales Stadtelement und Fokusbutton entfernt |
| `renderContracts` | View-Komposition | aufgelöster Kontext, Offers | DOM; kein globaler Markt ohne Fahrzeugstadt |
| `filterContracts` | Reiner Listenfilter | serverseitige Offerfakten | keine eigene Kompatibilitätslogik; Fahrzeug blendet nichts aus |
| `renderContractCard` | View-Projektion | `eligible_vehicle_ids`, Referenzfahrzeug | DOM; geeignet/ungeeignet explizit |
| `renderContractDetails` | View-Komposition | bestehender Offer/View | Rücklink erhält Fahrzeugkontext |
| `renderDispatchForm` | View | serverseitig geeignete Fahrzeuge | DOM; leerer expliziter Auswahlzustand darstellbar |
| `PanelController.reconcileVehicleSelection` | Auswahl-Lifecycle | Offer/URL/Eignungs-IDs | alte Quote löschen; explizit ungeeignetes Fahrzeug nie ersetzen |
| `renderVehicle` | View | Fahrzeug und Fahrt | idle Aktion heißt Stadtmarkt öffnen |

Kein Python-Core-Callable ergänzt oder geändert. `prepare_energy_fixture`
bleibt reine Testserver-Orchestrierung bestehender Domainmethoden; vor der
Verbrauchsvorgabe wird explizit aufgefüllt. Dadurch hängt der Test nicht von
einem vorherigen Aufruf des Fixtures ab.

## Im Review konkret korrigiert

- Gruppen verloren ihren separaten Bildrenderer; Bearings und Fallbacks
  werden jetzt vollständig durch denselben Symbolpfad wie Singletons getragen.
- Der feste 48-Pixel-Radius wurde durch gedrehte sichtbare Assetrechtecke
  ersetzt; Skalierung und Atlas-Pixelratio entsprechen dem Renderer.
- Die Facility-Projektion wird nur bei Änderung zum Worker geschickt.
- Globale Ganzbildfärbung ist entfernt; keine parallele Legacy-Tönung bleibt.
- SVG-Originalextraktion übernimmt nur eingebettetes PNG und Abmessungen,
  keine Eventattribute, alten Filter oder beliebiges Markup.
- Flottenfilter wurden aus der View entfernt, damit Kamerafokus und Ansicht
  nicht auseinanderlaufen. Automatischer Stadtfokus liegt nicht mehr im
  Stadt-Controller.
- Preference-Reads überschreiben keine neuere Auswahl; Writes laufen seriell.
- Bereits konsumierter Fokus und noch ausstehender Fokus sind getrennt,
  damit Wiederholung derselben noch ladenden Navigation nicht verloren geht.

## Daten- und Vertragsabgleich

API-Routen, Game-Schema, Preferences-Schema, World-/Vehicle-Kataloge und
private/öffentliche Snapshot-Verträge bleiben unverändert. Keine
Neuklassifizierung historischer Analytics, keine neue Marktstadt aus einem
Ziel oder einem fahrenden Checkpoint. Die bestehenden Fahrzeuglabels
bleiben serverseitig und ID-gruppiert.

Das Wirtschaftsaudit wurde erneut ausgeführt: 14 Modelle, 163.296 Zeilen,
2.457 explizit inkompatible Kombinationen. Minimale Referenzmarge
45,748730964467005 %, 16.298 negative Cashflowfälle, davon 4.878 typische
Beladungen. Diese Ergebnisse entsprechen dem vorherigen freigegebenen
Audit. Negative Cashflows bleiben möglich; keine Balanceparameter geändert.

Neue Testserveroption `single_stop` betrifft ausschließlich temporäre
Browserprofile und erzeugt deterministisch einen Einkauf. Sie verändert
keinen Produktionskatalog und keine Spielerdatei.

Produkt, Ziel, Meilensteine, Architektur, UI, Kartenprovider, Datenquellen
und Testdokumentation wurden abgeglichen. API-, Domain-, Persistenz- und
Economy-Dokumente benötigen keine neuen fachlichen Verträge.

## Abnahmenachweise

Die isolierten Browserprüfungen verwenden echte MapLibre-Renderer mit
Produktionsmodulen. Pixelprüfungen kontrollieren Alpha, alle nicht maskierten
RGB-Pixel sowie unabhängig gewählte Fenster-/Grill-/Reifenpunkte über alle
42 Ansichten. Sichtbare Richtungen werden zusätzlich mit der gerenderten
Cab-Ausrichtung und den Screenshotbelegen geprüft.

Aktuelle vollständige Gate-Ergebnisse und die visuelle Prüfliste stehen
im Qualitätsbericht. Quellen-SVGs bleiben durch das bestehende Inventar
mit unveränderten Hashes abgesichert; neue Masken haben ein eigenes Inventar.
