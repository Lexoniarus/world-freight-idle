# Market v2: Einzelreview der Core-Funktionen

Stand: 25.09.2026, Vergleich mit main `75e3d8a`. Jede unten aufgeführte neue
oder im Verhalten geänderte konkrete Funktion wurde anhand ihres Körpers
auf Zweck, Schicht, Abhängigkeiten und Seiteneffekte geprüft. Automatisch
erzeugte Dataclass-Methoden zählen nicht als eigene Implementierungen.
Das Function-Test-Manifest wird separat ausführbar geprüft.

## Befunde und Entscheidungen

- Marktfilter und Gewichtung liegen im Candidate-Service, Coverage-Schleifen
  ausschließlich im Coverage-Service; der Generator orchestriert drei Schritte.
- Factory-Fahrzeugwahl verwendet alle positiven Gewichte und bleibt getrennt
  vom Candidate-Maximalwert. Keine Fahrzeug-ID gelangt als Reservierung ins Offer.
- Pruning ist ein Lifecycle-Schritt in der Dispatch-UoW. Refill beginnt erst
  nach deren Commit und fängt ausschließlich Fehler seiner eigenen Transaktion.
- Fehlende Fahrzeugstandorte werden exakt aufgelöst. OwnedVehicle prüft die
  gespeicherte Facility-ID und schützt bestehende Snapshots vor Ersatz.
- Konstruktor-Docstrings und die Beschreibung der lazy Relation wurden ergänzt.
- Fehlende HTTP-Übersetzungen für Fahrzeugkatalog-Ausfälle und ungeklärte
  Altmodelle wurden als globale Handler ergänzt und mit API-Gegentests geprüft.
- Keine überprüfte Funktion vereint SQL/HTTP mit fachlicher Auswahl. Keine
  Views implementieren Klassen-/Scale-Regeln. Es verbleibt keine aus diesem
  Review erkannte vermischte Core-Verantwortlichkeit.

## app/api/v1/contracts.py

Schicht: API. Abhängigkeiten: GameService; HTTP-Schemas und Projektionen.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `list_contracts` | Return the active idle-vehicle city markets. | delegierte Use Cases, HTTP-Fehler; Zuständigkeit gewahrt |
| `get_contract` | Return one contract including real endpoint addresses. | delegierte Use Cases, HTTP-Fehler; Zuständigkeit gewahrt |
| `quote_contract` | Route saved coordinates and return a provider-backed truck quote. | delegierte Use Cases, HTTP-Fehler; Zuständigkeit gewahrt |
| `refresh_contracts` | Regenerate only the current active city markets. | delegierte Use Cases, HTTP-Fehler; Zuständigkeit gewahrt |

## app/api/v1/game_projection.py

Schicht: API. Abhängigkeiten: typisierte Domain-/Servicewerte.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `project_contract` | Expose an offer using the established v1 field names. | keine; JSON-Projektion; Zuständigkeit gewahrt |

## app/bootstrap.py

Schicht: Composition Root. Abhängigkeiten: konkrete Adapter und Service-Klassen.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `build_game_runtime` | Initialize only relational storage and shared application resources. | Objektaufbau; Runtime initialisiert SQLite; Zuständigkeit gewahrt |
| `build_market_generator` | Inject independent candidate, coverage and materialization services. | Objektaufbau; Runtime initialisiert SQLite; Zuständigkeit gewahrt |

## app/domain/contracts.py

Schicht: Domain. Abhängigkeiten: Snapshotwerte und Validierer.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `ContractOffer.__post_init__` | Reject invalid offer terms before an offer enters a use case. | keine; immutable Ergebniswerte; Zuständigkeit gewahrt |
| `ContractOffer.from_snapshot` | Promote generated immutable facts to a game-domain offer. | keine; immutable Ergebniswerte; Zuständigkeit gewahrt |
| `HistoricalContractSnapshot.from_offer` | Freeze accepted terms without inheriting the offer lifecycle. | keine; immutable Ergebniswerte; Zuständigkeit gewahrt |

## app/domain/game.py

Schicht: Domain. Abhängigkeiten: gespeicherter Fahrzeugzustand und Standortwert.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `OwnedVehicle.restore_location` | Restore an absent snapshot from the exact stored facility ID. | validate_dispatch: keine; restore/reposition: eigener Standort; Zuständigkeit gewahrt |
| `OwnedVehicle.validate_dispatch` | Validate whether this vehicle can accept one contract. | validate_dispatch: keine; restore/reposition: eigener Standort; Zuständigkeit gewahrt |
| `OwnedVehicle.reposition_within_city` | Reposition an idle vehicle within its city without time or costs. | validate_dispatch: keine; restore/reposition: eigener Standort; Zuständigkeit gewahrt |

## app/domain/market.py

