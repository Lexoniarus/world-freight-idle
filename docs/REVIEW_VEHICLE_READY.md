# Reviewkorrekturen und Vehicle-Ready: Einzelreview

Stand: 27.09.2026; Basis `e49e5fa`. Direkter bestehender Arbeitsbranch.
Status: implementiert / gezielte Prüfungen bestanden / Gesamtabnahme offen.

## Ergebnis der Verantwortungsprüfung

- Worker verantwortet nur Scheduling, Trace, Lifecycle und Fehlererholung. Bedarf und aktuelle Coverage liegen im injizierten Batch-Service.
- Batchplanung besitzt einen konsistenten lokalen Transaktionskontext; Provider-Awaits erfolgen erst nach dessen Ende. Generation-Fencing schützt vor veralteten Ergebnissen.
- Preparation projiziert Delivery und individuelle Approaches. VehicleCoverage plant Mengenbedarf; die Factory behält Materialisierung, Tarif und Tonnage. Der Generator delegiert.
- Cache-Schlüssel bleiben im Repository. Bind prüft alle Referenzen und besitzt eine eigene transaktionale Grenze. Repository-Ersetzung schützt eigenständige Aufrufe.
- Analytics-Skalarvalidierung und Mapping bleiben im Repository, fachliche Aggregation im Service, JSON-Projektion in der API. Die Prüfung ergänzte explizite SQL-Skalarvalidierung.
- EconomyAuditService enthält nur Referenzprojektion und deterministische Szenarien; konkrete SQLite-Verdrahtung liegt in Bootstrap und Dateiausgabe in der CLI.
- Cleanup versucht alle Ressourcen; AggregateError meldet Originalfehler erst danach. Disposed wird vor Freigaben gesetzt. JSDoc-only Änderungen ändern kein Verhalten.

## Einzelne Python-Funktionen

Die Liste ist gegen den Basiscommit per AST abgeglichen. Jede Zeile wurde auf Zweck, Schicht, unmittelbare Abhängigkeiten und Seiteneffekte geprüft. Die konkreten Core-Funktionen besitzen explizite Manifest-Gegentests; die Portdeklaration ist gesondert erkennbar. Zeilenzahl ist kein Abnahmekriterium.

### `app/api/v1/analytics_projection.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `project_analytics` | Preserve field names, flattened metrics and historical nulls. | `asdict` | Service-Aufruf und HTTP-Projektion; kein SQL/Provider |

### `app/api/v1/company.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `get_analytics` | Reconcile due arrivals, then use the independent read model. | `Depends`, `HTTPException`, `build_analytics_service`, `build_analytics_service(request.app.state.game, user['id']).analyze`, `game.now`, `game.reconcile_arrival`, `project_analytics`, `router.get`, `str`, `validate_scope` | Service-Aufruf und HTTP-Projektion; kein SQL/Provider |

### `app/api/v1/contracts.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `list_contracts` | Return the active idle-vehicle city markets. | `Depends`, `game.list_contracts`, `project_market`, `router.get` | Service-Aufruf und HTTP-Projektion; kein SQL/Provider |
| `project_market` | Translate authorized offer projections and vehicle coverage to HTTP. | `HTTPException`, `asdict`, `game.market_presentation`, `project_contract`, `str` | Service-Aufruf und HTTP-Projektion; kein SQL/Provider |
| `refresh_contracts` | Regenerate only the current active city markets. | `Depends`, `game.refresh_contracts`, `project_market`, `router.post` | Service-Aufruf und HTTP-Projektion; kein SQL/Provider |

### `app/bootstrap.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `build_market_generator` | Inject independent candidate, coverage and materialization services. | `ContractFactory`, `MarketCandidateService`, `MarketCoverageService`, `MarketGenerator`, `VehicleCoverageService` | Adapter/Services verdrahten; keine fachliche Berechnung |
| `build_market_preparation` | Bind production routing infrastructure to one player's offers. | `MarketPreparationService`, `SqliteOfferRouteStore` | Adapter/Services verdrahten; keine fachliche Berechnung |
| `build_preparation_worker` | Assemble owned preparation without initializing player state. | `MarketLifecycleService`, `MarketPreparationBatchService`, `MarketPreparationWorker`, `SqliteGameUnitOfWork`, `build_market_preparation` | Adapter/Services verdrahten; keine fachliche Berechnung |
| `build_preparation_worker.batch` | Compose one player's preparation without changing state. | `MarketLifecycleService`, `MarketPreparationBatchService`, `SqliteGameUnitOfWork`, `build_market_preparation` | Adapter/Services verdrahten; keine fachliche Berechnung |
| `build_economy_audit` | Compose reproducible audits from read-only reference catalogues. | `EconomyAuditService`, `SqliteVehicleCatalogue`, `SqliteWorldCatalogue`, `random.Random` | Adapter/Services verdrahten; keine fachliche Berechnung |

### `app/domain/market_preparation.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `preparation_generation` | Fingerprint relevant demand without copying entire facility trees. | `repr`, `repr((fleet, facts, references)).encode`, `sha256`, `sha256(repr((fleet, facts, references)).encode()).hexdigest`, `tuple` | Keine; reine Werte/Invarianten (Port ohne Implementierung) |
| `required_relations` | Prioritize deduplicated approaches before changing delivery choices. | `tuple` | Keine; reine Werte/Invarianten (Port ohne Implementierung) |

### `app/domain/routing_readiness.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `RoutingRelation.__post_init__` | Reject incoherent ready and negative routing records. | `ValueError`, `relation_identity`, `require_finite`, `require_identity` | Keine; reine Werte/Invarianten (Port ohne Implementierung) |

### `app/domain/state_ports.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `TransactionBoundary.transaction` | Abstrakte Transaktionsgrenze deklarieren |  | Keine; reine Werte/Invarianten (Port ohne Implementierung) |

