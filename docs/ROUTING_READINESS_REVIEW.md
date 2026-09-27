# Routing Readiness: Einzelreview

Stand: 27.09.2026. Basis `df40e7c800d21ac4187912fc9a81a6e08e1349bb`.
Status: implementiert / vollständige lokale Quality- und E2E-Gates bestanden.

Die folgende Liste ist per AST gegen die Basis abgeglichen. Jede aufgeführte
konkrete Funktion wurde auf Zweck, Schicht, Abhängigkeiten und Seiteneffekte
geprüft. Abstrakte Portmethoden sind als solche zusätzlich aufgeführt.
Docstrings beschreiben den fachlichen Zweck; die Aufrufliste zeigt die
unmittelbaren Abhängigkeiten im geprüften Körper, einschließlich Hilfsfunktionen.
Sie ist ein Reviewnachweis und kein Ersatz für Verhaltenstests.

## Feststellungen und Entscheidungen

- `MarketCandidateService` blieb unverändert und routerfrei. Vorbereitung liegt
  in einem eigenen Service; der Generator nimmt nur einen vorbereiteten Pool an.
- Generation-Fingerprint und Relationsbedarf wurden als reine Domainfunktionen
  extrahiert. Keine vollständigen Facility-Bäume im Generation-Hash.
- `prepare_publication` hat eine zusammenhängende Aufgabe: den aktuellen
  Publikationspool samt dauerhaftem Bedarf feststellen. Es führt kein HTTP aus.
- `MarketPreparationWorker.process` koordiniert einen Coverage-Batch über
  bestehende Candidate-, Coverage- und Preparation-Bausteine. Diagnosezählung
  beschreibt diesen Batch; Gewichtung, Materialisierung und Providerpacing
  verbleiben in ihren zuständigen Bausteinen.
- `RoutingReadinessService._validate` ist der begrenzte Validierungsablauf
  einer gerichteten Relation. HTTP-Decoding, Anchor-Reparatur, SQL und
  Payload-Invarianten werden delegiert. Genau eine Endpoint-Revalidierung,
  Fingerprintprüfung nach Await und Lease-Fencing vor Publikation.
- Der Generation-Fingerprint berücksichtigt Delivery und Approach: Wird nur
  ein Approach-Payload ungültig, wird abgeschlossener Spielerbedarf erneut
  eingeplant. Ein eigener Regressionstest schützt diesen Wiederaufnahmefall.
- Anchor- und Relationspublikation prüfen beide den Lease-Eigentümer. Cleanup
  gibt nur eigene Leases frei. Kein Request hält eine Player-Schreibtransaktion.
- `publish` kapselt eine technische atomare Operation (Payload + Relation),
  `bind` die Referenzen einer Markt-UoW. Das ist keine zweite Spielpersistenz.
- Audit-Repository-Komposition liegt in `bootstrap`; die CLI enthält kein SQL.
  Das CLI-Requestbudget ist eine Ausführungsgrenze, keine Providerdrosselung.
- Der Provider-Limiter besitzt Semaphore und Startabstand. Worker besitzen nur
  Scheduling/Backoff. Runtime und CLI injizieren dieselben Providergrenzen.
- `project_contract` ergänzt RouteReference ausschließlich für das typisierte
  AvailableContract-Read-Modell. Historische und rohe Offer-Projektionen erhalten
  keine neuen Felder; ein expliziter API-Gegencheck schützt diese Grenze.
- Die Dispatch-Grenze mappt globale Providerwerte in die unveränderte
  RouteSnapshot-Struktur. Journey/Economy bleiben getrennt und unverändert.
- Optionale Test-Komposition ohne Preparation bleibt für bestehende isolierte
  Service-Tests erhalten. Die Produktionskomposition bindet Preparation immer;
  sie besitzt keinen ungeprüften Quote-Routing-Fallback.
- Lifespan registriert Worker-Cleanup vor Start; frischer Context und eigene
  Execution-Traces verhindern langlebige HTTP-Kontexte.
- Frontendänderungen projizieren nur Preparationstatus. Polling, Abort und
  LatestRequest bleiben Controller-Verantwortung; Views führen keine Requests aus.

## Python-Core: einzeln abgeglichene Funktionen

### `app/api/v1/contracts.py`

