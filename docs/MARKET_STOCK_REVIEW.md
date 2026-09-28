# Review: drei sichtbare Angebote und gemeinsamer Vorrat

Stand: 28.09.2026, `feature/frontend-v2`. Grundlage: AGENTS.md,
CODING_STANDARDS.md und ADR 0008. Abschlusszahlen stehen ausschließlich im
aktuellen Abschnitt des Qualitätsberichts; Zwischenläufe sind keine Gesamtabnahme.

## Manuelle Prüfung der Verantwortlichkeiten

| Funktionen / Grenze | Inhaltliches Review |
| --- | --- |
| `StockPolicy.__post_init__`, `PreparedTemplate.__post_init__` | Unveränderliche Domainwerte; Mengenregeln, Identitäten und unbegrenzte Laufzeit; keine Infrastruktur. |
| `planning_vehicle`, `MarketDemandResolver.resolve` | Fahrzeug-Snapshot für einen künftigen Standort wird separat projiziert. Keine Mutation, Auszahlung oder vorzeitige Freigabe des echten Fahrzeugs. Katalogzugriff über injizierten Port. |
| `StockPlanningService.targets` | Indizes nach Fahrzeug, Stadt und Modell; kompatible, bereits geprüfte Bestände zählen. Verbrauch senkt den ungenutzten Modellvorrat des betreffenden Spielers. Kein SQL/Routing. |
| `StockTarget.key`, `order`, `choose` | Stabile Identitäten, fachliche Priorität, Rotation und Fortsetzung einer begonnenen Handelsbeziehung. Keine Zeitablauf-Lotterie. |
| `MarketTemplateService.materialize` | Berechnet nur den begrenzten Fehlbestand und verwendet unbenutzte gemeinsame Vorlagen bevorzugt. Die injizierte Factory erzeugt private IDs und Konditionen passend zur tatsächlichen Fahrzeugkapazität. |
| `MarketSelectionService.select` | Reine Begrenzung auf drei je Fahrzeug/Band aus serverseitig bestätigter Eignung; stabile Reihenfolge, keine Requests oder Neuberechnung der Frachtfähigkeit. |
| `StockPreparationBatch.process`, `_select`, `_ready`, `_runnable`, `_waiting`, `_result` | Orchestrierung einer Runde, nicht Implementierung eines Providers. Höchstens eine neue Relation; Negativevidenz/Backoff wird respektiert. Nach Await werden aktuelle Eingaben gelesen und Defizite neu berechnet. |
| `StockPublicationService.read` | Kurze konsistente Spieler-/Ankunftslesung, danach Kandidaten/Readiness außerhalb des Writers. Vollständiger Bestand und davon getrennte nutzbare Projektion. |
| `unchanged`, `publish` | Veröffentlichung besitzt ihre UoW. Lease, Bedarf, Flotte, Angebote, Ankünfte, gemeinsamer Bestand, Verbrauch, Weltrevision und Straßenbelege werden erneut abgeglichen; Templates, private Offers, Bindungen und Coverage committen gemeinsam. |
| `SqliteMarketStockStore.initialize`, `templates`, `used`, `bindings` | SQL und Dokumentmapping bleiben im Repository. Additive Infrastruktur derselben Datenbank; Stadt-/Modellindex, eindeutige Spieler-/Vorlagenidentität. |
| `add`, `issue`, `consume` | Immutable Vorlage, atomare persönliche Zuordnung und einmaliger Verbrauch. Membership-Prüfungen verwenden den eindeutigen SQL-Schlüssel statt vollständiger Ledger-Scans bei jeder Disposition. |
| `arrivals`, `cursor`, `pending`, `checkpoint` | Kompakte Ziel-/Zeitprojektion ohne Python-Geometrieobjekte; persistierte Rotation und Wiederaufnahme. Keine Veränderung des Transportlebenszyklus. |
| `MarketStockUpgradeRepository` einschließlich `_validate`, `_counts`, `_apply`, `_compare` | Explizites, ausschließlich offline verwendetes Verfahren. Neue Ausgabe, exakter Quellenabgleich, unveränderte Historie; unbekannte Schäden und Schemakollisionen werden abgewiesen. CLI besitzt Backup-/Pfadorchestrierung, das Repository besitzt SQL. |
| `GameService._commit_dispatch` | Verbrauch wurde in die bestehende finanzielle Transaktion aufgenommen; nachgelagerter Refill beeinflusst keinen erfolgreich abgeschlossenen Dispatch. |
| `MarketLifecycleService.published`, `prune_in_transaction`, `present` | Runtime liest vorbereitete Bestände, bewahrt ungenutzte Angebote und setzt Bedarf. Auswahlservice wird im Composition Root injiziert. Verborgene frühere Stadtbestände lösen keine ständige Neugenerierung aus. |
| `ContractMarketController` | Fahrzeugauswahl wird an dieselbe Markt-API weitergegeben. Gleichartige Requests werden zusammengefasst; Auswahlwechsel und Accountwechsel sperren verspätete Ergebnisse. Views bleiben ohne eigene Requests. |
| `DeferredMap`, `WorldMap`, `MapFocusController` | Renderer-Modul und WebGL starten nach der ersten Runtime-Darstellung. Der Adapter besitzt Frames, Erstellung, Listener und Cleanup; er behält den neuesten Zustand je Darstellungseigenschaft. Controller nutzen einen typisierten Kartenport statt nativer Renderer-Interna. Verzögerung, Fehler und Abmeldung sind gegengeprüft. |
| `VehicleImageController` | Ein eigener IntersectionObserver startet Farbkompositionen nur für sichtbare beziehungsweise unmittelbar benachbarte Bilder. Bereits gecachte Bilder übernehmen ihre Lease vor Freigabe der vorherigen DOM-Bindung; dadurch bleibt die Blob-URL beim Panelwechsel gültig. Entfernte Bindungen und verspätete Observer-/Ladeergebnisse werden verworfen; Observer und Bild-Leases werden beim Beenden freigegeben. |
| `DispatchRoutePlan.total_coordinates`, `matches_route` | Vergleich vollständig validierter unveränderlicher Straßenfakten ohne erneute Erzeugung eines Gesamtsnapshots pro Statuswechsel. Distanz, Dauer, Provider und jedes Koordinatenpaar müssen exakt übereinstimmen; abweichende Endpunkte werden nicht verschmolzen. |

