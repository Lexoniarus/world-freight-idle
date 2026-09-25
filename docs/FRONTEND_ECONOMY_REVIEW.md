# Frontend-v2: Einzelreview der Verantwortungen

Vergleichsbasis: erhaltener lokaler Commit `548336f`. Review vom 25.09.2026.
Jede unten aufgeführte Funktion wurde im Quelltext auf Zweck, Schicht,
Abhängigkeiten und Seiteneffekte geprüft. Grüne Tests und Funktionslänge
wurden nicht als Ersatz für diese Prüfung verwendet. Abstracte Ports sind
Verträge, keine konkreten Callables des Manifest-Gates.

## Im Review behobene Punkte

- Kostenberechnung verlangt einen expliziten `CostBreakdown`; der bisherige
  aggregierte Kilometerkostenpfad wurde aus neuen Quotes entfernt.
- Die Factory führt keine Katalogreads aus. Immutable Candidate-Kontexte
  tragen Kosten/Energie, die Tarifberechnung bleibt eine kleine Domainfunktion.
- Der minimale operative NHM-Faktor wird revisionsgebunden indexiert, nicht
  bei jedem einzelnen Candidate über alle Profile neu berechnet.
- Startup verdrahtet Markt-Lifecycles direkt; GameService-Initialisierung und
  Settlement sind kein Bestandteil des globalen Rebuilds.
- Analyticsnamen verändern keine historischen Klassifizierungen. Bei gleichen
  achtstelligen ID-Präfixen wird der Zusatz bis zur Eindeutigkeit verlängert.
- Bild-Leases werden vor Freigabe alter Bindungen übernommen. MapLibre erhält
  bereits kolorierte gemeinsame Quellen ohne einen zweiten SVG-Farbfilter.
- Dispatch-Navigation prüft die aktive URL-Objektidentität; berechtigtes
  Stadtparameter-Aufräumen unterdrückt nicht mehr die Transportansicht.

## Python-Core