Schicht: Domain. Abhängigkeiten: Profile, Relation und Fahrzeugwerte.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `MarketVehicle.__post_init__` | Require explicit identity, scale and usable owned capacity. | keine; Invarianten; Zuständigkeit gewahrt |
| `CompatibleVehicle.__post_init__` | Require a strictly positive selectable vehicle weight. | keine; Invarianten; Zuständigkeit gewahrt |
| `MarketCandidate.__post_init__` | Require coherent market facts and a selectable vehicle pool. | keine; Invarianten; Zuständigkeit gewahrt |

## app/domain/market_calculations.py

Schicht: Domain. Abhängigkeiten: Koordinaten, Relation oder numerische Argumente.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `great_circle_km` | Estimate distance deterministically from WGS84 facility points. | keine; deterministisch; Zuständigkeit gewahrt |
| `distance_band` | Use the V18 audit boundaries, including their upper endpoints. | keine; deterministisch; Zuständigkeit gewahrt |
| `evidence_weight` | Preserve sourced, confident, prioritized and exact NHM weighting. | keine; deterministisch; Zuständigkeit gewahrt |
| `shipment_tons` | Floor to hundredths without exceeding purchased vehicle capacity. | keine; deterministisch; Zuständigkeit gewahrt |

## app/domain/market_compatibility.py

Schicht: Domain. Abhängigkeiten: OwnedVehicle, Modell, Standort und Warenprofil.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `market_vehicle` | Freeze owned capacity while resolving only reference capabilities. | keine; reine Kompatibilität; Zuständigkeit gewahrt |
| `vehicle_suitability` | Combine class and scale weights without choosing a vehicle. | keine; reine Kompatibilität; Zuständigkeit gewahrt |
| `can_carry_offer` | Check current city, concrete tonnage and positive suitability. | keine; reine Kompatibilität; Zuständigkeit gewahrt |

## app/domain/market_profiles.py

Schicht: Domain. Abhängigkeiten: explizite Band-/Scale-/Klassenwerte.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `require_unit_weight` | Require a finite gameplay weight in the closed unit interval. | keine; Invarianten; Zuständigkeit gewahrt |
| `vehicle_scale_for_segment` | Resolve only explicitly supported catalogue segments. | keine; Invarianten; Zuständigkeit gewahrt |
| `TransportCapability.__post_init__` | Reject unknown classes and invalid suitability. | keine; Invarianten; Zuständigkeit gewahrt |
| `DistanceLoadProfile.__post_init__` | Require a supported band and a positive ordered load interval. | keine; Invarianten; Zuständigkeit gewahrt |
| `VehicleScaleProfile.__post_init__` | Reject unsupported scales and invalid suitability. | keine; Invarianten; Zuständigkeit gewahrt |
| `NhmMarketProfile.__post_init__` | Require complete, unique profiles and positive economic terms. | keine; Invarianten; Zuständigkeit gewahrt |

## app/domain/market_terms.py

Schicht: Domain. Abhängigkeiten: gespeicherte Generierungswerte.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `OfferMarketContext.__post_init__` | Reject inconsistent distance, equipment and monetary facts. | keine; Invarianten; Zuständigkeit gewahrt |
| `OfferMarketContext.validate_tonnage` | Require shipment capacity and rounded cargo value consistency. | keine; Invarianten; Zuständigkeit gewahrt |

## app/domain/vehicles.py

Schicht: Domain. Abhängigkeiten: Energie- und Capability-Werte.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `VehicleModel.__post_init__` | Require a usable speed limit and typed energy specification. | keine; Modellinvarianten; Zuständigkeit gewahrt |

## app/repositories/market_profile_reader.py

Schicht: Repository. Abhängigkeiten: read-only SQLite und immutable Profile.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `read_market_profiles` | Validate all profile rows and require every operative NHM node. | SELECT; kein Schreiben; Zuständigkeit gewahrt |

## app/repositories/snapshot_mapping.py

Schicht: Repository. Abhängigkeiten: Snapshotfelder und Domainkonstruktoren.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `load_offer` | Restore one complete offer using its retained reference facts. | keine Katalogreads; Deserialisierung; Zuständigkeit gewahrt |
| `load_historical_contract` | Restore agreed transport terms independently of offer availability. | keine Katalogreads; Deserialisierung; Zuständigkeit gewahrt |
| `load_market_context` | Restore optional historical V2 terms without reference lookups. | keine Katalogreads; Deserialisierung; Zuständigkeit gewahrt |

## app/repositories/vehicle_catalogue.py