### `app/repositories/analytics.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `validate_scalars` | Reject malformed SQL scalars before constructing typed read values. | `PersistenceError`, `require_finite`, `require_identity`, `require_integer` | Keine; Skalarvalidierung/Mapping |
| `map_ongoing` | Map validated booked amounts without historical reconstruction. | `AnalyticsOngoing`, `validate_scalars` | Keine; Skalarvalidierung/Mapping |
| `validate_row` | Validate extracted fields without decoding the JSON document. | `AnalyticsTransport`, `PersistenceError`, `any`, `isinstance`, `math.isfinite`, `validate_scalars` | Keine; Skalarvalidierung/Mapping |
| `SqliteAnalyticsReader.read` | Select scalar values only; the all-time totals require history. | `AnalyticsData`, `AnalyticsStatus`, `PersistenceError`, `db.commit`, `db.execute`, `db.execute("SELECT COUNT(*) AS vehicles, COALESCE(SUM(status='idle'),0) AS idle_vehicles, COALESCE(SUM(status='enroute'),0) AS enroute_vehicles, COUNT(DISTINCT CASE WHEN status='idle' THEN json_extract(location_snapshot, '$.data.city.city_uid') END) AS active_cities FROM owned_vehicles WHERE user_id=?", (self.user_id,)).fetchone`, `db.execute('SELECT cash, completed, reputation FROM player_states WHERE user_id = ?', (self.user_id,)).fetchone`, `dict`, `len`, `map_ongoing`, `self.database.connect`, `status.update`, `tuple`, `validate_row`, `validate_scalars` | SQLite-Lesen |

### `app/repositories/routing_readiness.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `SqliteRoutingReadinessStore.get` | Read the currently published revision of a directed relation. | `RouteReference`, `RoutingRelation`, `connection.execute`, `connection.execute('SELECT * FROM routing_relations WHERE relation_id=?', (relation_id,)).fetchone`, `dict`, `self.database.connect`, `values.pop` | SQLite-Lesen |
| `SqliteRoutingReadinessStore.publish` | Atomically fence the writer and publish metrics with readiness. | `ValueError`, `asdict`, `conn.execute`, `conn.execute('SELECT 1 FROM routing_leases WHERE subject=? AND owner=? AND expires_at>?', (relation.reference.relation_id, owner, now)).fetchone`, `json.dumps`, `self.database.connect`, `self.database.transaction` | Atomare SQLite-Mutation, äußere UoW beibehalten |
| `SqliteOfferRouteStore.replace` | Replace bindings atomically, joining the market transaction. | `connection.execute`, `connection.executemany`, `self.database.connect`, `self.database.transaction` | Atomare SQLite-Mutation, äußere UoW beibehalten |

### `app/services/analytics.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `summarize` | Compute additive performance and defined ratios. | `AnalyticsSummary`, `len`, `sum` | Keine; reine Aggregation/Dimension |
| `dimension_value` | Select a supported historical dimension without dynamic fields. |  | Keine; reine Aggregation/Dimension |
| `breakdown` | Group history without joining today's vehicle models. | `(labels or {}).get`, `AnalyticsGroup`, `dimension_value`, `groups.items`, `groups.setdefault`, `groups.setdefault(value, []).append`, `sorted`, `summarize`, `tuple` | Keine; reine Aggregation/Dimension |
| `AnalyticsService.__init__` | Inject a consistent scalar reader. |  | Injizierte Abhängigkeiten lokal binden |
| `AnalyticsService.analyze` | Read once and aggregate without invoking a write repository. | `(start + timedelta(days=offset)).isoformat`, `AnalyticsDay`, `AnalyticsResult`, `LOGGER.info`, `breakdown`, `by_day.get`, `by_day.setdefault`, `by_day.setdefault(day, []).append`, `datetime.combine`, `datetime.combine(start, datetime.min.time(), UTC).timestamp`, `datetime.fromtimestamp`, `datetime.fromtimestamp(now, UTC).date`, `datetime.fromtimestamp(row.arrives_at, UTC).date`, `datetime.fromtimestamp(row.arrives_at, UTC).date().isoformat`, `datetime.fromtimestamp(rows[0].arrives_at, UTC).date`, `datetime.min.time`, `dimension_value`, `int`, `len`, `range`, `self.reader.read`, `series.append`, `start.isoformat`, `sum`, `summarize`, `timedelta`, `today.isoformat`, `tuple`, `validate_scope`, `vehicle_labels` | Read-Port und Log |

### `app/services/economy_audit.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `EconomyAuditService.__init__` | Inject read-only catalogue ports and deterministic randomness. |  | Injizierte Abhängigkeiten lokal binden |
| `EconomyAuditService.matrix` | Enumerate unchanged low, generated median and high scenarios. | `audit_vehicle`, `min`, `self._rows`, `self.vehicles.list_models`, `self.world.read`, `tuple` | Injizierter RNG/Kataloglesung |
| `EconomyAuditService._rows` | Enumerate compatibility and unchanged scenarios for one profile. | `EconomyMatrixRow`, `audit_economy_case`, `range`, `self.rng.random`, `sorted`, `tuple`, `vehicle_suitability` | Injizierter RNG/Kataloglesung |
| `audit_vehicle` | Project catalogue reference facts into an audit-only vehicle context. | `MarketVehicle`, `VehicleCostProfile`, `vehicle_scale_for_segment` | Keine; reine Referenzprojektion/Summary |
| `summarize_economy` | Summarize reference profitability separately from cashflow. | `EconomyAuditSummary`, `len`, `min`, `sum` | Keine; reine Referenzprojektion/Summary |

### `app/services/game.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `GameService.contract_choices` | Expose server-side vehicle choices for already read offers. | `self.market_lifecycle.present` | Lokales Lesen/Delegation; kein Provider-Await |
| `GameService.market_presentation` | Read authorized offers and diagnostics in one local transaction. | `MarketPresentation`, `self.contract_choices`, `self.preparation_status`, `self.unit_of_work.transaction`, `self.vehicle_coverage`, `tuple` | Lokales Lesen/Delegation; kein Provider-Await |
| `GameService.vehicle_coverage` | Delegate actual per-vehicle coverage diagnostics. | `self.market_lifecycle.vehicle_diagnostics` | Lokales Lesen/Delegation; kein Provider-Await |

### `app/services/market.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `MarketGenerator.generate` | Return retained and newly materialized offers with diagnostics. | `ContractOffer.from_snapshot`, `self.candidates.build`, `self.coverage.plan`, `self.factory.build`, `self.vehicle_coverage.extend`, `tuple` | Delegierte Planung/Factory; keine SQL-/HTTP-Details |

### `app/services/market_coverage.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `MarketCoverageService.plan` | Compose independent city plans and compact coverage diagnostics. | `CoveragePlan`, `diagnostics.append`, `selected.extend`, `self._plan_city`, `tuple` | Lokaler Plan und injizierter RNG; keine Materialisierung |
| `MarketCoverageService._plan_city` | Apply facility coverage first and then fill available bands. | `CityCoverage`, `CoverageDiagnostic`, `coverage.add_candidate`, `coverage.record`, `len`, `selected.append`, `self._select`, `sorted`, `sum`, `tuple` | Lokaler Plan und injizierter RNG; keine Materialisierung |