Schicht: API. Grenze: HTTP-Projektion und Delegation; keine Fachberechnungen.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `list_contracts` | Return the active idle-vehicle city markets. | `Depends`, `asdict`, `game.contract_choices`, `game.list_contracts`, `game.preparation_status`, `project_contract`, `router.get` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `get_contract` | Return one contract including real endpoint addresses. | `Depends`, `HTTPException`, `game.contract_choices`, `game.get_contract`, `project_contract`, `router.get`, `str` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `quote_contract` | Quote the selected vehicle against prepared global routes. | `Depends`, `HTTPException`, `game.quote_contract`, `project_quote`, `router.post`, `str` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `accept_contract` | Accept and dispatch one contract with a selected vehicle. | `Depends`, `HTTPException`, `game.dispatch`, `project_transport`, `router.post`, `str` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `refresh_contracts` | Regenerate only the current active city markets. | `Depends`, `asdict`, `game.contract_choices`, `game.preparation_status`, `game.refresh_contracts`, `project_contract`, `router.post` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/api/v1/game_projection.py`

Schicht: API. Grenze: HTTP-Projektion und Delegation; keine Fachberechnungen.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `project_contract` | Expose an offer using the established v1 field names. | `asdict`, `isinstance`, `list`, `project_location`, `project_nhm_profile` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/bootstrap.py`

Schicht: Composition/Infrastructure. Grenze: Ressourcen/Abhängigkeiten konfigurieren; Fachregeln delegieren.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `build_routing_anchor_resolver` | Wire global truck anchors outside immutable world references. | `NominatimGeocoder`, `RoutingAnchorResolver`, `SqliteProviderCache`, `SqliteRoutingAnchorRepository`, `ValhallaTruckAnchorLocator`, `partial` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `build_game_runtime` | Initialize only relational storage and shared application resources. | `CachedVehicleCatalogue`, `GameRuntime`, `MarketScopeResolver`, `ProviderRequestLimiter`, `RoutingReadinessService`, `SqliteGameDatabase`, `SqlitePreparationStore`, `SqliteProviderCache`, `SqliteRoutingAnchorRepository`, `SqliteRoutingReadinessStore`, `ValhallaTruckRouter`, `build_market_generator`, `build_routing_anchor_resolver`, `build_vehicle_catalogue`, `build_world_catalogue`, `database.initialize`, `partial`, `random.Random` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `build_player_service` | Bind one authenticated owner to the shared relational transaction. | `DispatchPlanningService`, `GameService`, `SqliteGameUnitOfWork`, `VehicleCostResolver`, `build_market_preparation`, `game.ensure_initial_state` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `build_market_startup` | Wire existing profiles to a shared outer transaction. | `MarketLifecycleService`, `MarketStartupService`, `SqliteGameUnitOfWork`, `SqliteMarketStartupStore`, `build_market_preparation` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `build_market_startup.lifecycle` | Bind market-only operations without initializing or settling. | `MarketLifecycleService`, `SqliteGameUnitOfWork`, `build_market_preparation` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `build_market_preparation` | Bind production routing infrastructure to one player's offers. | `MarketPreparationService`, `SqliteOfferRouteStore` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `build_preparation_worker` | Assemble owned preparation without initializing player state. | `MarketLifecycleService`, `MarketPreparationWorker`, `SqliteGameUnitOfWork`, `build_market_preparation` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `build_preparation_worker.lifecycle` | Bind current player state without changing it during composition. | `MarketLifecycleService`, `SqliteGameUnitOfWork`, `build_market_preparation` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `build_routing_audit` | Compose local routing diagnostics without provider operations. | `SqliteRoutingAudit` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/config.py`

Schicht: Composition/Infrastructure. Grenze: Ressourcen/Abhängigkeiten konfigurieren; Fachregeln delegieren.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `Settings.from_env` | Build settings from the current process environment. | `Path`, `Path(__file__).resolve`, `cls`, `data_dir.mkdir`, `float`, `int`, `max`, `os.getenv`, `os.getenv('COOKIE_SECURE', 'false').lower`, `os.getenv('LOG_LEVEL', 'INFO').upper`, `os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org').rstrip`, `os.getenv('VALHALLA_URL', 'https://valhalla1.openstreetmap.de').rstrip` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/domain/market_compatibility.py`

Schicht: Domain. Grenze: Immutable Werte/Ports; keine I/O.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `market_vehicle` | Freeze owned capacity while resolving only reference capabilities. | `MarketVehicle`, `ValueError`, `VehicleCostProfile`, `vehicle_scale_for_segment` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/domain/market_preparation.py`