Schicht: Repository. Abhängigkeiten: read-only SQLite und VehicleModel.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `SqliteVehicleCatalogue.list_models` | Validate the reference schema and project complete offers. | SELECT; Connection-Cleanup; Zuständigkeit gewahrt |
| `SqliteVehicleCatalogue._read_model` | Reject incomplete or invalid gameplay values before projection. | SELECT; Connection-Cleanup; Zuständigkeit gewahrt |
| `read_transport_capabilities` | Project validated capability rows without model heuristics. | SELECT; Connection-Cleanup; Zuständigkeit gewahrt |

## app/repositories/world_catalogue.py

Schicht: Repository. Abhängigkeiten: read-only SQLite und WorldSnapshot.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `validate_world_schema` | Validate the NHM-capable schema and cross-table invariants. | SELECT; strukturierte Referenzdiagnose; Zuständigkeit gewahrt |
| `read_world_snapshot` | Read one complete revision and report the routability boundary. | SELECT; strukturierte Referenzdiagnose; Zuständigkeit gewahrt |

## app/services/contract_factory.py

Schicht: Service. Abhängigkeiten: Candidate, injizierter RNG und reine Tonnagefunktion.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `ContractFactory.build` | Create one typed immutable simulated contract snapshot. | RNG fortschreiben; Snapshot erzeugen; Zuständigkeit gewahrt |

## app/services/game.py

Schicht: Service. Abhängigkeiten: UoW-, Router-, Katalogports, Entities und Marktservice.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `GameService.__init__` | Wire player-scoped orchestration to injected service ports. | Abhängigkeiten binden; keine Spielmutation; Zuständigkeit gewahrt |
| `GameService.refresh_market` | Delegate city market lifecycle to its transactional service. | Marktrefresh an Lifecycle delegieren; Zuständigkeit gewahrt |
| `GameService.quote_contract` | Route snapshot coordinates and calculate simulated economics. | Routing außerhalb von Schreibtransaktionen; vor/nach Await validieren; Zuständigkeit gewahrt |
| `GameService.dispatch` | Validate and start one real-time delivery. | Dispatch-UoW öffnen/committen; danach separate Refill-Transaktion; Zuständigkeit gewahrt |
| `GameService._commit_dispatch` | Revalidate and atomically reserve the truck and funds. | Atomaren Dispatch koordinieren; nur innerhalb der geöffneten UoW; Zuständigkeit gewahrt |
| `GameService.reconcile_arrival` | Settle due active transports once, before refreshing the market. | Fällige Settlement-UoW committen; danach Marktrefill; Zuständigkeit gewahrt |
| `GameService.list_contracts` | Reconcile arrivals and return retained/refilled city markets. | Ankunft und Retention/Refill delegieren; Zuständigkeit gewahrt |
| `GameService.refresh_contracts` | Explicitly regenerate offers only for current active cities. | Ankunft und erzwungenen Marktrefresh delegieren; Zuständigkeit gewahrt |
| `GameService.contract_choices` | Expose server-side vehicle choices for already read offers. | Eignungsprojektion delegieren; keine Reservierung; Zuständigkeit gewahrt |
| `GameService.get_contract` | Return one available offer with historical endpoint values. | Aktuellen Markt lesen, Angebot suchen; Zuständigkeit gewahrt |
| `GameService._validate_dispatch` | Delegate vehicle-specific dispatch invariants to the entity. | Entity-/Kompatibilitätsprüfung; fehlenden Standort nur am gelesenen Objekt ergänzen; Zuständigkeit gewahrt |
| `GameService._calculate_quote` | Calculate economics and energy from current purchased values. | Domain-Pricing und Fahrtplanung mit gespeicherten Fahrzeugwerten komponieren; Zuständigkeit gewahrt |

## app/services/market.py

Schicht: Service. Abhängigkeiten: Candidate-, Coverage-Service und Factory.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `MarketGenerator.generate` | Return retained and newly materialized offers with diagnostics. | delegierte RNG-Auswahl; keine Transaktion; Zuständigkeit gewahrt |

## app/services/market_candidates.py

Schicht: Service. Abhängigkeiten: Katalogports, TradeNetwork, Kompatibilitätsfunktionen.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `MarketCandidateService.__init__` | Keep reference ports and initially empty revision indexes. | Referenzread und abgeleitete Index-Caches; Zuständigkeit gewahrt |
| `MarketCandidateService.reference` | Refresh derived reference indexes only for a changed revision. | Referenzread und abgeleitete Index-Caches; Zuständigkeit gewahrt |
| `MarketCandidateService.resolve_fleet` | Resolve idle models explicitly, preserving purchased capacities. | Referenzread und abgeleitete Index-Caches; Zuständigkeit gewahrt |
| `MarketCandidateService.build` | Generate active origins against the complete destination index. | Referenzread und abgeleitete Index-Caches; Zuständigkeit gewahrt |
| `MarketCandidateService._candidate` | Combine a trade profile, distance and compatible vehicle weights. | Referenzread und abgeleitete Index-Caches; Zuständigkeit gewahrt |
| `MarketCandidateService.eligible_ids` | Return compatible owned IDs without reserving a vehicle. | Referenzread und abgeleitete Index-Caches; Zuständigkeit gewahrt |
| `MarketCandidateService.structurally_current` | Require a live routable relation and a selectable distance band. | Referenzread und abgeleitete Index-Caches; Zuständigkeit gewahrt |