### `app/services/market_lifecycle.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `MarketLifecycleService.present` | Attach transient eligibility and separate route references. | `AvailableContract`, `ValueError`, `any`, `result.append`, `self.generator.candidates.eligible_ids`, `self.generator.candidates.resolve_fleet`, `self.preparation.eligible`, `self.preparation.references.get`, `self.preparation.retained`, `self.unit_of_work.repository.list_vehicles`, `tuple` | Lokales Lesen/Delegation; kein Provider-Await |
| `MarketLifecycleService.vehicle_diagnostics` | Read actual vehicle coverage without scheduling provider work. | `self._vehicle_diagnostics_in_transaction`, `self.unit_of_work.transaction` | Lokales Lesen/Delegation; kein Provider-Await |
| `MarketLifecycleService._vehicle_diagnostics_in_transaction` | Project consistent cached evidence in the active transaction. | `self.generator.candidates.build`, `self.generator.candidates.resolve_fleet`, `self.generator.vehicle_coverage.diagnose`, `self.preparation.ready_candidates`, `self.scope.resolve`, `self.unit_of_work.repository.list_offers`, `self.unit_of_work.repository.list_vehicles`, `tuple` | Lokales Lesen/Delegation; kein Provider-Await |

### `app/services/market_preparation.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `MarketPreparationService.__init__` | Inject global readiness and player-scoped reference storage. |  | Injizierte Abhängigkeiten lokal binden |
| `MarketPreparationService.prepare_publication` | Enqueue demand and expose vehicle-ready structural candidates. | `preparation_generation`, `required_relations`, `self._ready_candidates`, `self.clock`, `self.demand_state`, `self.jobs.request`, `self.transactions.transaction`, `tuple` | Transaktionale Bedarf-/Referenzmutation über Ports; kein HTTP |
| `MarketPreparationService.ready_candidates` | Expose only candidates with a usable delivery and vehicle start. | `required_relations`, `self._ready_candidates`, `self.demand_state`, `tuple` | Lokales Lesen/Delegation; kein Provider-Await |
| `MarketPreparationService._ready_candidates` | Project one consistent local evidence set into ready contexts. | `restrict_candidate`, `self.ready_context`, `tuple` | Keine; immutable Kontextprojektion |
| `MarketPreparationService.ready_context` | Map delivery and approach evidence to immutable vehicle context. | `VehicleReadyCandidate`, `references.get`, `tuple` | Keine; immutable Kontextprojektion |
| `MarketPreparationService.preparable_candidates` | Skip deterministic delivery or approach failures during planning. | `required_relations`, `restrict_candidate`, `result.append`, `self.readiness.current`, `tuple` | Lokales Lesen/Delegation; kein Provider-Await |
| `MarketPreparationService.demand_state` | Read stable routing facts including stale negative evidence. | `RelationDemandState`, `self.readiness.current`, `self.readiness.fingerprint` | Lokales Lesen/Delegation; kein Provider-Await |
| `MarketPreparationService.bind` | Own atomic binding, joining a surrounding market transaction. | `self._bind_in_transaction`, `self.transactions.transaction` | Transaktionale Bedarf-/Referenzmutation über Ports; kein HTTP |
| `MarketPreparationService._bind_in_transaction` | Validate and replace references inside the active transaction. | `ValueError`, `bindings.append`, `self.readiness.ready`, `self.references.replace`, `tuple` | Transaktionale Bedarf-/Referenzmutation über Ports; kein HTTP |

### `app/services/preparation_batch.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `MarketPreparationBatchService.__init__` | Inject state reads, pure market steps and transactional refresh. |  | Injizierte Abhängigkeiten lokal binden |
| `MarketPreparationBatchService.plan` | Read refreshed publication and determine still-needed relations. | `self._plan_in_transaction`, `self.preparation.transactions.transaction` | Lokale UoW/Refresh/Planung ohne externe Awaits |
| `MarketPreparationBatchService._plan_in_transaction` | Assemble cached demand within the active local transaction. | `Counter`, `Counter((relation.status if relation else 'unchecked_or_stale' for relation in states.values())).items`, `PreparationBatchPlan`, `bool`, `dict.fromkeys`, `len`, `self.candidates.build`, `self.candidates.resolve_fleet`, `self.coverage.plan`, `self.preparation.jobs.status`, `self.preparation.preparable_candidates`, `self.preparation.readiness.current`, `self.preparation.ready_candidates`, `self.refresh`, `self.repository.list_vehicles`, `self.scope.resolve`, `sorted`, `states.values`, `tuple`, `vehicles.extend` | Lokale UoW/Refresh/Planung ohne externe Awaits |
| `MarketPreparationBatchService.process` | Prepare outside transactions and evaluate fresh publication. | `PreparationBatchResult`, `self._ready`, `self.plan`, `self.preparation.prepare_batch` | Provider-Await zwischen zwei lokalen Transaktionen |
| `MarketPreparationBatchService._ready` | Require every planned delivery and approach to be ready. | `all`, `required_relations`, `self.preparation.readiness.ready` | Readiness-Lesen |

### `app/services/preparation_worker.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `MarketPreparationWorker.__init__` | Inject scheduling storage and player lifecycle composition. |  | Injizierte Abhängigkeiten lokal binden |
| `MarketPreparationWorker._run` | Recover the complete iteration, including scheduler failures. | `LOGGER.exception`, `asyncio.sleep`, `self._iteration` | Scheduling/Trace/Log/abbrechbare Sleeps und gefencetes Finish |
| `MarketPreparationWorker._iteration` | Run one due job in its own trace and persist retry state. | `LOGGER.exception`, `asyncio.sleep`, `background_trace`, `self.clock`, `self.jobs.finish`, `self.jobs.next_player`, `self.jobs.status`, `self.process` | Scheduling/Trace/Log/abbrechbare Sleeps und gefencetes Finish |
| `MarketPreparationWorker.process` | Execute a typed batch and persist its fenced scheduling result. | `LOGGER.info`, `dict`, `self.batches`, `self.batches(user_id).process`, `self.clock`, `self.jobs.finish` | Scheduling/Trace/Log/abbrechbare Sleeps und gefencetes Finish |