Schicht: Domain. Grenze: Immutable Werte/Ports; keine I/O.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `PreparationStore.request` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `PreparationStore.status` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `PreparationStore.next_player` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `PreparationStore.finish` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `preparation_generation` | Fingerprint relevant demand without copying entire facility trees. | `repr`, `repr((fleet, facts, references)).encode`, `sha256`, `sha256(repr((fleet, facts, references)).encode()).hexdigest`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `required_relations` | Deduplicate deliveries and actual-start approaches in stable order. | `dict.fromkeys`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/domain/readiness_ports.py`

Schicht: Domain. Grenze: Immutable Werte/Ports; keine I/O.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `RoutingReadinessStore.get` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `RoutingReadinessStore.payload` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `RoutingReadinessStore.acquire` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `RoutingReadinessStore.renew` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `RoutingReadinessStore.release` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `RoutingReadinessStore.publish` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `RoutingReadinessStore.append_attempt` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `OfferRouteStore.get` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `OfferRouteStore.replace` | Abstrakter injizierter Portvertrag. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
### `app/domain/routing_anchor_ports.py`

Schicht: Domain. Grenze: Immutable Werte/Ports; keine I/O.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `RoutingAnchorStore.put_leased` | Persist only while the matching global anchor lease is owned. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
| `RoutingAnchorResolverPort.resolve` | Resolve or reuse one routing anchor. | Keine konkreten Aufrufe | Port; keine Implementierungsseiteneffekte. |
### `app/domain/routing_anchors.py`

Schicht: Domain. Grenze: Immutable Werte/Ports; keine I/O.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `anchor_source_fingerprint` | Bind cached access to facility identity, address and coordinates. | `facility.address.display_text`, `repr`, `repr(value).encode`, `sha256`, `sha256(repr(value).encode()).hexdigest` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/domain/routing_readiness.py`

Schicht: Domain. Grenze: Immutable Werte/Ports; keine I/O.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `RouteReference.__post_init__` | Reject references which cannot identify a persisted revision. | `require_identity` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutePayload.__post_init__` | Apply the existing geometry and provider metric invariants. | `self.to_snapshot` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutePayload.to_snapshot` | Map provider facts without changing historical field names. | `RouteSnapshot` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingRelation.__post_init__` | Reject incoherent ready and negative routing records. | `ValueError`, `relation_identity`, `require_finite`, `require_identity` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingAttempt.__post_init__` | Require identifiable diagnostic evidence and finite values. | `Coordinates`, `ValueError`, `require_finite`, `require_identity` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `relation_identity` | Derive a stable directed truck relation identity. | `len`, `require_identity`, `sha256`, `sha256(value.encode()).hexdigest`, `value.encode` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/main.py`

Schicht: Composition/Infrastructure. Grenze: Ressourcen/Abhängigkeiten konfigurieren; Fachregeln delegieren.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `lifespan` | Create and close provider HTTP clients for the application lifetime. | `AccountRepository`, `AsyncExitStack`, `AuthService`, `PasswordHasher`, `build_game_runtime`, `build_market_startup`, `build_market_startup(app.state.game).rebuild`, `build_preferences`, `build_preparation_worker`, `httpx.AsyncClient`, `resources.push_async_callback`, `worker.start` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/providers/geocoding.py`