Schema-/SQL-Ports sind weder in der Domain noch im Vorlagen-/Auswahlservice
importiert. Die Produktionsverdrahtung erfolgt in `bootstrap.py`. Die frühere
Market-Generator-/Batch-Zusammensetzung bleibt für isolierte Referenz- und
Regressionstests vorhanden; Produktion verwendet den Vorratsworker. Der
immutable Katalogcache gilt weiterhin je Prozesslebensdauer, Katalogaustausch
erfordert einen Neustart. Gespeicherte historische Transporte werden nie aus
dem aktuellen Katalog rekonstruiert.

## Geprüfte Einführung auf der Kopie

Eine isolierte, bereits reparierte repräsentative Quelle mit drei Spielern,
35 Fahrzeugen und 165 Transporten wurde über `upgrade_market_stock.py` mit
eigenständigem SQLite-Backup nach 1.2.0 übernommen. 42 zum Stichtag gültige
Altangebote behielten IDs und Konditionen und erhielten den Null-Ablaufwert.
Der vollständige Abgleich bestätigte unveränderte historische Transportdokumente.
Private Dateien liegen unter `data/market-stock-review-20260928-1/` und sind
nicht Teil von Git. Diese Ausgabe ist keine Live-Aktivierung.

Zusätzliche synthetische Gegenproben enthalten abgelaufene Angebote, widersprüchliche
Ankünfte, unbekannte Schemas, kaputte Guards, Ausgabefehler, doppelte Verwendung,
parallel gestartete Dispositionen, Rollback nach Verbrauch, Lease-Verlust sowie
Providerfehler und unvollständige Verbindungen. Jede neue konkrete Core-Funktion
hat einen expliziten Gegentest im Manifest. Die 14 Modellkontexte werden auch mit
einer vom aktuellen Modell abweichenden gespeicherten LKW-Kapazität geprüft.

## Abnahmegrenzen

Die Leistungsprobe verwendet die übernommene Kopie mit getrennter API und
laufendem Fixture-Worker. Sie protokolliert dessen Vorratsfortschritt,
mindestens 100 Reads je Ressource, p95/Maximum, JSON-Größe, kalte Browserstarts
und Geometriedownloads. Lokale Tile-Fixtures vermeiden automatisierte externe
Kartenabfragen. Desktop/Mobil/Tablet im Browser ersetzen keine echte iPad-Abnahme.
Die bestehende Wolfsburger Provider-Fixture und Hin-/Rückwegregression bleiben
Teil der Gesamtsuite; diese Erweiterung erzeugt keine neuen Live-Provider-Bulks.

Browserprüfungen warten bei vollständiger Dreier-Abdeckung auf alle neun Angebote;
ein erstes Teilergebnis darf bereits sichtbar sein. Anfahrts- und Energietests
stellen ihre unterschiedlichen beziehungsweise direkten Abholorte ausdrücklich
auf der isolierten Browserdatenbank her. Diese Testendpunkte sind nicht Teil der
Produktions-API und umgehen keine dortige Readiness-Prüfung.

Code, Tests und Dokumentation dürfen nach vollständiger lokaler Abnahme auf
den beauftragten Branch gepusht werden. Ein Live-Schemawechsel bleibt ein
gesonderter Betriebsschritt mit gestoppten Schreibern und frischem Backup,
siehe [Betriebsanleitung](RUNTIME_OPERATIONS.md).