### `app/services/routing_readiness.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `RoutingReadinessService.current` | Return current ready or negative evidence without any HTTP call. | `relation_identity`, `replace`, `self.fingerprint`, `self.store.get`, `self.store.payload` | Read-Port, kein HTTP |
| `RoutingReadinessService._validate` | Resolve truck endpoints and validate one provider route. | `RoutePayload`, `RouteReference`, `RoutingAttempt`, `RoutingRelation`, `WorldScope`, `any`, `get_trace_id`, `relation_identity`, `scope.facility`, `self._failure`, `self._validate`, `self.anchors.resolve`, `self.clock`, `self.fingerprint`, `self.router.route`, `self.store.append_attempt`, `self.store.publish`, `self.store.renew`, `self.world.read`, `uuid.uuid4` | Provider über Ports, gefencete Persistenz |
| `RoutingReadinessService._failure` | Persist diagnostic failure and its bounded retry schedule. | `RouteReference`, `RoutingAttempt`, `RoutingRelation`, `get_trace_id`, `relation_identity`, `self.clock`, `self.fingerprint`, `self.store.append_attempt`, `self.store.publish`, `uuid.uuid4` | Diagnostik/Status über Repository-Port |

### `app/services/vehicle_coverage.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `restrict_candidate` | Preserve evidence weights while narrowing eligible contexts. | `max`, `replace` | Keine; reine Eignungs-/Coverageprojektion |
| `vehicle_candidates` | Select feasible generation contexts whose shipments fit the target. | `any`, `restrict_candidate`, `tuple` | Keine; reine Eignungs-/Coverageprojektion |
| `vehicle_offers` | Count actual tonnage only with ready delivery and vehicle approach. | `any`, `can_carry_offer`, `profiles.get`, `tuple` | Keine; reine Eignungs-/Coverageprojektion |
| `VehicleCoverageService.extend` | Plan smaller generation contexts first to share fitting offers. | `CoveragePlan`, `any`, `candidates_for_trade`, `list`, `max`, `selected.extend`, `self.coverage.plan`, `sorted`, `tuple`, `vehicle_candidates`, `vehicle_offers` | Coverage-RNG lokal |
| `VehicleCoverageService.diagnose` | Report actual coverage against structurally possible targets. | `VehicleCoverageDiagnostic`, `len`, `sorted`, `sum`, `tuple`, `vehicle_candidates`, `vehicle_offers`, `zip` | Keine; reine Eignungs-/Coverageprojektion |
| `candidates_for_trade` | Recover all compatible contexts before generation-capacity narrowing. | `tuple` | Keine; reine Eignungs-/Coverageprojektion |

### `scripts/audit_economy.py`

| Funktion | Einziger Zweck | Unmittelbare Abhängigkeiten | Seiteneffekte / Grenze |
|---|---|---|---|
| `project_row` | Flatten a typed scenario into the unchanged CSV columns. | `asdict`, `values.pop`, `values.update` | Keine; CSV-Mapping |
| `main` | Write local CSV and summary artifacts for review. | `(options.output / 'matrix.csv').open`, `(options.output / 'summary.json').write_text`, `Path`, `Path(__file__).resolve`, `SystemExit`, `argparse.ArgumentParser`, `asdict`, `build_economy_audit`, `build_economy_audit(Path(__file__).resolve().parents[1], 20260925).matrix`, `csv.DictWriter`, `dict.fromkeys`, `json.dumps`, `list`, `options.output.mkdir`, `parser.add_argument`, `parser.parse_args`, `print`, `project_row`, `summarize_economy`, `writer.writeheader`, `writer.writerows` | CLI-Dateiausgabe/Exitstatus |

Erfasste Python-Callables: 69 (einschließlich der abstrakten Portdeklaration).

## Frontend-Verhaltensänderungen

| Funktion | Zweck / Abhängigkeiten | Seiteneffekte und SRP-Befund |
|---|---|---|
| `releaseAll` | Geordnete Cleanup-Callbacks | Versucht alle, aggregiert danach Originalfehler; keine Navigation |
| `reportCleanup` | Fehlerdarstellung für Cleanup | Loggt AggregateError; überschreibt keinen Workflowfehler |
| `GameApplication.destroy` | Ressourcenbesitz beenden | Disposed zuerst; delegierte Freigaben, idempotent |
| `GameApplication.logout` | Logoutablauf koordinieren | API, Cleanup-Bericht, Redirect; keine Freigabedetails |
| `GameApplication.navigateTo` | Navigation orchestrieren | Aktuelle Map-Projektion und Auswahl synchronisieren, Generation prüfen |
| `GameApplication.synchronizeMapSelection` | Entityauswahl auf Karte abbilden | Nur Auswahl; keine Kamera-/HTTP-Regel |
| `bootstrap` / `pagehide` | Lebenszyklus-Grenze | Primärfehler erhalten; beide Cleanup-Callbacks ausführen |
| `WorldMap.destroy` | Kartenressourcen beenden | Alle Freigaben bis native map.remove; idempotent |
| `WorldMap.update` / `bindMapEvents` / `select` / `toggle` | Kartenprojektion aktualisieren | Vehicle-Kontext an Opportunity-Renderer weiterreichen; keine Eignungsberechnung |
| `Opportunities.update` / Klickcallback | Offer-Gruppen darstellen | Count aus bereits gefiltertem Pool; bestehende Fahrzeugauswahl im Link erhalten |
| `GameSync.publish` / `updateMap` | Read-Modell an Darstellung verteilen | Eigener Projektionsschritt; keine Kamerabewegung |
| `marketVehicle` | Explizites eigenes idle Fahrzeug finden | Rein; keine automatische Auswahl |
| `marketMapState` | Fahrzeugmarkt auf MapState projizieren | Rein; nur serverseitige eligible_vehicle_ids, Überblick bleibt unverändert |
| `CityContextController.selectRoute` / `update` | Fahrzeugstadt/URL synchronisieren | Keine automatische Ersatzwahl; inaktive Auswahl leeren |
| `renderContracts` / `filterContracts` | Sichtbare Angebote projizieren | DOM beziehungsweise reine Filter; keine Requests/Kompatibilitätsheuristik |
| `GameState.replaceContracts` | Marktantwort übernehmen | Shared Pool und Coverage zusammen speichern |
| `ContractMarketController.loadList` | Aktuelle Marktantwort publizieren | Stale-Response-/Abort-Schutz bleibt bestehen |

Die übrigen Änderungen an öffentlichen Methoden von GameApplication, WorldMap und Controllern sind JSDoc-Verträge. Konstruktoren beschreiben injizierte Abhängigkeiten; Parameter, Rückgaben und nullable Werte wurden geprüft. Die folgende Methodeninventur listet auch diese Einzelverträge. Keine neuen any-Ersatztypen oder Suppressions.