| Datei / Callable | Schicht | Fachlicher Zweck | Abhängigkeiten | Seiteneffekte / Reviewentscheidung |
| --- | --- | --- | --- | --- |
| `app/bootstrap.py` · `build_player_service` | Composition Root | Spieler-Service einschließlich Kostenresolver verdrahten | Runtime, UoW, Katalog | delegierte Initialisierung; keine Kostenregel |
| `app/bootstrap.py` · `build_market_startup` | Composition Root | globalen Marktstart verdrahten | Runtime und Store-Adapter | nur Konstruktion |
| `app/bootstrap.py` · `build_market_startup.lifecycle` | Composition Root | Market-Lifecycle für bestehende Profil-ID binden | gemeinsame DB/UoW, Markt, Uhr | Konstruktion; kein Settlement/Profilstart |
| `app/bootstrap.py` · `build_preferences` | Composition Root | Preference-Port und Service binden | Account-Store | Adapter initialisiert Hilfstabelle |
| `app/main.py` · `lifespan` | Application | Start-/Shutdown-Reihenfolge besitzen | HTTP-Client, Factories, Startup-Service | Ressourcen/Readiness; kein SQL/Marktalgorithmus |
| `app/api/v1/auth.py` · `current_user` | API | Identität mit wirksamer Farbe projizieren | Sitzung, Preference-Service | Read; keine Paletteberechnung |
| `app/api/v1/auth.py` · `preferences` | API | Preference samt erlaubter Palette ausliefern | Sitzung, Service, Palettekonstante | Read |
| `app/api/v1/auth.py` · `update_preferences` | API | Farbänderung und Fehler nach HTTP übersetzen | Body, Sitzung, Service | delegierter Write; 422-Übersetzung |
| `app/api/v1/game_projection.py` · `project_quote` | API | typisierte Quote in JSON projizieren | Quote-Snapshot | keine Mutation/Neuberechnung |
| `app/api/v1/game_projection.py` · `project_transport` | API | gespeicherten Transport in JSON projizieren | Transport, optionaler Zeitpunkt | keine Katalogrekonstruktion |
| `app/api/v1/traffic_projection.py` · `project_traffic` | API | öffentliche Bewegung und Farbe projizieren | SharedTransport, Viewer-ID, Domain-Fallback | strukturiertes Read-Log; keine privaten Kosten |
| `app/domain/analytics_labels.py` · `vehicle_labels` | Domain | aktuelle Anzeigenamen eindeutig bilden | Namen und IDs | rein; erweitert kollidierende Kurz-IDs |
| `app/domain/company_colors.py` · `player_color` | Domain | bestehenden deterministischen Fallback berechnen | Account-ID | rein; Algorithmus unverändert verschoben |
| `app/domain/economics.py` · `whole_euros` | Domain | einen Geldbetrag kaufmännisch runden | Decimal | rein |
| `app/domain/economics.py` · `VehicleCostProfile.__post_init__` | Domain | expliziten Wartungssatz validieren | numerische Validierung | nur Invariante |
| `app/domain/economics.py` · `EnergyPurchase.__post_init__` | Domain | einzelnen Einkauf validieren | Index, Menge, Integerbetrag | nur Invariante |
| `app/domain/economics.py` · `CostBreakdown.__post_init__` | Domain | gespeicherte Kostenkomponenten konsistent halten | Einheit, Sätze, immutable Einkäufe | nur Invariante; keine aktuellen Preise nachladen |
| `app/domain/economics.py` · `journey_costs` | Domain | Journey-Wartung und tatsächliche Käufe bilanzieren | Journey, Kostenprofil, Gameplaypreise | rein; keine Tonnage-/Tarifänderung |
| `app/domain/economy_audit.py` · `audit_economy_case` | Domain-Audit | ein reproduzierbares Wirtschaftsszenario auswerten | Produktionsfunktionen, explizite Szenariowerte | rein; orchestriert getrennte Regeln und Referenzvergleich |
| `app/domain/market.py` · `MarketCandidate.__post_init__` | Domain | Candidate-Kontext einschließlich Referenzfaktor validieren | Trade, Profile, Fahrzeuge | nur Invariante |
| `app/domain/market_calculations.py` · `biased_load_factor` | Domain | uniformen Draw in zulässige hohe Beladung transformieren | min/max/draw | rein; kein RNG, Tarif oder Retry |
| `app/domain/market_compatibility.py` · `market_vehicle` | Domain | Owned- und Katalogwerte zum Generierungskontext verbinden | OwnedVehicle, Modell, Location | rein; keine Modellheuristik |
| `app/domain/market_startup.py` · `MarketStartupStore.transaction` | Domain-Port | abstrakten Speichervertrag beschreiben | typisierte Werte/UoW | keine Implementierung; SQL bleibt im Adapter |
| `app/domain/market_startup.py` · `MarketStartupStore.player_ids` | Domain-Port | abstrakten Speichervertrag beschreiben | typisierte Werte/UoW | keine Implementierung; SQL bleibt im Adapter |
| `app/domain/preferences.py` · `PreferenceStore.transaction` | Domain-Port | abstrakten Speichervertrag beschreiben | typisierte Werte/UoW | keine Implementierung; SQL bleibt im Adapter |
| `app/domain/preferences.py` · `PreferenceStore.color` | Domain-Port | abstrakten Speichervertrag beschreiben | typisierte Werte/UoW | keine Implementierung; SQL bleibt im Adapter |
| `app/domain/preferences.py` · `PreferenceStore.save_color` | Domain-Port | abstrakten Speichervertrag beschreiben | typisierte Werte/UoW | keine Implementierung; SQL bleibt im Adapter |
| `app/domain/pricing.py` · `calculate_price` | Domain | gespeicherten Tarif auf Frachtkilometer anwenden | Tons, Lieferrouting, Tarif, explizite Kosten | rein; alte aggregierte Kostenschätzung entfernt |
| `app/domain/tariffs.py` · `FreightTariff.__post_init__` | Domain | vollständige positive Tarifwerte verlangen | Version und Zahlen | nur Invariante |
| `app/domain/tariffs.py` · `freight_tariff` | Domain | NHM-Mindesttarif aus Referenzfahrzeug ableiten | Kosten, Energie, NHM-Faktoren | rein; keine Mengen-/Fahrzeugwahl |
| `app/domain/transports.py` · `ActiveTransport.__post_init__` | Domain | Transport-Snapshot konsistent halten | Route, Journey, gespeicherte Beträge | nur Invariante; neue Aufteilung muss Gesamtbetrag entsprechen |
| `app/domain/vehicles.py` · `VehicleModel.__post_init__` | Domain | operative Referenzwerte einschließlich Wartung prüfen | Modellwerte und kleine Validatoren | nur Invariante; keine SQL-Konvertierung |
| `app/repositories/analytics.py` · `SqliteAnalyticsReader.read` | Repository | konsistentes Statistik-Read-Modell lesen | SQLite und Skalarprojektor | Read-Transaktion; keine historischen Modellklassifikationen |
| `app/repositories/market_startup.py` · `SqliteMarketStartupStore.transaction` | Repository | äußere UoW bereitstellen | SqliteGameDatabase | delegierte technische Transaktion |
| `app/repositories/market_startup.py` · `SqliteMarketStartupStore.player_ids` | Repository | bereits vorhandene Profile lesen | SQLite | Read in stabiler Reihenfolge; keine Accounts erzeugen |
| `app/repositories/preferences.py` · `SqlitePreferenceStore.__init__` | Repository | Account-Preference-Speicher initialisieren | SqliteGameDatabase | idempotentes Hilftabellen-DDL; kein Game-Schemawechsel |
| `app/repositories/preferences.py` · `SqlitePreferenceStore.transaction` | Repository | Preference-UoW bereitstellen | SqliteGameDatabase | delegierte technische Transaktion |
| `app/repositories/preferences.py` · `SqlitePreferenceStore.color` | Repository | gespeicherte Accountfarbe lesen | Account-ID, SQLite | Read; kein fachlicher Fallback |
| `app/repositories/preferences.py` · `SqlitePreferenceStore.save_color` | Repository | Accountfarbe persistieren | Account-ID, Farbe, SQLite | UPSERT innerhalb Service-UoW; keine Palettenregel |
| `app/repositories/relational_traffic.py` · `SqliteTrafficReader.list_active_transports` | Repository | öffentliche aktive Bewegungen samt Preference lesen | SQLite, Snapshot-Projektor | Read; Eigentümer-Joins strikt accountbezogen |
| `app/repositories/relational_traffic.py` · `project_traffic_row` | Repository | Snapshot in öffentlichen Domain-Lesewert abbilden | Transportdecoder, SQL-Zeile | rein; entfernt private Wirtschafts-/Energieinformationen |
| `app/repositories/snapshot_mapping.py` · `load_market_context` | Repository-Mapping | optionalen historischen Markt-/Tarifkontext decodieren | Snapshotdict, immutable Werte | rein; fehlend bleibt fehlend, leeres beschädigtes Tarifobjekt wird nicht verschluckt |
| `app/repositories/transport_mapping.py` · `load_transport` | Repository-Mapping | kanonischen Transport aus Snapshot zusammensetzen | kleine Decoder | rein; kein Routing/Katalog/Repricing |
| `app/repositories/transport_mapping.py` · `load_cost_breakdown` | Repository-Mapping | optionale gespeicherte Kosten decodieren | Snapshotdict, Kostenwerte | rein; keine aktuelle Preisquelle |
| `app/services/analytics.py` · `breakdown` | Analytics | Skalarhistorie nach unveränderten IDs aggregieren | Zeilen, Dimension, optionale Labels | rein; Label verändert Gruppierung nicht |
| `app/services/analytics.py` · `AnalyticsService.analyze` | Service | Statistik-Lese-Use-Case orchestrieren | Reader-Port, Aggregatoren, Label-Funktion | Read und strukturiertes Log; keine Mutationen |
| `app/services/contract_factory.py` · `ContractFactory.build` | Service | einen Candidate zu einem Offer materialisieren | injizierter RNG, immutable Candidate, reine Mengen-/Tariffunktionen | RNG-Verbrauch; kein SQL/Routing, kein Gewinn-Retry |
| `app/services/cost_profiles.py` · `VehicleCostResolver.resolve` | Service | explizites Kostenprofil zum Modell auflösen | VehicleCatalogue-Port | Referenzread; keine Rückrechnung |
| `app/services/dispatch_planning.py` · `DispatchPlanningService.quote` | Service | revalidierten Route-/Fahrzeugkontext zur Quote komponieren | Kostenresolver, Journey/Kosten/Pricing-Domain | Referenzread; keine Schreibtransaktion oder Offeränderung |
| `app/services/game.py` · `GameService._build_trip` | Service | geprüfte Quote als Transport einfrieren | Quote, Offer, Abfahrtszeit | UUID-Erzeugung; keine neue Preis-/Routingregel |
| `app/services/market_candidates.py` · `MarketCandidateService.__init__` | Service | Referenzports und Indexzustand besitzen | World-/Vehicle-Ports | lokaler Cachezustand |
| `app/services/market_candidates.py` · `MarketCandidateService.reference` | Service | revisionsabhängige Marktindizes aktualisieren | World-Port, TradeNetwork | Read und Cache; minimaler NHM-Faktor nur je Revision |
| `app/services/market_candidates.py` · `MarketCandidateService._candidate` | Service | Kompatibilität, Distanz und Candidategewicht kombinieren | Trade, aufgelöste Flotte, reine Regeln | rein bezogen auf Cache; kein konkretes Fahrzeug reserviert |
| `app/services/market_startup.py` · `MarketStartupService.rebuild` | Service | alle offenen Märkte atomar neu aufbauen | Startup-Port, Referenzports, Lifecycle-Factory | eine äußere UoW und Logs; kein Routing/Settlement/SQL |
| `app/services/preferences.py` · `PreferenceService.read` | Service | wirksame Accountfarbe auflösen | Preference-Port, deterministischer Fallback | Read; keine Speicherung des Fallbacks |
| `app/services/preferences.py` · `PreferenceService.update` | Service | erlaubte Firmenfarbe atomar ändern | Palette und Preference-Port | eine UoW und Log; Account kommt aus API-Sitzung |


