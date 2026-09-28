# Einzelreview: tatsächliche Abholanfahrt

Stand: 25.09.2026, `feature/frontend-v2`, Vergleich mit `fbeca0b`.
Jede neue oder semantisch geänderte benannte Core-Funktion wurde anhand ihres
AST-Diffs und der vollständigen Implementierung einzeln geprüft. Dazu zählen
private Methoden; Typwerte ohne eigene Methoden sind separat erfasst.
Zeilenzahl und erfolgreiche Tools waren keine Reviewkriterien.

## Python-Core

| Funktion | Fachlicher Zweck / Schicht | Abhängigkeiten und Seiteneffekte / Ergebnis |
| --- | --- | --- |
| `RouteSnapshot.__post_init__` | Domain: valide immutable Straßenroute | Nur Wertvalidatoren; keine Effekte. Unverändert aus transports verschoben. |
| `DispatchRoutePlan.__post_init__` | Domain: vollständige, stadtkompatible Abfahrts-/Abholwerte | Nur Snapshots; wirft bei fehlenden Koordinaten oder fehlender notwendiger Anfahrt. Keine Planung/I/O. |
| `DispatchRoutePlan.total_route` | Domain: Gesamtroutenwert aus geordneten Straßenabschnitten | Summiert Providerwerte, verbindet Geometrien, entfernt nur identischen Verbindungspunkt. Keine Kosten oder Uhr. |
| `DispatchRoutePlan.legs` | Domain: öffentliche geordnete Bewegungsabschnitte | Nur eigene immutable Werte; projiziert Grenzen, Providerzeit und Geometrie ohne private Werte. |
| `plan_dispatch_journey` | Domain: Energiepläne entlang der Straßenabschnitte komponieren | Ruft pure plan_journey je Abschnitt auf, verschiebt Intervalle, führt Füllstand fort; keine Reservierung. |
| `calculate_price` | Domain: Auftragswirtschaft berechnen | Nur übergebene Tonnen, Fracht-/Anfahrtskilometer und gespeicherte Raten; einmalige Grundbeträge. Keine Katalogwerte nachladen. |
| `ActiveTransport.__post_init__` | Domain: konsistente historische Transportwerte schützen | Ergänzt Prüfung der Routen-/Auftragssnapshots; kein Routing, Settlement oder Mapping. |
| `DispatchPlanningService.route` | Service: geordnete Routinganfragen orchestrieren | Injizierter TruckRouter; externe Reads für Anfahrt/Fracht, keine Unit of Work oder SQLite. |
| `DispatchPlanningService._route_between` | Service: eine validierte Routinganfrage übersetzen | Prüft Koordinaten und ruft Router-Port; kein Preis/Fahrzeugzustandswechsel. |
| `DispatchPlanningService.quote` | Service: Quote aus aktuellem Fahrzeugcheckpoint komponieren | Vergleicht Start, delegiert Journey/Preis an pure Funktionen; keine Reads/Writes im Speicher. Orchestrierung ist der gemeinsame Zweck. |
| `GameService.__init__` | Service: Abhängigkeiten verdrahten | Injizierten Planner speichern; keine neue Domainberechnung. |
| `GameService.quote_contract` | Service: konsistente Quote anfordern | Liest Angebot/Fahrzeug, delegiert Routing außerhalb Write-UoW, liest erneut, delegiert Kalkulation und protokolliert. Bestehende Arrival-Reconciliation bleibt explizit. |
| `GameService._calculate_quote` | Service: revalidierte Fahrzeugwahl an Planung übergeben | Bestehende Eignungsprüfung plus Planner-Delegation; keine eigenen Formeln. Fehlender Standort wird über bestehenden Resolver ergänzt. |
| `GameService._commit_dispatch` | Service: atomaren Annahmevorgang koordinieren | Liest/verifiziert Angebot, Fahrzeug und Checkpoint in offener UoW; Domain reserviert/debitiert, Repository speichert, Lifecycle pruned. Kein Routing/Refill in dieser Funktion. |
| `GameService._build_trip` | Service: historische Transportanlage zusammenstellen | Nur übergebene Quote/Auftrag/Zeit und neue UUID; keine DB oder Katalogrekonstruktion. |
| `build_player_service` | Composition Root: konkrete Adapter verdrahten | Baut Planner mit Runtime-Router; keine Fachberechnung. Test-Router bleibt injizierbar. |
| `load_route` | Repository: Straßen-Snapshot decodieren | Wandelt Koordinaten in immutable Tuples, Konstruktor validiert; kein Routing. |
| `load_dispatch_route` | Repository: optionalen historischen Routenplan decodieren | Nur Snapshot-Mapper/Konstruktoren, fehlender Plan bleibt None. Keine Rekonstruktion aus Referenzwerten. |
| `load_transport` | Repository: vollständigen Transport decodieren | Delegiert neue optionale Komponente; bestehende Hülle und Historie bleiben erhalten. |
| `project_traffic_row` | Repository: gespeicherte Fahrt auf öffentlichen Port abbilden | Ergänzt öffentliche RouteLeg-Werte; keine Preis-/Energieoffenlegung. Keine Simulation im Reader. |
| `project_dispatch_route` | API: Routenwerte in HTTP-Felder projizieren | Nur Standort-/Dataclassprojektion und historischer Fallback; kein Routing und keine Stadtmarktregeln. |
| `project_quote` | API: Quote darstellen | Nutzt gemeinsamen Routenprojektor; keine Kalkulation in HTTP-Schicht. |
| `project_transport` | API: eigene Transportdaten darstellen | Nutzt gemeinsamen Routenprojektor; bestehende zeitabhängige Domainprojektion bleibt delegiert. |
| `project_traffic` | API: öffentlichen Verkehr darstellen | Ergänzt ausschließlich öffentliche Abschnitte, bestehende strukturierte Logs; keine privaten Economics/Energieprofile. |