## Öffentliche Frontend-Methodenverträge

### `frontend/application.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `GameApplication.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert |  |
| `GameApplication.start` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `component?.start`, `this.panel.render`, `Promise.all`, `this.panel.loadDetails`, `this.sync.refreshGameState`, `this.navigateTo` |
| `GameApplication.navigateTo` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `this.focus?.cancel`, `this.actions.cancelQuote`, `this.city?.selectRoute`, `this.layers?.select`, `this.panel.selectRoute`, `this.sync.updateMap`, `this.map?.setPreview`, `this.synchronizeMapSelection`, `this.focus?.select`, `this.contractMarket.refresh`, `this.analytics?.refresh` |
| `GameApplication.synchronizeMapSelection` | Synchronize vehicle, transport or offer selection. | `this.map?.select`, `path.startsWith`, `path.split("/").at`, `path.split` |
| `GameApplication.logout` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `this.api.request`, `reportCleanup`, `this.destroy`, `this.redirect` |
| `GameApplication.destroy` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `releaseAll`, `[
        this.scheduler,
        this.focus,
        this.preferences,
        this.city,
        this.layers,
        this.analytics,
        this.managementInput,
        this.input,
        this.sheet,
        this.router,
        this.actions,
        this.panel,
        this.contractMarket,
        this.sync,
        this.map,
        this.notifications,
        this.state,
        this.assets,
        this.api,
      ].map`, `component?.destroy` |

### `frontend/map/world-map.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `WorldMap.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `OverlayData`, `maplibregl.Popup`, `maplibregl.setWorkerUrl`, `maplibregl.Map`, `provider.style`, `Math.max`, `VehicleIconRegistry`, `assets?.source.bind`, `MapCamera`, `VehicleAnimator`, `this.drawTraffic`, `this.map.touchZoomRotate.disableRotation`, `VehicleGroups`, `Opportunities`, `this.map.addControl`, `maplibregl.AttributionControl`, `maplibregl.NavigationControl`, `this.bindMapEvents` |
| `WorldMap.bindMapEvents` | Register map interaction handlers owned by the native map. | `this.map.on`, `console.warn`, `this.notify`, `this.initializeOverlays`, `this.drawTraffic`, `this.opportunities.update`, `this.selectFeature(event).catch`, `this.selectFeature`, `this.map.queryRenderedFeatures`, `this.map.getCanvas`, `this.updateFacilityHover` |
| `WorldMap.initializeOverlays` | Install overlay layers after the map becomes ready. | `addOverlayLayers`, `this.map.getContainer().setAttribute`, `this.map.getContainer`, `this.update`, `Object.entries`, `this.toggle`, `this.setPreview`, `this.select`, `this.setPreset`, `this.animator.start` |
| `WorldMap.update` | Synchronize the map read model and rendered overlays. | `this.overlays.update`, `this.setSourceData`, `this.overlays.locationFeatures`, `this.overlays.routeFeatures`, `this.updateSelectedRoute`, `selectedLocations`, `this.drawTraffic`, `this.opportunities.update`, `this.syncVehicleIcons`, `(state.traffic ?? []).map`, `state.vehicles.map` |
| `WorldMap.setCompanyColor` | Refresh own vehicle variants using the effective company color. | `this.update` |
| `WorldMap.updateFacilityHover` | Project facility hover information into the owned popup. | `FACILITY_HOVER_LAYERS.has`, `this.hoverPopup.remove`, `document.createElement`, `Number`, `content.append`, `this.hoverPopup.setLngLat(lngLat).setDOMContent(content).addTo`, `this.hoverPopup.setLngLat(lngLat).setDOMContent`, `this.hoverPopup.setLngLat` |
| `WorldMap.syncVehicleIcons` | Load current vehicle variants and ignore obsolete completions. | `this.vehicleIcons.ensure`, `this.overlays.setVehicleIcons`, `this.drawTraffic` |
| `WorldMap.drawTraffic` | Render current interpolated vehicle poses and groups. | `this.isHidden`, `this.now`, `this.overlays.vehicleFeatures`, `this.overlays.multiplayerVehicleFeatures`, `own.filter`, `this.groups.update`, `this.updateFacilityProjection`, `this.setSourceData`, `ungrouped.filter` |
| `WorldMap.updateFacilityProjection` | Publish facility visibility only when its rendered occupancy changes. | `this.overlays.hubFeatures`, `JSON.stringify`, `this.setSourceData` |
| `WorldMap.setGrouping` | Apply grouping preference to vehicle presentation. | `this.drawTraffic` |
| `WorldMap.setPreset` | Apply a route-specific visual preset. | `this.map.setPaintProperty`, `this.drawTraffic` |
| `WorldMap.setSourceData` | Update a registered GeoJSON source when available. | `(this.map.getSource(name))?.setData`, `this.map.getSource` |
| `WorldMap.selectFeature` | Translate a map hit into navigation or group interaction. | `this.map.queryRenderedFeatures`, `new Map(
        hits
          .filter((item) =>
            [...OWN_VEHICLE_LAYERS, ...MULTIPLAYER_VEHICLE_LAYERS].includes(item.layer.id),
          )
          .map((item) => [item.properties.key, item]),
      ).values`, `Map`, `hits
          .filter((item) =>
            [...OWN_VEHICLE_LAYERS, ...MULTIPLAYER_VEHICLE_LAYERS].includes(item.layer.id),
          )
          .map`, `hits
          .filter`, `[...OWN_VEHICLE_LAYERS, ...MULTIPLAYER_VEHICLE_LAYERS].includes`, `this.groups.showList`, `(
        this.map.getSource("hubs")
      ).getClusterExpansionZoom`, `this.map.getSource`, `this.map.easeTo`, `nearestLongitude`, `this.reducedMotion`, `OWN_VEHICLE_LAYERS.includes`, `this.navigate`, `encodeURIComponent`, `MULTIPLAYER_VEHICLE_LAYERS.includes`, `this.notify` |
| `WorldMap.setPreview` | Display or clear the current quote geometry. | `this.map.setLayoutProperty`, `this.setSourceData`, `previewFeatures` |
| `WorldMap.select` | Synchronize the selected vehicle, transport or offer overlay. | `this.drawTraffic`, `this.updateSelectedRoute`, `this.opportunities.update`, `this.setSourceData`, `selectedLocations`, `this.map.setPaintProperty` |
| `WorldMap.updateSelectedRoute` | Render the route associated with the current selection. | `this.overlays.state.transports.find`, `this.setSourceData`, `this.overlays
        .routeFeatures()
        .features.filter`, `this.overlays
        .routeFeatures` |