Schicht: Provider. Grenze: HTTP/Cache/Limiter; kein Player-State und keine Marktregeln.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `NominatimGeocoder.geocode` | Normalize transport and malformed-response errors at the port. | `GeocodingError`, `isinstance`, `self._resolve_address` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `NominatimGeocoder._resolve_address` | Resolve one postal address, using the persistent cache first. | `GeocodingError`, `LOGGER.info`, `LOGGER.warning`, `ValueError`, `first.get`, `get_trace_id`, `isinstance`, `parse_coordinates`, `response.headers.get`, `response.json`, `response.raise_for_status`, `retry_after_seconds`, `self._respect_rate_limit`, `self.cache.get_geocode`, `self.cache.put_geocode`, `self.client.get`, `str`, `time.monotonic`, `time.time` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/providers/request_limiter.py`

Schicht: Provider. Grenze: HTTP/Cache/Limiter; kein Player-State und keine Marktregeln.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `retry_after_seconds` | Parse HTTP delay seconds or an HTTP date without inventing retries. | `float`, `math.isfinite`, `max`, `parsedate_to_datetime`, `parsedate_to_datetime(value).timestamp` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ProviderRequestLimiter.__init__` | Reject invalid limits before allocating asynchronous resources. | `ValueError`, `asyncio.Lock`, `asyncio.Semaphore`, `math.isfinite` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ProviderRequestLimiter.request` | Reserve concurrency and pace starts, releasing on cancellation. | `asyncio.sleep`, `time.monotonic` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ProviderRequestLimiter.defer` | Apply Retry-After to all subsequent requests for this provider. | `max`, `retry_after_seconds`, `time.monotonic`, `time.time` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/providers/routing.py`

Schicht: Provider. Grenze: HTTP/Cache/Limiter; kein Player-State und keine Marktregeln.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `ValhallaTruckRouter.__init__` | Inject HTTP, cache, pacing and observed revision boundaries. | `ProviderRequestLimiter`, `base_url.rstrip` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ValhallaTruckRouter._resolve_route` | Fetch or reuse a real truck route between two coordinates. | `(provider_message or '').casefold`, `LOGGER.info`, `LOGGER.warning`, `RoutingError`, `any`, `get_trace_id`, `graph_revision`, `isinstance`, `payload.get`, `raw_message.strip`, `response.headers.get`, `response.json`, `route_cache_document`, `self._build_cache_key`, `self._extract_route`, `self.cache.get_route`, `self.cache.put_route`, `self.client.post`, `self.limiter.defer`, `self.limiter.request`, `self.revision_observer`, `validate_route` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ValhallaTruckRouter._build_cache_key` | Create a stable cache key for one directed truck route. | `hashlib.sha256`, `hashlib.sha256(raw.encode('utf-8')).hexdigest`, `raw.encode` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/providers/routing_anchor.py`

Schicht: Provider. Grenze: HTTP/Cache/Limiter; kein Player-State und keine Marktregeln.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `ValhallaTruckAnchorLocator.__init__` | Inject truck-locate HTTP and shared provider request limits. | `ProviderRequestLimiter`, `base_url.rstrip` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ValhallaTruckAnchorLocator.locate` | Validate a candidate without inventing coordinates. | `Coordinates`, `LOGGER.info`, `LOGGER.warning`, `LocateResult`, `any`, `float`, `get_trace_id`, `response.headers.get`, `response.json`, `response.text.casefold`, `self._access_candidates`, `self._correlated_location`, `self._edge_count`, `self._response_failure`, `self._revision`, `self._snap_distance_m`, `self.client.post`, `self.limiter.defer`, `self.limiter.request`, `self.revision_observer`, `str` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ValhallaTruckAnchorLocator._response_failure` | Retain bounded provider evidence for append-only diagnostics. | `LocateResult`, `data.get`, `isinstance`, `response.json`, `type` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ValhallaTruckAnchorLocator._access_candidates` | Retain at most five distinct truck-compatible OSM correlations. | `Coordinates`, `candidates.append`, `edge.get`, `edge.get('access', {}).get`, `float`, `len`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `ValhallaTruckAnchorLocator._revision` | Read a provider or graph revision only when supplied. | `graph_revision` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/providers/valhalla_metadata.py`

Schicht: Provider. Grenze: HTTP/Cache/Limiter; kein Player-State und keine Marktregeln.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `graph_revision` | Prefer a graph revision over the routing engine's software version. | `headers.get` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/repositories/market_preparation.py`

Schicht: Repository. Grenze: SQLite über injizierte Runtime-Datenbank; keine HTTP-Aufrufe.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `SqlitePreparationStore.__init__` | Initialize additive infrastructure before opening game work. | `conn.execute`, `database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqlitePreparationStore.request` | Enqueue changed demand without resetting unchanged retry timing. | `conn.execute`, `self.database.connect`, `uuid.uuid4` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqlitePreparationStore.status` | Read the bound player's public preparation projection. | `PreparationStatus`, `conn.execute`, `conn.execute('SELECT preparation_id, generation, status, next_retry_at FROM market_preparations WHERE user_id=?', (user_id,)).fetchone`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqlitePreparationStore.next_player` | Choose the oldest due batch so active players share the worker. | `conn.execute`, `conn.execute("SELECT user_id FROM market_preparations WHERE status='partial' AND (next_retry_at IS NULL OR next_retry_at<=?) ORDER BY updated_at, user_id LIMIT 1", (now,)).fetchone`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqlitePreparationStore.finish` | Update only the demand generation actually processed. | `conn.execute`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/repositories/routing_anchors.py`