Alle konkreten neuen Python-Callables besitzen explizite Gegentests im
Function-Test-Manifest. Datenklassen ohne eigene Methoden ergänzen reine
Werte: `AccountPreferences`, `MarketVehicle`, `OfferMarketContext`,
`ContractQuote`, `PriceQuote`, `AnalyticsData`, `SharedTransport` und
`EconomyAuditResult`. Sie führen keine versteckten Speicherzugriffe aus.

## Browser-Core

Die folgenden Methoden einschließlich ihrer lokalen Promise-/Eventcallbacks
wurden einzeln geprüft. Alle View-/UI-Funktionen bleiben reine Darstellung;
Requests und Ressourcenbesitz liegen in Controllers/Registries.

| Datei / Callable | Zweck und Grenze | Abhängigkeiten / Seiteneffekte |
| --- | --- | --- |
| `frontend/application.js` · `GameApplication.constructor` | Lebenszyklus-Abhängigkeiten halten | injizierte Komponenten; keine Requests |
| `frontend/application.js` · `GameApplication.start` | Komponenten und initiale Synchronisierung starten | delegierte Starts/Reads |
| `frontend/application.js` · `GameApplication.destroy` | Komponenten in definierter Reihenfolge freigeben | Listener/Requests/Map/Bilder via Besitzer beenden |
| `frontend/bootstrap.js` · `createGameApplication` | Browser-Composition-Root verdrahten | API und Komponenten; keine Fachberechnung |
| `frontend/bootstrap.js` · `createWorldMap` | Map-Adapter und dessen Dependencies konstruieren | WebGL/Kartenprovider; expliziter UI-Fallback |
| `frontend/controllers/city-context-controller.js` · `CityContextController.constructor` | Stadtauswahl-Zustand halten | State/View/Request-Port |
| `frontend/controllers/city-context-controller.js` · `CityContextController.update` | aktive Marktstädte und Auswahl abgleichen | State; View/URL/Label aktualisieren, kein HTTP |
| `frontend/controllers/city-context-controller.js` · `CityContextController.selectRoute` | URL-Stadtkontext auflösen | Request-Port/LatestRequest; alte Antworten verwerfen |
| `frontend/controllers/game-actions.js` · `GameActions.dispatchTransport` | Annahme ausführen und aktuellen Transport öffnen | Request/State/Navigate; serverseitige Quote maßgeblich |
| `frontend/controllers/panel-controller.js` · `PanelController.constructor` | Panel-Abhängigkeiten und Bindungsbesitzer halten | DOM/Request-Port; kein Bildfetch |
| `frontend/controllers/panel-controller.js` · `PanelController.replaceContent` | Panel-DOM mit Fokus/Disclosures/Bildern abgleichen | Renderer und Bildbinder; keine Game-Requests |
| `frontend/controllers/panel-controller.js` · `PanelController.destroy` | Panelressourcen freigeben | Requests abbrechen, Bild-Leases lösen |
| `frontend/map/grouping.js` · `groupVehicles` | Bewegungen deterministisch räumlich gruppieren | reine Projektion; eigene/fremde und fremde Owner trennen |
| `frontend/map/layers.js` · `addOverlayLayers` | MapLibre-Darstellungslayer definieren | Map-Stylemutation; keine Daten-/Eignungsregeln |
| `frontend/map/overlay-data.js` · `OverlayData.constructor` | Projektionszustand initialisieren | lokale Werte |
| `frontend/map/overlay-data.js` · `OverlayData.hubFeatures` | sichtbare Facilities projizieren | State; unter eigenen sichtbaren idle Fahrzeugen filtern, Quelldaten erhalten |
| `frontend/map/overlay-data.js` · `OverlayData.vehicleFeatures` | eigene Fahrzeuge zu GeoJSON projizieren | serverseitiger Zustand/Farbe/Asset-ID; rein |
| `frontend/map/overlay-data.js` · `OverlayData.trafficFeatures` | öffentliche Bewegungen zu GeoJSON projizieren | gespeicherte Abschnitte/Farbe; rein, keine privaten Werte |
| `frontend/map/vehicle-assets.js` · `vehicleIconId` | stabile Modell/Rolle/Farbe-ID bilden | Assetregister und validierte Farbe; rein |
| `frontend/map/vehicle-assets.js` · `colorizeVehicleSvg` | validierte Firmenfarbe auf lokale SVG-Quelle anwenden | SVG/Farbe; rein, Masken oder expliziter Gesamt-Tint |
| `frontend/map/vehicle-assets.js` · `VehicleIconRegistry.constructor` | Map-Atlas-Abhängigkeiten halten | Map/Quellloader/Rasterizer injiziert |
| `frontend/map/vehicle-assets.js` · `VehicleIconRegistry.ensure` | benötigte Atlasvarianten deduplizieren | delegierte Registry-Loads |
| `frontend/map/vehicle-assets.js` · `VehicleIconRegistry.register` | genau eine Variante registrieren | Pending-/Atlas-Cache; wiederverwendet Promise |
| `frontend/map/vehicle-assets.js` · `VehicleIconRegistry.loadAndRegister` | Atlas-Ladevorgang orchestrieren | gemeinsame Quelle/Rasterizer/Map; disposed-Guard, explizites Fehlerlog |
| `frontend/map/vehicle-assets.js` · `VehicleIconRegistry.destroy` | Atlasbilder und Cache freigeben | Map-Bilder entfernen, spätere Loads ignorieren |
| `frontend/map/vehicle-groups.js` · `VehicleGroups.constructor` | Gruppenmarker-Ressourcen halten | Map/Navigate/ReducedMotion/Bildbinder |
| `frontend/map/vehicle-groups.js` · `VehicleGroups.update` | Gruppenmarker mit aktueller Projektion abgleichen | Gruppierungsfunktion/Map/DOM; keine Requests |
| `frontend/map/vehicle-groups.js` · `VehicleGroups.renderVisual` | repräsentatives Fahrzeug und Count rendern | Assetregister/DOM; stabile Signatur erhält Bilder |
| `frontend/map/vehicle-groups.js` · `VehicleGroups.destroy` | Gruppenmarker und Bilder freigeben | Bild-Leases, Marker, Popup |
| `frontend/map/world-map.js` · `WorldMap.constructor` | Map-Komponenten/Ressourcen verdrahten | injizierte Quellen/Kamera/Animator/Registries |
| `frontend/map/world-map.js` · `WorldMap.update` | aktuellen State auf Kartenkomponenten verteilen | Projektoren/Registry; delegierte Kartenupdates |
| `frontend/map/world-map.js` · `WorldMap.setCompanyColor` | eigene wirksame Farbe veröffentlichen | lokale Projektion/Update; keine Persistenz |
| `frontend/map/world-map.js` · `WorldMap.toggle` | Sichtbarkeit samt abhängigen Projektionen ändern | Map-Layer; Facilities wiederherstellen |
| `frontend/map/world-map.js` · `WorldMap.destroy` | alle Kartenressourcen freigeben | Animator/Marker/Atlas/Map |
| `frontend/ui/filters.js` · `cityFilter` | passende Stadtauswahl rendern | serverbasierter aktiver Kontext; keine Eignungsregeln |
| `frontend/ui/preserve-vehicle-images.js` · `matchVehicleImages` | wiederverwendbare Bildknoten finden | DOM-Vergleich; keine URLs laden/freigeben |
| `frontend/ui/vehicle-image.js` · `renderVehicleImage` | Modellasset und Rollenmetadaten rendern | Assetregister/DOM; kein Fetch |
| `frontend/views/company.js` · `renderCompany` | Unternehmensansicht zusammenstellen | Read-Modell/Subrenderer; DOM |
| `frontend/views/contracts.js` · `renderContracts` | aktive Stadtangebote/Leermeldung darstellen | View; DOM, keine zweite Kompatibilitätsregel |
| `frontend/views/contracts.js` · `renderQuote` | serverseitige Quote und Ergebnis darstellen | Quote/Kostenrenderer; DOM, keine Preisberechnung |
| `frontend/views/shop.js` · `renderOffer` | Katalogangebot mit Wartung statt Aggregatkosten darstellen | Katalogprojektion; reine Einheitenformatierung |
| `frontend/views/transports.js` · `renderTransportDetails` | gespeicherte Fahrt/Kosten darstellen | Transport/Kostenrenderer; keine historische Rekonstruktion |
| `frontend/controllers/preferences-controller.js` · `PreferencesController.constructor` | Preference-Abhängigkeiten und Requestlebenszeit halten | Request/Panel/Map/Notify/Page |
| `frontend/controllers/preferences-controller.js` · `PreferencesController.start` | Farbaktionen und Sichtbarkeitsrefresh anbinden | AbortSignal-Listener; delegierter Read |
| `frontend/controllers/preferences-controller.js` · `PreferencesController.refresh` | wirksame Preference laden | LatestRequest; alte Readantworten verwerfen |
| `frontend/controllers/preferences-controller.js` · `PreferencesController.save` | eine Farbschreiboperation ausführen | API-Port; serialisierter Write und LatestRequest |
| `frontend/controllers/preferences-controller.js` · `PreferencesController.publish` | bestätigte Farbe an Darstellung verteilen | View/CSS/Map/Panel; keine Speicherregel |
| `frontend/controllers/preferences-controller.js` · `PreferencesController.destroy` | Preference-Requests/Listener beenden | Cancel/Abort |
| `frontend/ui/company-preferences.js` · `renderCompanyPreferences` | validierte Palette und drei Vorschauen rendern | View/Assetrenderer; keine Requests |
| `frontend/ui/cost-breakdown.js` · `renderCostBreakdown` | gespeicherte Komponenten nachvollziehbar anzeigen | CostBreakdown/Formatter; keine Neuberechnung |
| `frontend/vehicle-color-assets.js` · `VehicleColorAssets.constructor` | Quell- und Variantencache besitzen | injizierter Quellloader |
| `frontend/vehicle-color-assets.js` · `VehicleColorAssets.source` | lokale Rollenquelle einmal laden und kolorieren | Loader/Assetregister/reine Farbtransformation |
| `frontend/vehicle-color-assets.js` · `VehicleColorAssets.key` | Variantenidentität bilden | registrierter Pfad/Rolle/validierte Farbe; rein |
| `frontend/vehicle-color-assets.js` · `VehicleColorAssets.peek` | vorhandene URL ohne neue Lease abfragen | lokaler Cache; nur Vorbereitungsphase |
| `frontend/vehicle-color-assets.js` · `VehicleColorAssets.acquire` | eine referenzgezählte Bild-Lease bereitstellen | Quelle/Blob-URL; Fehler/Dispose geben Referenz frei |
| `frontend/vehicle-color-assets.js` · `VehicleColorAssets.destroy` | alle Varianten freigeben | URLs widerrufen, späte Loads invalidieren |
| `frontend/vehicle-image-bindings.js` · `VehicleImageController.constructor` | DOM-Bindungen besitzen | injizierter Asset-Service |
| `frontend/vehicle-image-bindings.js` · `VehicleImageController.prepare` | Bildidentität vor DOM-Vergleich vorbereiten | Cache-Peek; kein Fetch |
| `frontend/vehicle-image-bindings.js` · `VehicleImageController.update` | Bild-Leases gegen aktuelle Knoten abgleichen | Asset-Service; Übergabe vor Freigabe, Identitätsprüfung späterer Antworten |
| `frontend/vehicle-image-bindings.js` · `VehicleImageController.imageKey` | Identität eines Bildknotens ableiten | Metadaten und Asset-Key; rein |
| `frontend/vehicle-image-bindings.js` · `VehicleImageController.destroy` | gebundene Leases freigeben | lokale Bindungen; späte Ergebnisse ignorieren |