| `WorldMap.focusRoute` | Delegate one route fit to the camera primitives. | `this.camera.fitRoute`, `unwrapRoute`, `routeGeometry` |
| `WorldMap.focusFleet` | Delegate a fleet-position fit to the camera primitives. | `this.overlays.fleetCoordinates`, `this.now`, `this.camera.fitCoordinates`, `this.notify` |
| `WorldMap.toggle` | Change one overlay visibility and redraw dependent markers. | `Boolean`, `this.map.getLayer`, `this.map.setLayoutProperty`, `this.drawTraffic`, `this.opportunities.update` |
| `WorldMap.destroy` | Release every map resource once, aggregating cleanup failures. | `releaseAll`, `this.animator.destroy`, `this.groups.destroy`, `this.opportunities.destroy`, `this.hoverPopup.remove`, `this.vehicleIcons.destroy`, `this.map.remove` |

### `frontend/controllers/analytics-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `AnalyticsController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `LatestRequest` |
| `AnalyticsController.refresh` | Load the current analytics selection with stale-response protection. | `this.pending.start`, `URLSearchParams`, `view.url.searchParams.get`, `view.url.searchParams.has`, `params.set`, `this.panel.render`, `this.request`, `pending.isCurrent` |
| `AnalyticsController.destroy` | Release owned resources and reject late updates. | `this.pending.cancel` |

### `frontend/controllers/auth-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `AuthController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `AbortController` |
| `AuthController.start` | Mount the authentication view and attach its controls. | `this.root.replaceChildren`, `renderAuth`, `requiredElement("#login-tab").addEventListener`, `requiredElement`, `this.setMode`, `requiredElement("#register-tab").addEventListener`, `requiredElement("#auth-form").addEventListener`, `event.preventDefault`, `this.submitCredentials` |
| `AuthController.setMode` | Present login or registration without replacing the form. | `requiredElement`, `tab.classList.toggle`, `Boolean`, `tab.setAttribute`, `String`, `requiredElement("#password").setAttribute`, `requiredElement("#submit-auth").replaceChildren`, `icon` |
| `AuthController.setBusy` | Prevent mode changes and duplicate submissions while authenticating. | `requiredElement("#" + id).toggleAttribute`, `requiredElement` |
| `AuthController.submitCredentials` | Submit credentials exclusively to the same-origin API. | `this.setBusy`, `requiredElement`, `this.api.request`, `JSON.stringify`, `Object.fromEntries`, `FormData`, `this.redirect` |
| `AuthController.destroy` | Release handlers and abort an in-flight authentication request. | `this.listeners.abort`, `this.api.destroy` |

### `frontend/controllers/city-context-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `CityContextController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `Map`, `LatestRequest`, `this.update` |
| `CityContextController.start` | Register owned listeners for this controller. | `this.state.addEventListener` |
| `CityContextController.update` | Synchronize the explicit vehicle city and available city labels. | `cityLocations`, `this.known.set`, `activeCityIds`, `marketVehicle`, `vehicleCity`, `this.route.searchParams.delete`, `this.writeCity`, `[...this.known.values()].sort`, `this.known.values`, `a.city.localeCompare`, `this.view.cities.filter`, `active.includes` |
| `CityContextController.writeCity` | Normalize only this route's city parameter. | `url.searchParams.set`, `url.searchParams.delete`, `window.history.replaceState` |
| `CityContextController.selectRoute` | Resolve and normalize the route-local city selection. | `this.pending.start`, `url.searchParams.delete`, `url.searchParams.get`, `this.state.data?.vehicles.find`, `url.pathname.startsWith`, `url.pathname.split`, `url.searchParams.has`, `resolveLegacyCity`, `this.request`, `encodeURIComponent`, `this.known.set`, `this.known.has`, `pending.isCurrent`, `this.notify`, `url.searchParams.set`, `marketVehicle`, `this.update`, `this.writeCity` |
| `CityContextController.destroy` | Release owned resources and reject late updates. | `this.pending.cancel`, `this.state.removeEventListener` |

### `frontend/controllers/contract-market-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `ContractMarketController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `LatestRequest` |
| `ContractMarketController.start` | Register owned listeners for this controller. |  |
| `ContractMarketController.refresh` | Load offers required by the current route or visible map layer. | `this.currentUrl`, `path.startsWith`, `path.split`, `this.ordersVisible`, `tasks.push`, `this.loadList`, `this.pending.cancel`, `this.loadDetail`, `this.detailPending.cancel`, `Promise.all` |
| `ContractMarketController.forceRefresh` | Replace the market for an explicit user refresh. | `this.currentUrl`, `this.loadList` |
| `ContractMarketController.loadList` | Load and publish the current shared offer pool. | `this.pending.start`, `this.request`, `request.isCurrent`, `this.state.replaceContracts`, `this.notify` |
| `ContractMarketController.loadDetail` | Load one selected offer without accepting stale responses. | `this.detailPending.start`, `this.request`, `encodeURIComponent`, `request.isCurrent`, `this.state.replaceContractDetail`, `this.notify` |
| `ContractMarketController.destroy` | Release owned resources and reject late updates. | `this.pending.cancel`, `this.detailPending.cancel` |

### `frontend/controllers/game-actions.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `GameActions.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `LatestRequest` |
| `GameActions.handle` | Route a UI action to a single-purpose handler. | `this.navigate`, `this.map?.focusFleet`, `this.map?.focusRoute`, `this.focusTransport`, `this.panel.loadDetails`, `this.refresh`, `this.selectVehicle`, `this.calculateQuote`, `this.runMutation`, `this.purchaseVehicle`, `this.dispatchTransport`, `this.refreshMarket`, `this.logout`, `actions[action]` |
| `GameActions.focusTransport` | Show the route for an active transport if it still exists. | `this.state.data?.transports.find`, `this.map?.focusRoute` |
| `GameActions.cancelQuote` | Cancel the old selection's quote without blocking the new selection. | `this.quoteRequest.cancel` |
| `GameActions.selectVehicle` | Select a vehicle and discard economics belonging to its predecessor. | `this.cancelQuote`, `this.panel.view.url.searchParams.set`, `window.history.replaceState`, `this.map?.setPreview`, `this.panel.render` |
| `GameActions.calculateQuote` | Request a quote and publish it only for the current selection. | `this.panel.view.url.pathname.split("/").at`, `this.panel.view.url.pathname.split`, `this.quoteRequest.start`, `this.panel.render`, `this.request`, `JSON.stringify`, `request.isCurrent`, `this.map?.setPreview`, `this.focus?.quote`, `this.notify` |
| `GameActions.runMutation` | Serialize writes and reconcile even if a response was lost. | `this.panel.render`, `operation`, `this.state.afterMutation`, `this.notify` |
| `GameActions.purchaseVehicle` | Purchase one server-priced vehicle model. | `this.request`, `JSON.stringify`, `this.notify` |
| `GameActions.dispatchTransport` | Dispatch the selected vehicle and follow the resulting transport. | `this.panel.view.url.pathname.split("/").at`, `this.panel.view.url.pathname.split`, `requiredElement`, `this.request`, `JSON.stringify`, `this.notify`, `this.state.afterMutation`, `this.navigate` |
| `GameActions.refreshMarket` | Replace the player's available contract market. | `this.contractMarket.forceRefresh`, `this.notify` |
| `GameActions.destroy` | Invalidate pending quotes and suppress late action results. | `this.cancelQuote` |