Schicht: Repository. Grenze: SQLite über injizierte Runtime-Datenbank; keine HTTP-Aufrufe.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `SqliteRoutingAnchorRepository.get` | Return one persisted routing result. | `Coordinates`, `RoutingAnchor`, `ValueError`, `connection.execute`, `connection.execute('SELECT fingerprint FROM routing_anchor_sources WHERE facility_uid=? AND routing_profile=?', (facility_uid, routing_profile)).fetchone`, `connection.execute('\n                SELECT facility_uid, routing_profile, anchor_lat, anchor_lon,\n                       method, facility_lat, facility_lon, snap_distance_m,\n                       validation_status, provider, provider_revision,\n                       validated_at\n                FROM routing_anchors\n                WHERE facility_uid=? AND routing_profile=?\n                ', (facility_uid, routing_profile)).fetchone`, `float`, `self._database.connect`, `str` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingAnchorRepository.put` | Replace one routing result after provider awaits have completed. | `connection.execute`, `self._database.connect`, `self._database.transaction` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingAnchorRepository.put_leased` | Fence anchor publication with its infrastructure lease. | `conn.execute`, `conn.execute('SELECT 1 FROM routing_leases WHERE subject=? AND owner=? AND expires_at>?', (subject, owner, now)).fetchone`, `self._database.connect`, `self._database.transaction`, `self.put` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/repositories/routing_audit.py`

Schicht: Repository. Grenze: SQLite über injizierte Runtime-Datenbank; keine HTTP-Aufrufe.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `SqliteRoutingAudit.__init__` | Bind an existing runtime database without creating game state. | Keine konkreten Aufrufe | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingAudit.report` | Report global outcomes and optionally focused facility attempts. | `conn.execute`, `dict`, `focused.extend`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/repositories/routing_readiness.py`

Schicht: Repository. Grenze: SQLite über injizierte Runtime-Datenbank; keine HTTP-Aufrufe.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `SqliteRoutingReadinessStore.__init__` | Create additive infrastructure without changing game columns. | `connection.executescript`, `database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.get` | Read the currently published revision of a directed relation. | `RouteReference`, `RoutingRelation`, `connection.execute`, `connection.execute('SELECT * FROM routing_relations WHERE relation_id=?', (relation_id,)).fetchone`, `dict`, `self.database.connect`, `values.pop` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.payload` | Reject missing, stale or malformed cached route documents. | `RoutePayload`, `connection.execute`, `connection.execute("SELECT c.payload FROM routing_relations r JOIN route_cache c ON c.cache_key=r.cache_key WHERE r.relation_id=? AND r.revision=? AND r.status='ready'", (reference.relation_id, reference.revision)).fetchone`, `json.loads`, `self.database.connect`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.acquire` | Acquire only an absent or expired globally shared lease. | `ValueError`, `connection.execute`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.renew` | Extend a still-owned lease without resurrecting expired work. | `ValueError`, `connection.execute`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.release` | Release only this owner's lease, including cancellation cleanup. | `connection.execute`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.publish` | Atomically fence the writer and publish metrics with readiness. | `ValueError`, `asdict`, `conn.execute`, `conn.execute('SELECT 1 FROM routing_leases WHERE subject=? AND owner=? AND expires_at>?', (relation.reference.relation_id, owner, now)).fetchone`, `json.dumps`, `self.database.connect`, `self.database.transaction` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.append_attempt` | Append evidence; previous failures are never overwritten. | `asdict`, `asdict(attempt).values`, `connection.execute`, `self.database.connect`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.provider_revision` | Read the latest actually observed graph revision for a provider. | `connection.execute`, `connection.execute('SELECT revision FROM routing_provider_revisions WHERE provider=?', (provider,)).fetchone`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteRoutingReadinessStore.observe_provider_revision` | Persist known provider metadata independently of player state. | `connection.execute`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteOfferRouteStore.__init__` | Bind infrastructure references to one authenticated owner. | Keine konkreten Aufrufe | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteOfferRouteStore.get` | Read only the bound player's open-offer reference. | `RouteReference`, `connection.execute`, `connection.execute('SELECT relation_id, revision FROM offer_route_references WHERE user_id=? AND contract_id=?', (self.user_id, offer_id)).fetchone`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `SqliteOfferRouteStore.replace` | Replace bindings inside the caller's atomic market transaction. | `connection.execute`, `connection.executemany`, `self.database.connect` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/dispatch_planning.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `DispatchPlanningService.route` | Load prepared approach and delivery before a write transaction. | `DispatchRoutePlan`, `ValueError`, `self._route_between`, `self.preparation.retained` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `DispatchPlanningService._route_between` | Resolve a prepared relation at the dispatch boundary. | `ValueError`, `WorldScope`, `self.anchors.resolve`, `self.preparation.readiness.load`, `self.preparation.readiness.load(start.facility_uid, destination.facility_uid).to_snapshot`, `self.router.route`, `self.world.read`, `world.facility` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `DispatchPlanningService.quote` | Compose journey and economics from revalidated purchased values. | `ContractQuote`, `ValueError`, `calculate_price`, `current.load`, `current.load(contract.origin.facility_uid, contract.destination.facility_uid).to_snapshot`, `current.load(route.start.facility_uid, contract.origin.facility_uid).to_snapshot`, `journey_costs`, `plan_dispatch_journey`, `self.costs.resolve`, `self.preparation.retained` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/game.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `GameService.__init__` | Wire player-scoped orchestration to injected service ports. | `MarketLifecycleService`, `max`, `self.now` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `GameService.preparation_status` | Expose typed progress for the authenticated player's market. | `preparation.jobs.status` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `GameService.quote_contract` | Load prepared routes and calculate selected-vehicle economics. | `LOGGER.info`, `ValueError`, `self._calculate_quote`, `self._find_contract`, `self._find_vehicle`, `self._validate_dispatch`, `self.dispatch_planning.route`, `self.get_vehicle`, `self.reconcile_arrival`, `self.state_repository.list_vehicles` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/market.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `MarketGenerator.generate` | Return retained and newly materialized offers with diagnostics. | `ContractOffer.from_snapshot`, `self.candidates.build`, `self.coverage.plan`, `self.factory.build`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/market_lifecycle.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `MarketLifecycleService.refresh` | Read fleet, retain valid work and fill coverage atomically. | `LOGGER.info`, `asdict`, `len`, `list`, `repository.list_vehicles`, `self._retained`, `self._store`, `self.clock`, `self.generator.candidates.build`, `self.generator.candidates.resolve_fleet`, `self.generator.generate`, `self.preparation.prepare_publication`, `self.scope.resolve`, `self.unit_of_work.transaction` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketLifecycleService._retained` | Keep only fresh, structurally current, currently drivable offers. | `candidates.eligible_ids`, `candidates.structurally_current`, `offer.is_available`, `self.preparation.retained`, `self.unit_of_work.repository.list_offers`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketLifecycleService._store` | Persist changed offers inside the caller-owned transaction. | `repository.list_offers`, `repository.replace_offers`, `self.preparation.bind` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketLifecycleService.present` | Attach transient eligibility and separate route references. | `AvailableContract`, `result.append`, `self.generator.candidates.eligible_ids`, `self.generator.candidates.resolve_fleet`, `self.preparation.eligible`, `self.preparation.references.get`, `self.preparation.retained`, `self.unit_of_work.repository.list_vehicles`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/market_preparation.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `MarketPreparationService.__init__` | Inject global readiness and player-scoped reference storage. | Keine konkreten Aufrufe | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationService.prepare_publication` | Enqueue demand and expose delivery-ready structural candidates. | `preparation_generation`, `required_relations`, `references.items`, `self.clock`, `self.jobs.request`, `self.readiness.ready`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationService.retained` | Require the exact persisted revision before retaining an offer. | `self.readiness.ready`, `self.references.get` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationService.eligible` | Add actual-start approach readiness to shared vehicle rules. | `self.readiness.ready`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationService.bind` | Write exact route references within the caller's market UoW. | `ValueError`, `bindings.append`, `self.readiness.ready`, `self.references.replace`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationService.prepare_batch` | Prepare a bounded batch; provider adapters own request pacing. | `min`, `required_relations`, `self.clock`, `self.readiness.current`, `self.readiness.prepare` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/preparation_worker.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `MarketPreparationWorker.__init__` | Inject scheduling storage and player lifecycle composition. | Keine konkreten Aufrufe | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationWorker.start` | Start exactly one owned loop in a fresh context. | `Context`, `RuntimeError`, `asyncio.create_task`, `asyncio.sleep`, `self._run`, `self._task.done` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationWorker.close` | Cancel and await owned work before provider resources close. | `task.cancel` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationWorker._run` | Process due batches fairly and isolate failures with backoff. | `LOGGER.exception`, `asyncio.sleep`, `background_trace`, `self.clock`, `self.jobs.finish`, `self.jobs.next_player`, `self.jobs.status`, `self.process` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `MarketPreparationWorker.process` | Prepare missing coverage and re-read state before publication. | `Counter`, `LOGGER.info`, `dict`, `dict.fromkeys`, `len`, `lifecycle.generator.candidates.build`, `lifecycle.generator.candidates.resolve_fleet`, `lifecycle.generator.coverage.plan`, `lifecycle.refresh`, `lifecycle.scope.resolve`, `lifecycle.unit_of_work.repository.list_vehicles`, `preparation.prepare_batch`, `preparation.readiness.current`, `self.clock`, `self.jobs.finish`, `self.jobs.status`, `self.lifecycle`, `states.values`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/routing_anchors.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `RoutingAnchorResolver.__init__` | Inject provider ports and optional infrastructure diagnostics. | `ValueError` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingAnchorResolver.resolve` | Reuse a validated anchor or acquire globally bounded repair work. | `TimeoutError`, `anchor_source_fingerprint`, `asyncio.sleep`, `asyncio.timeout`, `replace`, `self._clock`, `self._evidence.acquire`, `self._evidence.release`, `self._repair`, `self._store.get`, `self._store.put`, `self._store.put_leased`, `uuid.uuid4` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingAnchorResolver._repair` | Try facility, postal address and bounded real OSM candidates. | `Coordinates`, `RoutingAnchor`, `attempted.add`, `candidates.extend`, `dict.fromkeys`, `facility.address.display_text`, `self._attempt`, `self._clock`, `self._geocoder.geocode`, `self._record`, `set`, `str`, `tuple` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingAnchorResolver._attempt` | Validate a candidate and append evidence before returning it. | `self._accepted_anchor`, `self._failure`, `self._locator.locate`, `self._record` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingAnchorResolver._record` | Append an attempt without overwriting earlier repair evidence. | `RoutingAttempt`, `get_trace_id`, `logging.getLogger`, `logging.getLogger(__name__).log`, `self._clock`, `self._evidence.append_attempt` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/routing_inventory.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `routing_inventory` | Yield NHM trades and city approaches, never a global cross-product. | `TradeNetwork`, `city_name.casefold`, `network.options_for`, `origin.address.city.name.casefold`, `origin.is_routable`, `seen.add`, `set`, `start.is_routable` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/services/routing_readiness.py`