## Audit-CLI und Grenzen

`scripts/audit_economy.matrix` enumeriert katalogbasierte Szenarien und
komponiert die Produktions-Domainauswertung. `main` verarbeitet CLI/CSV/JSON;
SQL bleibt in den Referenzrepositories. Die CLI schreibt keine Spielerwerte.
Im Review ergab sich keine verbleibende Vermischung von Tonnage, Tarif,
Kosten, HTTP und SQL. Die bekannten Front-/Seiten-Rasterwrapper besitzen
keine Lackiermasken; der Gesamt-Tint ist explizit in UI-Dokumentation und
Qualitätsbericht benannt. Es wurden keine Ersatzmasken oder Katalogwerte
heuristisch erfunden.


### Letzter Planabgleich: Vehicle-Cache

| Callable | Schicht / Zweck | Abhängigkeiten / Seiteneffekte |
| --- | --- | --- |
| `bootstrap.build_game_runtime` | Composition Root: validierende Vehicle-Quelle mit Laufzeitcache verdrahten | nur Konstruktion; Offline-Factories unverändert |
| `CachedVehicleCatalogue.__init__` | Repository-Dekorator: Referenzcache besitzen | injizierter Port, lokaler Lock, kein SQL |
| `CachedVehicleCatalogue.list_models` | Repository-Dekorator: eine erfolgreich validierte Revision wiederverwenden | einmaliger Portread und Log; parallele Reads serialisiert, Fehler nicht gecacht |

Expliziter Gegentest: Fehler beim ersten Read, danach erfolgreicher Retry
und acht konkurrierende Reads mit identischem immutable Ergebnis und ohne
weiteren Quellzugriff. Keine Vermischung mit Kosten- oder Marktregeln.


Zusätzlich wurden die indirekt durch die neue SQL-Projektion betroffenen
`SqliteVehicleCatalogue.list_models` und `_read_model` geprüft: Erstere
besitzt weiterhin ausschließlich read-only Schema-/Integritätsprüfung und
Modellprojektion, letztere die technische SQL-Zeile-zu-Domain-Zuordnung.
Der Wartungswert gelangt als explizite Spalte in den typisierten Konstruktor;
die fachliche Endlichkeits-/Nichtnegativitätsinvariante liegt im Domainwert.
Keiner der beiden Adapter enthält Tarif-, Mengen- oder Gewinnregeln.