## app/services/market_coverage.py

Schicht: Service. Abhängigkeiten: Candidates, Retained Offers, injizierter RNG.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `CityCoverage.record` | Count one retained or planned offer using the same dimensions. | nur Planungscounter und RNG; kein Offer/SQL; Zuständigkeit gewahrt |
| `CityCoverage.rank` | Prefer unused relations, cargo nodes, then destination cities. | nur Planungscounter und RNG; kein Offer/SQL; Zuständigkeit gewahrt |
| `CityCoverage.add_candidate` | Count planned coverage before the factory creates an offer. | nur Planungscounter und RNG; kein Offer/SQL; Zuständigkeit gewahrt |
| `MarketCoverageService.plan` | Compose independent city plans and compact coverage diagnostics. | nur Planungscounter und RNG; kein Offer/SQL; Zuständigkeit gewahrt |
| `MarketCoverageService._plan_city` | Apply facility coverage first and then fill available bands. | nur Planungscounter und RNG; kein Offer/SQL; Zuständigkeit gewahrt |
| `MarketCoverageService._select` | Choose by diversity rank then candidate weight and record it. | nur Planungscounter und RNG; kein Offer/SQL; Zuständigkeit gewahrt |

## app/services/market_lifecycle.py

Schicht: Service. Abhängigkeiten: UoW-Port, Generator, Scope und Uhr.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `MarketLifecycleService.refresh` | Read fleet, retain valid work and fill coverage atomically. | Marktpersistenz und strukturierte Diagnosen; Zuständigkeit gewahrt |
| `MarketLifecycleService.prune_in_transaction` | Prune within the caller's dispatch transaction, without refill. | Marktpersistenz und strukturierte Diagnosen; Zuständigkeit gewahrt |
| `MarketLifecycleService._retained` | Keep only fresh, structurally current, currently drivable offers. | Marktpersistenz und strukturierte Diagnosen; Zuständigkeit gewahrt |
| `MarketLifecycleService._store` | Persist changed offers inside the caller-owned transaction. | Marktpersistenz und strukturierte Diagnosen; Zuständigkeit gewahrt |
| `MarketLifecycleService.refill_after_commit` | Keep a committed trip successful even when separate refill fails. | Marktpersistenz und strukturierte Diagnosen; Zuständigkeit gewahrt |
| `MarketLifecycleService.present` | Attach transient eligibility without changing offer snapshots. | Marktpersistenz und strukturierte Diagnosen; Zuständigkeit gewahrt |

## app/services/market_scope.py

Schicht: Service. Abhängigkeiten: OwnedVehicle-Snapshots und WorldCatalogue-Port.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `MarketScopeResolver.resolve` | Return stable distinct city UIDs even for multiple idle trucks. | nur optionaler Referenzread; Zuständigkeit gewahrt |

## app/services/trade_network.py

Schicht: Service. Abhängigkeiten: immutable Facilities und NHM-Profile.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `TradeNetwork.__init__` | Index routable destinations without computing origin relations. | nur revisionsgebundene Indizes und Diagnose; Zuständigkeit gewahrt |
| `TradeNetwork.options_for` | Resolve and cache trade options for one requested origin. | nur revisionsgebundene Indizes und Diagnose; Zuständigkeit gewahrt |
| `TradeNetwork._build_trade_options` | Build compatible NHM trades from one origin without SQL access. | nur revisionsgebundene Indizes und Diagnose; Zuständigkeit gewahrt |

## app/main.py

Schicht: Composition Root / HTTP-Fehlergrenze. Abhängigkeiten: FastAPI und
benannte Domainfehler. Die Handler lesen oder verändern keinen Spielzustand.

| Callable | Fachlicher Zweck | Seiteneffekte / Review |
| --- | --- | --- |
| `create_app` | Adapter und globale Fehlerübersetzung registrieren | App-Aufbau; keine Marktauswahl; Zuständigkeit gewahrt |
| `vehicle_catalogue_error` | Katalogausfall als sichere HTTP-503-Antwort projizieren | Nur JSONResponse; Zuständigkeit gewahrt |
| `unresolved_vehicle_model` | Expliziten Zuordnungsbedarf als HTTP 409 melden | Nur JSONResponse; keine Modellheuristik; Zuständigkeit gewahrt |

Geprüfte konkrete Core-Callables: **81**.