Schicht: Service. Grenze: Injizierte Ports und Domainregeln; kein SQL/HTTP-Parsing.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `RoutingReadinessService.__init__` | Inject infrastructure ports and a bounded provider-work deadline. | `ValueError` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingReadinessService.fingerprint` | Bind readiness to current facilities, anchors and provider graph. | `WorldScope`, `asdict`, `facility.address.display_text`, `facts.append`, `json.dumps`, `json.dumps(facts, default=str).encode`, `scope.facility`, `self.anchor_store.get`, `self.provider_revision`, `self.world.read`, `sha256`, `sha256(json.dumps(facts, default=str).encode()).hexdigest` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingReadinessService.current` | Return current ready or negative evidence without any HTTP call. | `relation_identity`, `replace`, `self.fingerprint`, `self.store.get`, `self.store.payload` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingReadinessService.ready` | Expose only a validated current relation to market publication. | `self.current` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingReadinessService.load` | Load validated metrics without a quote-time provider fallback. | `ValueError`, `self.ready`, `self.store.payload` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingReadinessService.prepare` | Deduplicate directed work globally and reuse negative evidence. | `asyncio.timeout`, `relation_identity`, `self._failure`, `self._validate`, `self.clock`, `self.current`, `self.store.acquire`, `self.store.release`, `uuid.uuid4` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingReadinessService._validate` | Resolve truck endpoints and validate one provider route. | `RoutePayload`, `RouteReference`, `RoutingAttempt`, `RoutingRelation`, `WorldScope`, `any`, `get_trace_id`, `relation_identity`, `scope.facility`, `self._failure`, `self._validate`, `self.anchors.resolve`, `self.clock`, `self.fingerprint`, `self.router.route`, `self.store.append_attempt`, `self.store.publish`, `self.store.renew`, `self.world.read`, `uuid.uuid4` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
| `RoutingReadinessService._failure` | Persist diagnostic failure and its bounded retry schedule. | `RouteReference`, `RoutingAttempt`, `RoutingRelation`, `get_trace_id`, `relation_identity`, `self.clock`, `self.fingerprint`, `self.store.append_attempt`, `self.store.publish`, `uuid.uuid4` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |
### `app/tracing.py`