Alle 24 Funktionen haben einen Eintrag im expliziten Function-Test-Manifest.
`RouteLeg`, `ContractQuote`, `SharedTransport` und der optionale Transportwert
wurden auf Immutable-/Typgrenzen geprüft; automatisch erzeugte Dataclass-
Methoden führen keine zusätzliche Geschäftslogik ein. OwnedVehicle.start_trip
und arrive wurden als unveränderte Nachbarn geprüft: Abfahrtscheckpoint bleibt
bei Reservierung erhalten, erst Ankunft ersetzt Facility/Snapshot gemeinsam.

## Frontend

| Funktion | Zweck / Grenze | Ergebnis |
| --- | --- | --- |
| `journeyProgress` | Gespeicherten Zeitplan interpolieren | Liefert absolute Kilometer zusätzlich zur Fraction; keine neue Planung. |
| `transportProgress` | Laufende Abschnittsphase ableiten | Vergleicht dieselben Kilometergrenzen wie die Karte; keine Persistenz. |
| `phaseLabel` | Deutsche Statusbeschriftung | Fahrabschnitt ergänzt, Energiehalte/Ankunft bleiben prioritär. |
| `prepareTransportRoute` | Kartengeometrien vorbereiten | Cacht jede Abschnittsgeometrie einmal; keine Requests. |
| `transportRoutePose` | Position im aktiven Abschnitt interpolieren | Straßenkilometer bestimmen Leg/Fraction, Alttransporte nutzen alte Gesamtroute. |
| `OverlayData.update` | Kartendaten/Geometriecaches aktualisieren | Start-Snapshot ergänzt; Cachebereinigung unverändert. |
| `OverlayData.trafficFeatures` | Fahrzeug-Features darstellen | Eigene/fremde Fahrzeuge verwenden denselben Pose-Helfer; keine Wirtschaftslogik. |
| `renderContractDetails` | Gewählten Start, Abholung, Ziel darstellen | Nutzt Quote beziehungsweise ausgewähltes Fahrzeug, keine Routing-/Eignungsregeln. |
| `renderQuote` | Autoritative Kosten/Zeit/Strecken anzeigen | Zusätzliche Kilometerwerte sind reine Serverprojektionen. |
| `renderTransportDetails` | Fahrtablauf und Kennzahlen anzeigen | Zeigt Checkpoint und Abholung getrennt; keine zweite Dispatch-Aktion. |
| `progressDisplay` | Fortschrittslabel und Restzeit aufbereiten | Delegiert an zentrale Interpolation, keine zweite Zeitplanung. |
| `renderVehicle` | Flottenstatus darstellen | Nutzt zentrale Phasenlabels einschließlich Anfahrt; keine eigene Bewegung. |

Ergebnis: Keine Funktion verbindet SQLite mit Fachberechnung oder HTTP mit
Planung. GameService wurde um Berechnungen erleichtert; Marktgenerator und
Coverage wurden nicht erweitert. Die gemeinsame Planung und Projektion
verhindern abweichende private/öffentliche Abschnittsgrenzen. Die abschließenden
Prüfergebnisse und Daten-/Browsergrenzen stehen im [Qualitätsbericht](../QUALITY_REPORT.md).