### `frontend/controllers/game-sync.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `GameSync.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `this.publish` |
| `GameSync.start` | Register owned listeners for this controller. | `this.state.addEventListener` |
| `GameSync.publish` | Publish a state revision to HUD, panel and map. | `requiredElement`, `money`, `String`, `document.querySelector`, `current.vehicles.filter`, `this.notify`, `this.updateMap`, `path.startsWith`, `this.map?.select`, `path.split`, `this.panel.render` |
| `GameSync.updateMap` | Project current route eligibility without moving the camera. | `this.map?.update`, `marketMapState` |
| `GameSync.refreshGameState` | Refresh player state and display connection failures. | `this.state.refresh`, `requiredElement`, `notice.replaceChildren` |
| `GameSync.updateProgress` | Update live transport progress from the server clock. | `this.updateEnergyMeters`, `document.querySelectorAll("[data-phase-trip]").forEach`, `document.querySelectorAll`, `this.state.data.transports.find`, `element.getAttribute`, `progressDisplay`, `this.state.now`, `document.querySelectorAll("[data-trip]").forEach`, `requiredElement`, `element.querySelector` |
| `GameSync.updateEnergyMeters` | Update only meter values and text, preserving vehicle image nodes. | `document.querySelectorAll("[data-energy-vehicle]").forEach`, `document.querySelectorAll`, `this.state.data.vehicles.find`, `element.getAttribute`, `this.state.data.transports.find`, `energyDisplay`, `this.state.now`, `element.querySelector`, `requiredElement` |
| `GameSync.destroy` | Release owned resources and reject late updates. | `this.state.removeEventListener` |

### `frontend/controllers/input-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `InputController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `AbortController` |
| `InputController.start` | Attach one listener per interaction type. | `this.page.addEventListener`, `this.handleClick`, `this.handleChange`, `this.handleKey`, `this.handleImage` |
| `InputController.handleClick` | Route links and action buttons, preserving modified native link clicks. | `event.target.closest`, `event.preventDefault`, `this.navigate`, `link.getAttribute`, `button.hasAttribute`, `this.actions.handle`, `button.getAttribute` |
| `InputController.handleChange` | Update a presentation preference selected by the player. | `this.actions.selectVehicle` |
| `InputController.handleImage` | Reveal loaded photos or retain their illustration after a network failure. | `image.hasAttribute`, `image.closest` |
| `InputController.handleKey` | Close the topmost overlay using Escape and restore its focus. | `this.page.querySelector`, `layers.querySelector("summary").focus`, `layers.querySelector`, `this.navigate` |
| `InputController.destroy` | Remove all delegated listeners. | `this.listeners.abort` |

### `frontend/controllers/layer-state-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `LayerStateController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `JSON.parse`, `storage.getItem`, `Object.keys` |
| `LayerStateController.effective` | Resolve current preset visibility with saved overrides. |  |
| `LayerStateController.select` | Apply the layer preset for a navigation intent. | `presetFor`, `this.apply` |
| `LayerStateController.set` | Persist and apply one layer visibility choice. | `this.persist`, `this.apply` |
| `LayerStateController.reset` | Clear overrides for the current preset. | `this.persist`, `this.apply` |
| `LayerStateController.setGrouping` | Persist and apply vehicle grouping preference. | `this.persist`, `this.apply` |
| `LayerStateController.persist` | Store account-local layer preferences. | `this.storage.setItem`, `JSON.stringify` |
| `LayerStateController.apply` | Synchronize layer controls and map presentation. | `Object.entries`, `this.effective`, `this.map?.toggle`, `document.querySelector`, `this.map?.setGrouping`, `this.map?.setPreset` |
| `LayerStateController.destroy` | Complete the lifecycle of this resource-free controller. |  |

### `frontend/controllers/management-input.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `ManagementInput.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `AbortController` |
| `ManagementInput.start` | Register owned listeners for this controller. | `this.page.addEventListener`, `this.change`, `this.click` |
| `ManagementInput.change` | Translate management input changes into controller actions. | `this.layers.set`, `this.market.refresh`, `this.layers.setGrouping`, `URL`, `url.searchParams.set`, `url.searchParams.delete`, `this.navigate` |
| `ManagementInput.click` | Dispatch a management button action. | `event.target.closest("[data-action]")?.getAttribute`, `event.target.closest`, `this.layers.reset`, `this.market.refresh`, `this.analytics.refresh`, `document
        .querySelector("#game")
        ?.classList.toggle`, `document
        .querySelector`, `this.page.querySelector`, `nav.classList.toggle`, `event.target
        .closest("button")
        ?.setAttribute`, `event.target
        .closest`, `String`, `nav.classList.contains` |
| `ManagementInput.destroy` | Release owned resources and reject late updates. | `this.lifetime.abort` |

### `frontend/controllers/map-focus-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `MapFocusController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `this.flush` |
| `MapFocusController.start` | Register owned listeners for this controller. | `this.state.addEventListener`, `this.map?.map.on` |
| `MapFocusController.cancel` | Invalidate delayed work before asynchronous navigation resolution. |  |
| `MapFocusController.select` | Record only a genuine route or visible-filter change. | `["city", "status", "model", "search"]
        .map((name) => `${name}=${url.searchParams.get(name) ?? ""}`)
        .join`, `["city", "status", "model", "search"]
        .map`, `url.searchParams.get`, `URL`, `this.flush` |