Schicht: Observability. Grenze: ContextVar setzen/zurücksetzen; keine Playerdatenmutation.

| Funktion | Zweck | Direkte Aufrufe / Abhängigkeiten | Review |
| --- | --- | --- | --- |
| `background_trace` | Correlate one execution without retaining an HTTP request context. | `_TRACE_ID.reset`, `_TRACE_ID.set`, `new_trace_id` | Eine zusammenhängende Aufgabe; Schichtgrenze eingehalten. |

Inventar: 117 neue oder geänderte Core-Callables einschließlich abstrakter
Portmethoden und verschachtelter Composition-Fabriken. Rein deklarative
Dataclass-Felder sind über Domain-/Mappingtests abgedeckt.

## Frontend: Einzelreview

| Funktion | Zweck / Abhängigkeit | Seiteneffekte / Ergebnis |
| --- | --- | --- |
| ContractMarketController.loadList | Aktuelle Antwort über LatestRequest an GameState weitergeben | HTTP/Abort bleiben im Controller; stale Antworten verändern weder Offers noch Preparationstatus. |
| GameState.replaceContracts | Gemeinsamen Offer-/Preparation-Read-State ersetzen | Nur lokaler Zustand und vorhandene Benachrichtigung; keine Requests. |
| renderContracts | Angebote und verständlichen Preparationstatus darstellen | DOM; keine Providerdetails, keine Tarif- oder Eignungsberechnung. |

Tests/Fixtures wurden separat auf Mock-Isolation und serverseitige Eignung
geprüft: `readyContracts` wartet auf abgeschlossene Vorbereitung;
`openEligibleOffer` wählt daraus ein für alle übergebenen Fahrzeuge geeignetes
Angebot und wählt das Fahrzeug ausdrücklich. `openVehicleMarket` navigiert über
das idle Fahrzeug. Keine Assertions für Quote, Kosten, Ankunft, Isolation,
Kamerastabilität oder historische Daten wurden entfernt.

`install_fake_routing` bindet beide Providerpfade im isolierten API-Testserver.
`prepare_client_market` übergibt die Vorbereitung dem Application-Eventloop;
`prepare_player_market` nutzt echte Readiness und Publikation für einen Candidate.
`add_transport` erzeugt eine historische Testsendung direkt aus einem Candidate,
ohne eine aktuelle Marktveröffentlichung vorzutäuschen. Diese Testhelfer besitzen
keinen Produktionspfad.

Der Browser-beforeEach ordnet Auth-Requests jedes Testfalls einem eigenen
simulierten Client hinter dem lokalen vertrauenswürdigen Testproxy zu. Dadurch
teilen unabhängige Testfälle kein IP-Versuchsbudget. Der Produktions-Throttle
bleibt unverändert und innerhalb eines Testfalls wirksam; seine API-Gegenproben
bleiben erhalten. Der erste vollständige Browserlauf deckte diese bisher
geteilte Testressource auf.

`scripts/quality.py` ergänzt ausschließlich den Audit-Einstiegspunkt in seinen
vorhandenen Ruff-/Format-/mypy-Kommandos. Reihenfolge und Coverage-Schwelle bleiben
erhalten; keine neue Core-Funktion und keine zusätzliche Verantwortlichkeit.

## Abnahme und Betriebsgrenzen

Vollständige Quality-/Playwright-Gates und git diff --check bestanden.
Gesamt-Core-Coverage: 5413/5413 Statements. Der Qualitätsbericht enthält die
tatsächlichen Befehle, Testergebnisse und die korrigierten Zwischenfehler.
Echte Providerantworten und produktive Multi-Prozess-Last sind nicht durch
Mocktests oder Screenshotbefunde abgenommen.