| `MapFocusController.flush` | Fulfil a pending intent without establishing a polling camera follower. | `focusCoordinates`, `this.state.now`, `this.map.camera.fitCoordinates` |
| `MapFocusController.quote` | A current user-requested quote supersedes the endpoint framing. | `this.map?.focusRoute` |
| `MapFocusController.destroy` | Release owned resources and reject late updates. | `this.cancel`, `this.state.removeEventListener`, `this.map?.map.off` |

### `frontend/controllers/mobile-sheet.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `MobileSheet.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `this.cycleHeight`, `this.startDrag`, `this.finishDrag` |
| `MobileSheet.start` | Attach sheet controls once for the application lifetime. | `Object.entries`, `this.handle.addEventListener` |
| `MobileSheet.cycleHeight` | Advance the three accessible sheet sizes. | `this.setHeight` |
| `MobileSheet.startDrag` | Begin a captured pointer gesture. | `this.handle.setPointerCapture` |
| `MobileSheet.finishDrag` | Snap a completed gesture without applying its synthetic click twice. | `Math.abs`, `event.preventDefault`, `this.setHeight` |
| `MobileSheet.setHeight` | Apply a sheet height in dynamic viewport units. | `this.panel.style.setProperty`, `document.querySelector`, `document.querySelector("#game")?.classList.toggle`, `this.handle.setAttribute` |
| `MobileSheet.destroy` | Release pointer and click listeners. | `Object.entries`, `this.handle.removeEventListener` |

### `frontend/controllers/notifications.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `Notifications.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `this.show.bind` |
| `Notifications.show` | Show literal text in the appropriate notification surface. | `this.toast.classList.add`, `this.timers.clearTimeout`, `this.timers.setTimeout`, `this.toast.classList.remove` |
| `Notifications.destroy` | Stop a pending dismissal. | `this.timers.clearTimeout` |

### `frontend/controllers/panel-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `PanelController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `LatestRequest`, `requiredElement` |
| `PanelController.selectRoute` | Reset only panel-specific selection when the route changes. | `document.activeElement?.closest`, `this.pending.cancel`, `Object.assign`, `url.searchParams.get`, `document
      .querySelector("#game")
      ?.classList.toggle`, `document
      .querySelector`, `this.render`, `(this.returnFocus?.isConnected ? this.returnFocus : requiredElement(".nav-item")).focus`, `requiredElement`, `this.title.focus`, `this.loadDetails` |
| `PanelController.loadDetails` | Fetch selection-specific data; an obsolete response cannot publish. | `this.view.url.searchParams.get`, `this.pending.start`, `this.request`, `request.isCurrent`, `this.notify`, `this.render` |
| `PanelController.render` | Synchronize the selected panel and its navigation state. | `this.reconcileVehicleSelection`, `document.querySelector`, `requiredElement("#game").classList.toggle`, `requiredElement`, `panelTitle`, `this.updateNavigation`, `this.replaceContent` |
| `PanelController.reconcileVehicleSelection` | Keep the selection explicit and invalidate quotes for removed vehicles. | `this.view.url.pathname.startsWith`, `this.view.url.pathname.split`, `this.view.state?.contracts.find`, `eligibleVehicles`, `vehicles.some`, `this.view.url.searchParams.get` |
| `PanelController.updateNavigation` | Mark exactly the active navigation destination. | `document.querySelectorAll(".nav-rail a").forEach`, `document.querySelectorAll`, `URL`, `link.getAttribute`, `this.view.url.pathname.startsWith`, `target.searchParams.get`, `this.view.url.searchParams.get`, `link.classList.toggle`, `link.setAttribute`, `link.removeAttribute` |
| `PanelController.replaceContent` | Replace changed DOM while preserving a selected control's keyboard focus. | `this.content.contains`, `focused.getAttribute`, `renderPanel`, `this.now`, `fragment.querySelectorAll`, `[...this.content.querySelectorAll("details[data-disclosure]")].find`, `this.content.querySelectorAll`, `item.getAttribute`, `detail.getAttribute`, `this.images?.prepare`, `matchVehicleImages`, `[...this.content.childNodes].every`, `node.isEqualNode`, `next.replaceWith`, `this.content.replaceChildren`, `this.images?.update`, `this.restoreFocus` |
| `PanelController.restoreFocus` | Restore a surviving control only when a replacement was necessary. | `[...this.content.querySelectorAll("button, a, select, input")].find`, `this.content.querySelectorAll`, `element.getAttribute`, `replacement.hasAttribute`, `replacement.focus` |
| `PanelController.destroy` | Stop selection-specific reads and future rendering. | `this.pending.cancel`, `this.images?.destroy` |

### `frontend/controllers/preferences-controller.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `PreferencesController.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `LatestRequest`, `AbortController` |
| `PreferencesController.start` | Bind preference actions and refresh visibility-sensitive state. | `this.page.addEventListener`, `event.target.closest`, `this.save`, `button.getAttribute`, `this.refresh` |
| `PreferencesController.refresh` | Publish only the latest successful preference read. | `this.pending.start`, `this.panel.render`, `this.request`, `task.isCurrent`, `this.publish` |
| `PreferencesController.save` | Persist a curated selection through the account API. | `this.panel.view.companyPalette?.includes`, `this.pending.cancel`, `this.publish`, `this.persist` |
| `PreferencesController.persist` | Persist one serialized selection, without overwriting a newer preview. | `this.request`, `JSON.stringify`, `this.publish`, `this.notify` |
| `PreferencesController.publish` | Publish the current confirmed or optimistic color to presentation owners. | `this.page.documentElement.style.setProperty`, `this.map?.setCompanyColor`, `this.panel.render` |
| `PreferencesController.destroy` | Abort preference requests and owned DOM listeners. | `this.pending.cancel`, `this.lifetime.abort` |

### `frontend/controllers/refresh-scheduler.js`

| Methode | Zweck / Vertrag | Abhängigkeiten |
|---|---|---|
| `RefreshScheduler.constructor` | Explizite Parameter-/Rückgabeverträge; Körper unverändert | `this.canRefresh`, `this.refresh`, `this.updateProgress` |
| `RefreshScheduler.start` | Start one polling loop and one progress loop. | `this.timers.setInterval`, `this.page.addEventListener`, `this.browser.addEventListener` |
| `RefreshScheduler.destroy` | Release timers and browser listeners. | `this.intervals.forEach`, `this.timers.clearInterval`, `this.page.removeEventListener`, `this.browser.removeEventListener` |
