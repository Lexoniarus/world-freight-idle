FUNCTION_TESTS = {
    "app.bootstrap.build_routing_audit": "test_audit_report_is_local_and_prewarm_counts_every_request",
    "app.domain.market_preparation.preparation_generation": "test_preparation_generation_and_reference_rollback",
    "app.domain.market_preparation.required_relations": "test_preparation_failures_backoff_fencing_and_worker_cleanup",
    "app.providers.valhalla_metadata.graph_revision": "test_graph_revision_prefers_graph_metadata_without_inventing_versions",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.provider_revision": "test_observed_global_graph_revision_invalidates_shared_routes",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.observe_provider_revision": "test_observed_global_graph_revision_invalidates_shared_routes",
    "app.domain.routing_anchors.anchor_source_fingerprint": "test_anchor_policy_changes_invalidate_coordinate_and_address_evidence",
    "app.providers.routing_anchor.ValhallaTruckAnchorLocator._response_failure": "test_locate_failure_preserves_bounded_provider_diagnostics",
    "app.repositories.routing_anchors.SqliteRoutingAnchorRepository.put_leased": "test_anchor_publication_rejects_expired_owner",
    "app.bootstrap.build_market_preparation": "test_preparation_composition_preserves_unconfigured_test_runtime",
    "app.bootstrap.build_preparation_worker": "test_preparation_composition_preserves_unconfigured_test_runtime",
    "app.bootstrap.build_preparation_worker.batch": "test_preparation_composition_preserves_unconfigured_test_runtime",
    "app.domain.routing_readiness.RoutePayload.__post_init__": "test_readiness_domain_rejects_incoherent_records",
    "app.domain.routing_readiness.RoutePayload.to_snapshot": "test_readiness_domain_rejects_incoherent_records",
    "app.domain.routing_readiness.RouteReference.__post_init__": "test_readiness_domain_rejects_incoherent_records",
    "app.domain.routing_readiness.RoutingAttempt.__post_init__": "test_readiness_domain_rejects_incoherent_records",
    "app.domain.routing_readiness.RoutingRelation.__post_init__": "test_readiness_domain_rejects_incoherent_records",
    "app.domain.routing_readiness.relation_identity": "test_readiness_domain_rejects_incoherent_records",
    "app.providers.request_limiter.ProviderRequestLimiter.__init__": "test_limiter_serializes_and_releases_cancelled_waiters",
    "app.providers.request_limiter.ProviderRequestLimiter.defer": "test_limiter_serializes_and_releases_cancelled_waiters",
    "app.providers.request_limiter.ProviderRequestLimiter.request": "test_limiter_serializes_and_releases_cancelled_waiters",
    "app.providers.request_limiter.retry_after_seconds": "test_retry_after_and_invalid_provider_limits",
    "app.providers.routing_anchor.ValhallaTruckAnchorLocator._access_candidates": "test_locate_candidates_are_bounded_and_exclude_nontruck_edges",
    "app.repositories.market_preparation.SqlitePreparationStore.__init__": "test_preparation_generation_and_reference_rollback",
    "app.repositories.market_preparation.SqlitePreparationStore.finish": "test_preparation_generation_and_reference_rollback",
    "app.repositories.market_preparation.SqlitePreparationStore.next_player": "test_preparation_generation_and_reference_rollback",
    "app.repositories.market_preparation.SqlitePreparationStore.request": "test_preparation_generation_and_reference_rollback",
    "app.repositories.market_preparation.SqlitePreparationStore.status": "test_preparation_generation_and_reference_rollback",
    "app.repositories.routing_audit.SqliteRoutingAudit.__init__": "test_audit_inventory_is_structural_and_report_preserves_history",
    "app.repositories.routing_audit.SqliteRoutingAudit.report": "test_audit_inventory_is_structural_and_report_preserves_history",
    "app.repositories.routing_readiness.SqliteOfferRouteStore.__init__": "test_attempt_history_and_offer_reference_atomicity",
    "app.repositories.routing_readiness.SqliteOfferRouteStore.get": "test_attempt_history_and_offer_reference_atomicity",
    "app.repositories.routing_readiness.SqliteOfferRouteStore.replace": "test_attempt_history_and_offer_reference_atomicity",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.__init__": "test_global_lease_fences_expired_and_competing_writers",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.acquire": "test_global_lease_fences_expired_and_competing_writers",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.append_attempt": "test_attempt_history_and_offer_reference_atomicity",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.get": "test_global_lease_fences_expired_and_competing_writers",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.payload": "test_global_lease_fences_expired_and_competing_writers",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.publish": "test_global_lease_fences_expired_and_competing_writers",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.release": "test_global_lease_fences_expired_and_competing_writers",
    "app.repositories.routing_readiness.SqliteRoutingReadinessStore.renew": "test_global_lease_fences_expired_and_competing_writers",
    "app.services.game.GameService.preparation_status": "test_preparation_generation_and_reference_rollback",
    "app.services.market_preparation.MarketPreparationService.__init__": "test_partial_market_never_publishes_unchecked_offers",
    "app.services.market_preparation.MarketPreparationService.bind": "test_partial_market_never_publishes_unchecked_offers",
    "app.services.market_preparation.MarketPreparationService.eligible": "test_partial_market_never_publishes_unchecked_offers",
    "app.services.market_preparation.MarketPreparationService.prepare_publication": "test_partial_market_never_publishes_unchecked_offers",
    "app.services.market_preparation.MarketPreparationService.prepare_batch": "test_preparation_failures_backoff_fencing_and_worker_cleanup",
    "app.services.market_preparation.MarketPreparationService.retained": "test_partial_market_never_publishes_unchecked_offers",
    "app.services.preparation_worker.MarketPreparationWorker.__init__": "test_worker_fills_ready_market_and_owns_shutdown",
    "app.services.preparation_worker.MarketPreparationWorker._run": "test_preparation_failures_backoff_fencing_and_worker_cleanup",
    "app.services.preparation_worker.MarketPreparationWorker.close": "test_worker_fills_ready_market_and_owns_shutdown",
    "app.services.preparation_worker.MarketPreparationWorker.process": "test_worker_fills_ready_market_and_owns_shutdown",
    "app.services.preparation_worker.MarketPreparationWorker.start": "test_worker_fills_ready_market_and_owns_shutdown",
    "app.services.routing_anchors.RoutingAnchorResolver._record": "test_candidate_search_keeps_evidence_and_never_changes_saved_anchor",
    "app.services.routing_inventory.routing_inventory": "test_audit_inventory_is_structural_and_report_preserves_history",
    "app.services.routing_readiness.RoutingReadinessService.__init__": "test_global_negative_cache_timeout_and_stale_payload",
    "app.services.routing_readiness.RoutingReadinessService._failure": "test_global_negative_cache_timeout_and_stale_payload",
    "app.services.routing_readiness.RoutingReadinessService._validate": "test_preparation_failures_backoff_fencing_and_worker_cleanup",
    "app.services.routing_readiness.RoutingReadinessService.current": "test_global_negative_cache_timeout_and_stale_payload",
    "app.services.routing_readiness.RoutingReadinessService.fingerprint": "test_global_negative_cache_timeout_and_stale_payload",
    "app.services.routing_readiness.RoutingReadinessService.load": "test_global_negative_cache_timeout_and_stale_payload",
    "app.services.routing_readiness.RoutingReadinessService.prepare": "test_global_negative_cache_timeout_and_stale_payload",
    "app.services.routing_readiness.RoutingReadinessService.ready": "test_global_negative_cache_timeout_and_stale_payload",
    "app.tracing.background_trace": "test_background_trace_never_retains_request_context",
    "app.domain.routes.DispatchRoutePlan.__post_init__": "test_dispatch_route_invariants_and_historical_mapping",
    "app.domain.routes.DispatchRoutePlan.total_route": "test_dispatch_route_invariants_and_historical_mapping",
    "app.domain.routes.DispatchRoutePlan.total_coordinates": "test_dispatch_route_matches_all_saved_facts_without_revalidation",
    "app.domain.routes.DispatchRoutePlan.matches_route": "test_dispatch_route_matches_all_saved_facts_without_revalidation",
    "app.domain.routes.DispatchRoutePlan.legs": "test_dispatch_route_invariants_and_historical_mapping",
    "app.domain.dispatch_journey.plan_dispatch_journey": "test_dispatch_journey_preserves_leg_speeds_energy_and_boundary",
    "app.services.dispatch_planning.DispatchPlanningService.route": "test_planner_routes_from_checkpoint_and_skips_colocated_pickup",
    "app.services.dispatch_planning.DispatchPlanningService._route_between": "test_planner_routes_from_checkpoint_and_skips_colocated_pickup",
    "app.services.dispatch_planning.DispatchPlanningService.quote": "test_changed_departure_and_provider_failure_never_dispatch",
    "app.repositories.transport_mapping.load_route": "test_dispatch_route_invariants_and_historical_mapping",
    "app.repositories.transport_mapping.load_dispatch_route": "test_dispatch_route_invariants_and_historical_mapping",
    "app.api.v1.dispatch_projection.project_dispatch_route": "test_approach_dispatch_reload_public_privacy_and_offline_arrival",
    "app.repositories.analytics.validate_row": "test_analytics_rejects_corrupt_scalar_fields",
    "app.repositories.analytics.SqliteAnalyticsReader.__init__": "test_analytics_rejects_corrupt_scalar_fields",
    "app.repositories.analytics.SqliteAnalyticsReader.read": "test_analytics_rejects_corrupt_scalar_fields",
    "app.services.analytics.validate_scope": "test_analytics_scope_validation",
    "app.services.analytics.summarize": "test_analytics_scalars_do_not_hydrate_routes",
    "app.services.analytics.breakdown": "test_analytics_scalars_do_not_hydrate_routes",
    "app.services.analytics.AnalyticsService.__init__": "test_analytics_empty_and_utc_boundary",
    "app.services.analytics.AnalyticsService.analyze": "test_analytics_empty_and_utc_boundary",
    "app.api.v1.company.get_analytics": "test_analytics_and_exact_api_require_session",
    "app.bootstrap.build_analytics_service": "test_analytics_and_exact_api_require_session",
    "app.api.v1.map.exact_city": "test_analytics_and_exact_api_require_session",
    "app.api.v1.map.exact_facility": "test_analytics_and_exact_api_require_session",
    "app.services.map_locations.MapLocationService.exact_city": "test_analytics_and_exact_api_require_session",
    "app.services.map_locations.MapLocationService.exact_facility": "test_analytics_and_exact_api_require_session",
    "app.repositories.legacy_import_mapping.LegacyFieldError.__init__": "test_import_modes_reject_nested_loss_without_outputs",
    "app.repositories.legacy_import_mapping.require_legacy_array": "test_nested_cargo_sources_and_arrays_reject_unknown_values",
    "app.repositories.legacy_import_mapping.read_legacy_source": "test_nested_cargo_sources_and_arrays_reject_unknown_values",
    "app.repositories.legacy_import_mapping.read_legacy_sources": "test_nested_cargo_sources_and_arrays_reject_unknown_values",
    "app.repositories.legacy_import_mapping.read_legacy_good": "test_nested_cargo_sources_and_arrays_reject_unknown_values",
    "app.repositories.legacy_import_mapping.read_legacy_route": "test_legacy_route_rejects_unretained_feature_metadata",
    "app.repositories.game_database.SqliteGameDatabase._validate_keys": "test_schema_rejects_missing_or_changed_ownership_keys",
    "app.repositories.game_database.SqliteGameDatabase._validate_guards": "test_schema_rejects_ineffective_unique_index",
    "app.repositories.game_database.schema_sql_tokens": "test_schema_accepts_formatting_but_preserves_literals",
    "app.repositories.game_state.SqliteGameStateRepository.list_active_transports": "test_transport_queries_filter_before_decoding",
    "app.repositories.game_state.SqliteGameStateRepository.list_due_transports": "test_transport_queries_filter_before_decoding",
    "app.repositories.game_state.SqliteGameStateRepository._read_transport": "test_transport_validation_cache_rechecks_changed_rows_and_bounds_memory",
    "app.domain.routes.RouteSnapshot.__post_init__": "test_route_snapshot_rejects_invalid_measurements_and_geometry",
    "app.domain.transports.ActiveTransport.__post_init__": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
    "app.domain.transports.ActiveTransport.is_due": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
    "app.domain.transports.ActiveTransport.settle": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
    "app.repositories.transport_mapping.load_transport": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
    "app.services.game.GameService._get_player": "test_relational_game_use_cases_preserve_atomic_settlement",
    "app.domain.contracts.ContractOffer.__post_init__": "test_contract_offer_domain_rules",
    "app.domain.validation.require_finite": "test_domain_value_validators_reject_invalid_values",
    "app.domain.validation.require_integer": "test_domain_value_validators_reject_invalid_values",
    "app.domain.validation.require_identity": "test_domain_value_validators_reject_invalid_values",
    "app.api.v1.map.list_map_hubs": "test_map_endpoint_requires_session_and_uses_game_provider",
    "app.api.v1.contracts.accept_contract": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.contracts.get_contract": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.contracts.list_contracts": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.contracts.quote_contract": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.contracts.refresh_contracts": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.dashboard.get_dashboard": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.dependencies.get_game_service": "test_auth_api_and_private_game_resources",
    "app.api.v1.fleet.get_vehicle": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.fleet.list_fleet": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.router.build_v1_router": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.system.get_health": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.transports.get_transport": "test_v1_resource_endpoints_and_error_mapping",
    "app.api.v1.transports.list_transports": "test_v1_resource_endpoints_and_error_mapping",
    "app.bootstrap.build_game_runtime": "test_build_game_service_wires_real_provider_adapters",
    "app.config.Settings.from_env": "test_settings_from_env",
    "app.logging_config.JsonFormatter.format": "test_json_formatter_includes_structured_fields",
    "app.logging_config.configure_logging": "test_configure_logging_replaces_root_handler",
    "app.main.create_app": "test_v1_resource_endpoints_and_error_mapping",
    "app.main.lifespan": "test_v1_resource_endpoints_and_error_mapping",
    "app.providers.geocoding.NominatimGeocoder._respect_rate_limit": "test_respect_rate_limit_sleeps_remaining_time",
    "app.providers.geocoding.NominatimGeocoder.geocode": "test_geocode_calls_nominatim_and_caches",
    "app.providers.routing.ValhallaTruckRouter._build_cache_key": "test_build_cache_key_is_stable",
    "app.providers.routing.ValhallaTruckRouter._extract_route": "test_extract_route_supports_geojson_and_rejects_empty",
    "app.providers.routing.ValhallaTruckRouter.route": "test_route_calls_valhalla_and_caches",
    "app.providers.routing.decode_polyline6": "test_decode_polyline6_and_invalid_input",
    "app.services.game.GameService._build_trip": "test_build_trip_contains_tracking_timestamps",
    "app.services.game.GameService._find_contract": "test_find_contract_returns_match_and_raises",
    "app.services.game.GameService._find_vehicle": "test_find_vehicle_returns_match_and_raises",
    "app.services.game.GameService._validate_dispatch": "test_validate_dispatch_checks_location_capacity_mode_and_status",
    "app.services.game.GameService.dashboard": "test_dashboard_returns_product_projection",
    "app.services.game.GameService.dispatch": "test_dispatch_builds_persisted_trip_and_debits_cost",
    "app.services.game.GameService.ensure_initial_state": "test_ensure_initial_state_is_idempotent",
    "app.services.game.GameService.get_contract": "test_list_and_get_contracts_return_real_addresses",
    "app.services.game.GameService.get_transport": "test_list_and_get_transports",
    "app.services.game.GameService.get_vehicle": "test_list_get_and_expand_vehicles",
    "app.services.game.GameService.list_contracts": "test_list_and_get_contracts_return_real_addresses",
    "app.services.game.GameService.list_transports": "test_list_and_get_transports",
    "app.services.game.GameService.list_vehicles": "test_list_get_and_expand_vehicles",
    "app.services.game.GameService.quote_contract": "test_quote_contract_geocodes_routes_and_prices",
    "app.services.game.GameService.reconcile_arrival": "test_reconcile_arrival_moves_vehicle_and_pays",
    "app.services.game.GameService.refresh_contracts": "test_list_and_get_contracts_return_real_addresses",
    "app.services.game.GameService.refresh_market": "test_refresh_market_reuses_fresh_market_and_can_force",
    "app.services.game.GameService.reset": "test_reset_restores_playable_state",
    "app.services.game.GameService.state": "test_state_expands_contract_addresses",
    "app.domain.contracts.ContractOffer.from_snapshot": "test_contract_offer_domain_rules",
    "app.domain.contracts.ContractOffer.is_available": "test_contract_offer_domain_rules",
    "app.domain.game.PlayerState.debit": "test_player_state_domain_rules",
    "app.domain.game.PlayerState.complete_delivery": "test_player_state_domain_rules",
    "app.domain.game.OwnedVehicle.validate_dispatch": "test_owned_vehicle_domain_rules",
    "app.domain.game.OwnedVehicle.start_trip": "test_owned_vehicle_domain_rules",
    "app.domain.game.OwnedVehicle.arrive": "test_owned_vehicle_domain_rules",
    "app.domain.game.OwnedVehicle.apply_model": "test_owned_vehicle_domain_rules",
    "app.services.contract_factory.ContractFactory.build": "test_materialization_snapshots_profile_terms_and_validates_context",
    "app.services.trade_network.TradeNetwork.__init__": "test_reference_cache_and_empty_origin_relations",
    "app.services.trade_network.TradeNetwork._build_trade_options": "test_reference_cache_and_empty_origin_relations",
    "app.services.trade_network.TradeNetwork._index_inbound_profiles": "test_reference_cache_and_empty_origin_relations",
    "app.services.trade_network.TradeNetwork.options_for": "test_reference_cache_and_empty_origin_relations",
    "app.services.market.MarketGenerator.generate": "test_city_coverage_preserves_ids_and_never_invents_relations",
    "app.services.market_scope.MarketScopeResolver.resolve": "test_city_scope_uses_only_distinct_idle_city_identities",
    "app.tracing.TraceIdMiddleware.dispatch": "test_trace_id_middleware_propagates_header_and_context",
    "app.tracing.get_trace_id": "test_get_trace_id_default",
    "app.tracing.new_trace_id": "test_new_trace_id_is_unique_hex",
    "app.web._application_path": "test_product_pages_are_distinct_routes",
    "app.web.contract_detail_page": "test_product_pages_are_distinct_routes",
    "app.web.contracts_page": "test_product_pages_are_distinct_routes",
    "app.web.dashboard_page": "test_product_pages_are_distinct_routes",
    "app.web.fleet_page": "test_product_pages_are_distinct_routes",
    "app.web.transport_detail_page": "test_product_pages_are_distinct_routes",
    "app.web.transports_page": "test_product_pages_are_distinct_routes",
}

FUNCTION_TESTS.update(
    {
        "app.api.v1.auth.check_attempt": "test_auth_api_and_private_game_resources",
        "app.api.v1.auth.current_user": "test_auth_api_and_private_game_resources",
        "app.api.v1.auth.login": "test_auth_api_and_private_game_resources",
        "app.api.v1.auth.logout": "test_auth_api_and_private_game_resources",
        "app.api.v1.auth.register": "test_auth_api_and_private_game_resources",
        "app.api.v1.auth.set_session": "test_auth_api_and_private_game_resources",
        "app.api.v1.dependencies.get_auth_service": "test_auth_api_and_private_game_resources",
        "app.api.v1.dependencies.get_current_user": "test_auth_api_and_private_game_resources",
        "app.api.v1.dependencies.require_same_origin": "test_auth_api_and_private_game_resources",
        "app.api.v1.fleet.get_catalogue": "test_auth_api_and_private_game_resources",
        "app.api.v1.fleet.purchase_vehicle": "test_auth_api_and_private_game_resources",
        "app.api.v1.leaderboard.get_leaderboard": "test_auth_api_and_private_game_resources",
        "app.bootstrap.build_player_service": "test_player_service_isolation_and_atomic_purchases",
        "app.repositories.accounts.AccountRepository.allow_attempt": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.accounts.AccountRepository.create_user": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.accounts.AccountRepository.find_user": "test_migrated_email_uses_existing_password_and_compact_player_id",
        "app.repositories.accounts.AccountRepository.revoke_session": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.accounts.AccountRepository.save_session": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.accounts.AccountRepository.session_user": "test_auth_sessions_expire_revoke_and_throttle",
        "app.services.auth.AuthService.authenticate": "test_auth_sessions_expire_revoke_and_throttle",
        "app.services.auth.AuthService.issue_session": "test_auth_sessions_expire_revoke_and_throttle",
        "app.services.auth.AuthService.register": "test_auth_sessions_expire_revoke_and_throttle",
        "app.services.auth.PasswordHasher.hash_password": "test_password_hashes_are_salted_and_verified",
        "app.services.auth.PasswordHasher.verify_password": "test_password_hashes_are_salted_and_verified",
        "app.services.fleet.FleetService.purchase": "test_player_service_isolation_and_atomic_purchases",
        "app.services.game.GameService._commit_dispatch": "test_simultaneous_dispatch_revalidates_after_routing",
        "app.services.game.GameService._complete_trip": "test_parallel_transports_and_offline_settlement",
        "app.web.leaderboard_page": "test_product_pages_are_distinct_routes",
        "app.web.login_page": "test_product_pages_are_distinct_routes",
    }
)

FUNCTION_TESTS.update(
    {
        "app.bootstrap.build_fleet_service": "test_auth_api_and_private_game_resources",
        "app.bootstrap.build_map_service": "test_map_endpoint_requires_session_and_uses_game_provider",
        "app.api.v1.dependencies.get_fleet_service": "test_auth_api_and_private_game_resources",
        "app.api.v1.dependencies.get_map_service": "test_map_endpoint_requires_session_and_uses_game_provider",
        "app.providers.geocoding.NominatimGeocoder._resolve_address": "test_geocode_calls_nominatim_and_caches",
        "app.providers.routing.ValhallaTruckRouter._resolve_route": "test_route_calls_valhalla_and_caches",
    }
)

FUNCTION_TESTS.update(
    {
        "app.providers.geocoding.NominatimGeocoder.__init__": "test_geocode_calls_nominatim_and_caches",
        "app.providers.routing.ValhallaTruckRouter.__init__": "test_route_calls_valhalla_and_caches",
        "app.providers.validation.parse_coordinates": "test_coordinate_validation_rejects_invalid_values",
        "app.providers.validation.validate_route": "test_route_metrics_must_be_finite_and_positive",
        "app.repositories.accounts.AccountRepository.__init__": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.vehicle_catalogue.SqliteVehicleCatalogue.__init__": "test_catalogue_projects_all_offers_without_writing",
        "app.repositories.vehicle_catalogue.SqliteVehicleCatalogue._read_model": "test_catalogue_failures_are_explicit",
        "app.repositories.vehicle_catalogue.SqliteVehicleCatalogue.list_models": "test_catalogue_projects_all_offers_without_writing",
        "app.services.auth.AuthService.__init__": "test_auth_sessions_expire_revoke_and_throttle",
        "app.services.fleet.FleetService.__init__": "test_purchase_reputation_snapshots_and_rollback",
        "app.services.fleet.FleetService.list_catalogue": "test_catalogue_api_errors_and_vehicle_quote_validation",
        "app.services.game.GameService.__init__": "test_player_service_isolation_and_atomic_purchases",
        "app.services.map_locations.MapLocationService.__init__": "test_map_hubs_resolve_and_preserve_partial_failures",
    }
)

FUNCTION_TESTS.update(
    {
        "app.bootstrap.build_vehicle_catalogue": "test_catalogue_builder_default_path",
        "app.api.v1.dependencies.get_vehicle_catalogue": "test_auth_api_and_private_game_resources",
        "app.repositories.vehicle_catalogue.SqliteVehicleCatalogue._read_image": "test_images_preserve_provenance_and_never_change_gameplay",
        "app.api.v1.vehicle_presentation.present_vehicles": "test_images_preserve_provenance_and_never_change_gameplay",
    }
)

FUNCTION_TESTS.update(
    {
        "app.services.fleet.build_owned_vehicle": "test_starter_uses_catalogue_snapshot_and_preserves_existing_accounts",
        "app.services.fleet.create_starter_vehicle": "test_starter_uses_catalogue_snapshot_and_preserves_existing_accounts",
    }
)

FUNCTION_TESTS.update(
    {
        "app.services.game.GameService._ensure_initial_state": "test_initialization_direct_failure_is_atomic",
        "app.bootstrap.build_profile_maintenance_service": "test_profile_update_preserves_other_players_and_trip_snapshots",
        "app.bootstrap.build_profile_maintenance_service.player_unit_of_work_factory": "test_profile_update_preserves_other_players_and_trip_snapshots",
        "app.repositories.database_backup.backup_database": "test_backup_reads_committed_wal_and_refuses_overwrite",
        "app.services.profile_maintenance.ProfileMaintenanceService.__init__": "test_profile_update_preserves_other_players_and_trip_snapshots",
        "app.services.profile_maintenance.ProfileMaintenanceService.update_profile": "test_maintenance_write_failure_rolls_back_and_retains_unselected",
        "app.services.profile_maintenance.validate_assignments": "test_maintenance_validation_preserves_state",
        "app.services.game.GameService.ensure_initial_state": "test_initialization_direct_failure_is_atomic",
        "app.main.lifespan": "test_lifespan_cleans_up_partial_start_and_shutdown",
    }
)

FUNCTION_TESTS["app.services.game.GameService._commit_dispatch"] = (
    "test_dispatch_rejects_offer_changed_after_quote"
)

FUNCTION_TESTS.update(
    {
        "app.api.v1.map.list_map_facilities": "test_map_endpoint_requires_session_and_uses_game_provider",
        "app.bootstrap.build_world_catalogue": "test_world_catalogue_composition_uses_explicit_path_without_game_state",
        "app.domain.cargo.NhmProduct.is_compatible_with": "test_nhm_cargo_profiles_follow_parent_hierarchy",
        "app.domain.world.Facility.has_verified_location": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.Facility.location_snapshot": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.Facility.inbound_profiles": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.Facility.is_routable": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.Facility.outbound_profiles": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.FacilityQuery.includes": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.FacilityQuery.parse": "test_world_snapshot_identity_provenance_and_query",
        "app.main.world_catalogue_error": "test_map_endpoint_requires_session_and_uses_game_provider",
        "app.repositories.cached_world_catalogue.CachedWorldCatalogue.__init__": "test_cached_world_catalogue_reads_source_once",
        "app.repositories.cached_world_catalogue.CachedWorldCatalogue.read": "test_cached_world_catalogue_reads_source_once",
        "app.repositories.world_catalogue.SqliteWorldCatalogue.__init__": "test_world_repository_readonly_and_cleanup",
        "app.repositories.world_catalogue.SqliteWorldCatalogue.read": "test_world_repository_readonly_and_cleanup",
        "app.repositories.world_catalogue.read_cargo": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.read_nhm_ancestors": "test_world_snapshot_identity_provenance_and_query",
        "app.repositories.world_catalogue.read_companies": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.read_facility": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.read_world_snapshot": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.source_reference": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.validate_uid": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.validate_world_schema": "test_world_repository_rejects_incompatible_data",
        "app.services.fleet.resolve_delivery_facility": "test_delivery_requires_verified_catalogue_endpoint",
        "app.services.map_locations.MapLocationService.list_facilities": "test_map_hubs_resolve_and_preserve_partial_failures",
    }
)

FUNCTION_TESTS.update(
    {
        "app.api.v1.dependencies.get_traffic_reader": "test_multiplayer_map_endpoint_requires_login_and_shares_other_players",
        "app.api.v1.map.list_map_traffic": "test_multiplayer_map_endpoint_requires_login_and_shares_other_players",
        "app.bootstrap.build_traffic_reader": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.api.v1.traffic_projection.project_traffic": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.domain.company_colors.player_color": "test_player_color_is_stable_and_changes_between_users",
    }
)

FUNCTION_TESTS.update(
    {
        "app.domain.game.PlayerState.__init__": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.PlayerState.replace_cash": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.__init__": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.PlayerState.cash": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.PlayerState.completed": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.PlayerState.reputation": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.id": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.name": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.mode": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.capacity_tons": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.status": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.model_id": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.operating_cost_eur_per_km": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.facility_uid": "test_entity_construction_and_mutation_are_guarded",
        "app.domain.game.OwnedVehicle.location": "test_entity_construction_and_mutation_are_guarded",
    }
)

FUNCTION_TESTS.update(
    {
        "app.repositories.game_database.SqliteGameDatabase.__init__": "test_database_schema_rejects_old_and_unknown_files",
        "app.repositories.game_database.SqliteGameDatabase.connect": "test_database_schema_rejects_old_and_unknown_files",
        "app.repositories.game_database.SqliteGameDatabase.initialize": "test_database_schema_rejects_old_and_unknown_files",
        "app.repositories.game_database.SqliteGameDatabase.transaction": "test_unit_of_work_rolls_back_nested_writes_and_closes",
        "app.repositories.game_state.SqliteGameStateRepository.__init__": "test_unit_of_work_rolls_back_nested_writes_and_closes",
        "app.repositories.game_state.SqliteGameStateRepository.get_player": "test_unit_of_work_rolls_back_nested_writes_and_closes",
        "app.repositories.game_state.SqliteGameStateRepository.save_player": "test_unit_of_work_rolls_back_nested_writes_and_closes",
        "app.repositories.game_state.SqliteGameStateRepository.list_vehicles": "test_relational_entities_roundtrip_isolate_and_protect_history",
        "app.repositories.game_state.SqliteGameStateRepository.save_vehicle": "test_relational_entities_roundtrip_isolate_and_protect_history",
        "app.repositories.game_state.SqliteGameStateRepository.list_offers": "test_relational_entities_roundtrip_isolate_and_protect_history",
        "app.repositories.game_state.SqliteGameStateRepository.replace_offers": "test_relational_entities_roundtrip_isolate_and_protect_history",
        "app.repositories.game_state.SqliteGameStateRepository.remove_offer": "test_relational_entities_roundtrip_isolate_and_protect_history",
        "app.repositories.game_state.SqliteGameStateRepository.list_transports": "test_relational_entities_roundtrip_isolate_and_protect_history",
        "app.repositories.game_state.SqliteGameStateRepository.save_transport": "test_relational_entities_roundtrip_isolate_and_protect_history",
        "app.repositories.game_state.SqliteGameStateRepository.reset": "test_relational_entities_roundtrip_isolate_and_protect_history",
        "app.repositories.game_state.SqliteGameUnitOfWork.__init__": "test_unit_of_work_rolls_back_nested_writes_and_closes",
        "app.repositories.game_state.SqliteGameUnitOfWork.transaction": "test_unit_of_work_rolls_back_nested_writes_and_closes",
        "app.repositories.game_state.load_vehicle_record": "test_snapshot_envelopes_and_corrupt_records_fail_explicitly",
        "app.repositories.game_state.load_offer_record": "test_snapshot_envelopes_and_corrupt_records_fail_explicitly",
        "app.repositories.game_state.load_transport_record": "test_snapshot_envelopes_and_corrupt_records_fail_explicitly",
        "app.repositories.state_snapshots.encode_snapshot": "test_snapshot_envelopes_and_corrupt_records_fail_explicitly",
        "app.repositories.state_snapshots.decode_snapshot": "test_snapshot_envelopes_and_corrupt_records_fail_explicitly",
    }
)

FUNCTION_TESTS[
    "app.repositories.game_database.SqliteGameDatabase._validate_structure"
] = "test_schema_structure_rejects_missing_columns_and_guards"
FUNCTION_TESTS.update(
    {
        "app.repositories.leaderboard.SqliteLeaderboardReader.__init__": "test_relational_public_reads_preserve_privacy_and_offline_progress",
        "app.repositories.leaderboard.SqliteLeaderboardReader.list_ranking": "test_relational_public_reads_preserve_privacy_and_offline_progress",
        "app.repositories.relational_traffic.SqliteTrafficReader.__init__": "test_relational_public_reads_preserve_privacy_and_offline_progress",
        "app.repositories.relational_traffic.SqliteTrafficReader.list_active_transports": "test_relational_public_reads_preserve_privacy_and_offline_progress",
        "app.repositories.relational_traffic.project_traffic_row": "test_relational_public_reads_preserve_privacy_and_offline_progress",
        "app.repositories.provider_cache.SqliteProviderCache.__init__": "test_provider_cache_roundtrip_replaces_invalid_documents",
        "app.repositories.provider_cache.SqliteProviderCache.get_route": "test_provider_cache_roundtrip_replaces_invalid_documents",
        "app.repositories.provider_cache.SqliteProviderCache.put_route": "test_provider_cache_roundtrip_replaces_invalid_documents",
        "app.repositories.provider_cache.SqliteProviderCache.get_geocode": "test_provider_cache_roundtrip_replaces_invalid_documents",
        "app.repositories.provider_cache.SqliteProviderCache.put_geocode": "test_provider_cache_roundtrip_replaces_invalid_documents",
        "app.bootstrap.build_leaderboard_reader": "test_leaderboard_counts_offline_arrivals_without_double_counting",
        "app.api.v1.dependencies.get_leaderboard_reader": "test_auth_api_and_private_game_resources",
    }
)

FUNCTION_TESTS.update(
    {
        "app.api.v1.game_projection.project_contract": "test_contract_projection_retains_endpoint_snapshots",
        "app.api.v1.game_projection.project_vehicle": "test_api_projection_never_invents_missing_vehicle_locations",
        "app.api.v1.game_projection.project_quote": "test_vehicle_quotes_and_legacy_snapshots_remain_compatible",
        "app.api.v1.game_projection.project_transport": "test_relational_game_use_cases_preserve_atomic_settlement",
        "app.api.v1.game_projection.project_state": "test_reset_restores_playable_state",
        "app.api.v1.game_projection.project_dashboard": "test_dashboard_returns_product_projection",
        "app.api.v1.game_projection.project_catalogue": "test_catalogue_builder_default_path",
        "app.providers.routing.route_cache_document": "test_route_calls_valhalla_and_caches",
    }
)

FUNCTION_TESTS.update(
    {
        "app.repositories.snapshot_mapping.load_location": "test_canonical_snapshots_preserve_facts_and_reject_public_documents",
        "app.repositories.snapshot_mapping.load_product": "test_canonical_snapshots_preserve_facts_and_reject_public_documents",
        "app.repositories.snapshot_mapping.load_offer": "test_canonical_snapshots_preserve_facts_and_reject_public_documents",
    }
)

FUNCTION_TESTS.update(
    {
        "app.api.v1.location_projection.project_location": "test_world_snapshot_identity_provenance_and_query",
        "app.api.v1.game_projection.project_player": "test_player_state_domain_rules",
    }
)

FUNCTION_TESTS.update(
    {
        "app.domain.cargo.NhmProduct.__post_init__": "test_nhm_entities_reject_invalid_hierarchies_and_weights",
        "app.domain.cargo.FacilityNhmProfile.__post_init__": "test_nhm_entities_reject_invalid_hierarchies_and_weights",
        "app.repositories.snapshot_mapping.load_profile": "test_canonical_snapshots_preserve_facts_and_reject_public_documents",
        "app.api.v1.game_projection.project_nhm_profile": "test_nhm_profile_projection_retains_fields_without_mutating_products",
    }
)

FUNCTION_TESTS.update(
    {
        "app.domain.geography.Coordinates.__post_init__": "test_geography_values_reject_invalid_coordinates_and_identities",
        "app.domain.geography.Country.__post_init__": "test_geography_values_reject_invalid_coordinates_and_identities",
        "app.domain.geography.City.__post_init__": "test_geography_values_reject_invalid_coordinates_and_identities",
        "app.domain.geography.Address.display_text": "test_geography_values_reject_invalid_coordinates_and_identities",
        "app.services.world_geography.validate_geography_mapping": "test_geography_mapping_rejects_duplicate_or_changed_assignments",
        "app.bootstrap.build_geography_migration": "test_geography_migration_reconciles_identity_and_is_idempotent",
        "app.repositories.world_geography.WorldGeographyRepository.__init__": "test_geography_migration_reconciles_identity_and_is_idempotent",
        "app.repositories.world_geography.WorldGeographyRepository.normalize": "test_geography_migration_rolls_back_and_requires_backup",
        "app.repositories.world_geography.catalogue_identities": "test_geography_migration_reconciles_identity_and_is_idempotent",
        "app.repositories.world_geography.validate_source_geography": "test_geography_mapping_rejects_duplicate_or_changed_assignments",
        "app.repositories.world_geography.normalize_geography_tables": "test_geography_migration_rolls_back_and_requires_backup",
        "app.repositories.world_geography.rebuild_geographical_table": "test_geography_migration_rolls_back_and_requires_backup",
        "app.repositories.world_geography.validate_normalized_geography": "test_geography_migration_reconciles_identity_and_is_idempotent",
    }
)

FUNCTION_TESTS.update(
    {
        "app.repositories.world_geography_reader.read_countries": "test_world_geography_shares_identities_and_rejects_broken_references",
        "app.repositories.world_geography_reader.read_cities": "test_world_geography_shares_identities_and_rejects_broken_references",
        "app.repositories.snapshot_mapping.load_city": "test_canonical_snapshots_preserve_facts_and_reject_public_documents",
    }
)

FUNCTION_TESTS.update(
    {
        "app.domain.world_scopes.require_unique_reference": "test_world_scopes_report_ambiguity_and_keep_uid_queries_exact",
        "app.domain.world_scopes.select_city": "test_world_scopes_report_ambiguity_and_keep_uid_queries_exact",
        "app.domain.world_scopes.select_company": "test_world_scopes_report_ambiguity_and_keep_uid_queries_exact",
        "app.domain.world_scopes.scope_company": "test_world_scopes_filter_facilities_without_reparenting_companies",
        "app.domain.world_scopes.WorldScope.facilities": "test_world_scopes_filter_facilities_without_reparenting_companies",
        "app.domain.world_scopes.WorldScope.facility": "test_world_scopes_report_ambiguity_and_keep_uid_queries_exact",
        "app.domain.world_scopes.WorldScope.country": "test_world_scopes_report_ambiguity_and_keep_uid_queries_exact",
        "app.domain.world_scopes.WorldScope.city": "test_world_scopes_report_ambiguity_and_keep_uid_queries_exact",
        "app.domain.world_scopes.WorldScope.company": "test_world_scopes_report_ambiguity_and_keep_uid_queries_exact",
        "app.domain.world_scopes.WorldScope.query": "test_world_scopes_filter_facilities_without_reparenting_companies",
        "app.domain.world_scopes.CountryScope.facilities": "test_world_scopes_filter_facilities_without_reparenting_companies",
        "app.domain.world_scopes.CountryScope.city": "test_world_scopes_report_ambiguity_and_keep_uid_queries_exact",
        "app.domain.world_scopes.CountryScope.company": "test_world_scopes_filter_facilities_without_reparenting_companies",
        "app.domain.world_scopes.CityScope.facilities": "test_world_scopes_filter_facilities_without_reparenting_companies",
        "app.domain.world_scopes.CityScope.company": "test_world_scopes_filter_facilities_without_reparenting_companies",
    }
)

FUNCTION_TESTS["app.domain.pricing.calculate_price"] = (
    "test_pricing_quote_uses_distance_and_cargo_rate"
)

FUNCTION_TESTS.update(
    {
        "app.bootstrap.build_game_importer": "test_import_cli_requires_backup_and_separate_paths",
        "app.repositories.legacy_game_import.read_legacy_json": "test_offline_import_rejects_corruption_and_unknown_state",
        "app.repositories.legacy_game_import.validate_profile_links": "test_offline_import_rejects_corruption_and_unknown_state",
        "app.repositories.legacy_game_import.summarize_import": "test_offline_import_preserves_profiles_history_and_settles_once",
        "app.repositories.legacy_game_import.reconcile_import": "test_import_reconciliation_detects_retained_value_changes",
        "app.repositories.legacy_game_import.LegacyGameImporter.__init__": "test_offline_import_rejects_corruption_and_unknown_state",
        "app.repositories.legacy_game_import.LegacyGameImporter.inspect": "test_offline_import_rejects_corruption_and_unknown_state",
        "app.repositories.legacy_game_import.LegacyGameImporter._read_profiles": "test_offline_import_rejects_corruption_and_unknown_state",
        "app.repositories.legacy_game_import.LegacyGameImporter._read_profile": "test_offline_import_rejects_corruption_and_unknown_state",
        "app.repositories.legacy_game_import.LegacyGameImporter.import_to": "test_import_rolls_back_reconciliation_and_write_failures",
        "app.repositories.legacy_game_import.LegacyGameImporter._write_profiles": "test_import_rolls_back_reconciliation_and_write_failures",
        "app.repositories.legacy_import_mapping.LegacySnapshotReader.__init__": "test_legacy_snapshot_decoding_rejects_conflicting_facts",
        "app.repositories.legacy_import_mapping.LegacySnapshotReader.location": "test_legacy_snapshot_decoding_rejects_conflicting_facts",
        "app.repositories.legacy_import_mapping.LegacySnapshotReader.vehicle": "test_legacy_snapshot_decoding_rejects_conflicting_facts",
        "app.repositories.legacy_import_mapping.LegacySnapshotReader.offer": "test_legacy_snapshot_decoding_rejects_conflicting_facts",
        "app.repositories.legacy_import_mapping.LegacySnapshotReader.transport": "test_legacy_snapshot_decoding_rejects_conflicting_facts",
        "app.repositories.legacy_import_mapping.read_legacy_profile": "test_legacy_snapshot_decoding_rejects_conflicting_facts",
    }
)

FUNCTION_TESTS[
    "app.repositories.legacy_import_mapping.reject_unknown_fields"
] = "test_legacy_snapshot_decoding_rejects_conflicting_facts"

FUNCTION_TESTS.update(
    {
        "app.domain.cargo.DocumentedCargo.__post_init__": "test_historical_terms_preserve_non_nhm_evidence_and_reject_invalid_values",
        "app.domain.contracts.HistoricalContractSnapshot.__post_init__": "test_historical_terms_preserve_non_nhm_evidence_and_reject_invalid_values",
        "app.domain.contracts.HistoricalContractSnapshot.from_offer": "test_historical_terms_preserve_non_nhm_evidence_and_reject_invalid_values",
        "app.repositories.snapshot_mapping.load_documented_cargo": "test_historical_terms_preserve_non_nhm_evidence_and_reject_invalid_values",
        "app.repositories.snapshot_mapping.load_historical_contract": "test_historical_terms_preserve_non_nhm_evidence_and_reject_invalid_values",
        "app.repositories.legacy_import_mapping.read_documented_cargo": "test_old_reference_documents_and_retired_offers_are_explicitly_handled",
        "app.repositories.legacy_import_mapping.LegacySnapshotReader.historical_contract": "test_old_reference_documents_and_retired_offers_are_explicitly_handled",
        "app.repositories.legacy_import_mapping.LegacySnapshotReader.validate_obsolete_offer": "test_old_reference_documents_and_retired_offers_are_explicitly_handled",
        "app.repositories.legacy_game_import.LegacyGameImporter._exclude_global_demo": "test_global_demo_exclusion_requires_explicit_choice",
    }
)

FUNCTION_TESTS["app.main.persistence_error"] = (
    "test_persistence_outage_does_not_expose_database_details"
)

FUNCTION_TESTS.update(
    {
        "app.domain.energy.EnergyProfile.__post_init__": "test_energy_profile_validates_measurements_and_consumption",
        "app.domain.energy.EnergyProfile.validate_level": "test_energy_profile_validates_measurements_and_consumption",
        "app.domain.energy.EnergyProfile.consumption_for": "test_energy_profile_validates_measurements_and_consumption",
        "app.domain.vehicles.VehicleModel.__post_init__": "test_catalogue_energy_values_match_all_fourteen_models",
        "app.repositories.vehicle_catalogue.read_energy_profile": "test_catalogue_rejects_incomplete_energy",
    }
)

FUNCTION_TESTS.update(
    {
        "app.domain.journeys.JourneySegment.__post_init__": "test_journey_rejects_inconsistent_intervals_and_energy",
        "app.domain.journeys.JourneyPlan.__post_init__": "test_journey_rejects_inconsistent_intervals_and_energy",
        "app.domain.journeys.JourneyPlan._validate_segment_energy": "test_journey_rejects_inconsistent_intervals_and_energy",
        "app.domain.journeys.JourneyPlan.duration_seconds": "test_journey_reserve_stops_and_speed_limits",
        "app.domain.journeys.JourneyPlan.driving_seconds": "test_journey_reserve_stops_and_speed_limits",
        "app.domain.journeys.JourneyPlan.stop_count": "test_journey_reserve_stops_and_speed_limits",
        "app.domain.journeys.JourneyPlan.progress_at": "test_journey_progress_and_shared_timeline_boundaries",
        "app.domain.journeys.plan_journey": "test_journey_reserve_stops_and_speed_limits",
        "app.domain.journeys.unmetered_journey": "test_journey_progress_and_shared_timeline_boundaries",
    }
)

FUNCTION_TESTS.update(
    {
        "app.domain.game.OwnedVehicle.consume_energy": "test_owned_energy_is_encapsulated_and_model_changes_preserve_fraction",
        "app.domain.game.OwnedVehicle.refill_energy": "test_owned_energy_is_encapsulated_and_model_changes_preserve_fraction",
        "app.domain.game.OwnedVehicle.energy": "test_owned_energy_is_encapsulated_and_model_changes_preserve_fraction",
        "app.domain.game.OwnedVehicle.energy_level": "test_owned_energy_is_encapsulated_and_model_changes_preserve_fraction",
        "app.domain.game.OwnedVehicle.top_speed_kmh": "test_owned_energy_is_encapsulated_and_model_changes_preserve_fraction",
        "app.domain.transports.ActiveTransport.progress_at": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
        "app.repositories.transport_mapping.load_journey": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
        "app.bootstrap.build_energy_upgrade": "test_energy_upgrade_builder_requires_catalogue",
        "app.repositories.energy_upgrade.VehicleEnergyUpgradeRepository.__init__": "test_energy_upgrade_rejects_invalid_source_without_output",
        "app.repositories.energy_upgrade.VehicleEnergyUpgradeRepository.inspect": "test_energy_upgrade_rejects_invalid_source_without_output",
        "app.repositories.energy_upgrade.VehicleEnergyUpgradeRepository.upgrade_to": "test_energy_upgrade_reconciliation_failure_removes_target",
        "app.repositories.energy_upgrade.VehicleEnergyUpgradeRepository._read_source": "test_energy_upgrade_rejects_invalid_source_without_output",
        "app.repositories.energy_upgrade.VehicleEnergyUpgradeRepository._validate_source_schema": "test_energy_upgrade_rejects_invalid_source_without_output",
        "app.repositories.energy_upgrade.VehicleEnergyUpgradeRepository._convert_record": "test_energy_upgrade_rejects_invalid_source_without_output",
        "app.repositories.energy_upgrade.VehicleEnergyUpgradeRepository._write_inventory": "test_energy_upgrade_reconciliation_failure_removes_target",
        "app.repositories.energy_upgrade.VehicleEnergyUpgradeRepository._verify_inventory": "test_energy_upgrade_reconciliation_failure_removes_target",
    }
)

FUNCTION_TESTS.update(
    {
        "app.services.game.GameService._calculate_quote": "test_energy_quote_dispatch_pause_and_offline_settlement",
        "app.api.v1.game_projection.project_fleet": "test_energy_quote_dispatch_pause_and_offline_settlement",
    }
)


FUNCTION_TESTS.update(
    {
        "app.domain.market_profiles.require_unit_weight": "test_market_profile_small_values_reject_invalid_weights",
        "app.domain.market_profiles.vehicle_scale_for_segment": "test_market_profile_small_values_reject_invalid_weights",
        "app.domain.market_profiles.TransportCapability.__post_init__": "test_market_profile_small_values_reject_invalid_weights",
        "app.domain.market_profiles.DistanceLoadProfile.__post_init__": "test_market_profile_small_values_reject_invalid_weights",
        "app.domain.market_profiles.VehicleScaleProfile.__post_init__": "test_market_profile_small_values_reject_invalid_weights",
        "app.domain.market_profiles.NhmMarketProfile.__post_init__": "test_market_profiles_require_complete_immutable_values",
        "app.repositories.market_profile_reader.read_market_profiles": "test_world_market_profile_corruption_is_rejected",
        "app.repositories.vehicle_catalogue.read_transport_capabilities": "test_vehicle_market_profile_corruption_is_rejected",
    }
)

FUNCTION_TESTS.update(
    {
        "app.bootstrap.build_market_generator": "test_city_coverage_preserves_ids_and_never_invents_relations",
        "app.domain.game.OwnedVehicle.reposition_within_city": "test_reposition_rejects_busy_other_city_and_missing_location",
        "app.domain.market_calculations.distance_band": "test_distance_and_tonnage_are_deterministic_and_bounded",
        "app.domain.market_calculations.great_circle_km": "test_distance_and_tonnage_are_deterministic_and_bounded",
        "app.domain.market_calculations.shipment_tons": "test_distance_and_tonnage_are_deterministic_and_bounded",
        "app.domain.market_calculations.evidence_weight": "test_candidate_compatibility_and_weighting_are_separate",
        "app.domain.market_compatibility.market_vehicle": "test_candidate_compatibility_and_weighting_are_separate",
        "app.domain.market_compatibility.vehicle_suitability": "test_candidate_compatibility_and_weighting_are_separate",
        "app.domain.market_compatibility.can_carry_offer": "test_candidate_compatibility_and_weighting_are_separate",
        "app.domain.market.MarketVehicle.__post_init__": "test_candidate_value_invariants_reject_invalid_context",
        "app.domain.market.CompatibleVehicle.__post_init__": "test_candidate_value_invariants_reject_invalid_context",
        "app.domain.market.MarketCandidate.__post_init__": "test_candidate_value_invariants_reject_invalid_context",
        "app.domain.market_terms.OfferMarketContext.__post_init__": "test_materialization_snapshots_profile_terms_and_validates_context",
        "app.domain.market_terms.OfferMarketContext.validate_tonnage": "test_materialization_snapshots_profile_terms_and_validates_context",
        "app.repositories.snapshot_mapping.load_market_context": "test_historical_v2_and_missing_context_roundtrip_without_catalogue",
        "app.services.game.GameService.contract_choices": "test_retention_prunes_v1_unavailable_fleet_and_expiring_offers",
        "app.services.market_candidates.MarketCandidateService.__init__": "test_reference_cache_and_empty_origin_relations",
        "app.services.market_candidates.MarketCandidateService.reference": "test_reference_cache_and_empty_origin_relations",
        "app.services.market_candidates.MarketCandidateService.resolve_fleet": "test_model_resolution_is_explicit_and_saved_capacity_wins",
        "app.services.market_candidates.MarketCandidateService.build": "test_candidate_compatibility_and_weighting_are_separate",
        "app.services.market_candidates.MarketCandidateService._candidate": "test_candidate_compatibility_and_weighting_are_separate",
        "app.services.market_candidates.MarketCandidateService.eligible_ids": "test_retention_requires_structure_and_actual_vehicle_compatibility",
        "app.services.market_candidates.MarketCandidateService.structurally_current": "test_retention_requires_structure_and_actual_vehicle_compatibility",
        "app.services.market_coverage.CityCoverage.record": "test_city_coverage_preserves_ids_and_never_invents_relations",
        "app.services.market_coverage.CityCoverage.rank": "test_city_coverage_preserves_ids_and_never_invents_relations",
        "app.services.market_coverage.CityCoverage.add_candidate": "test_city_coverage_preserves_ids_and_never_invents_relations",
        "app.services.market_coverage.MarketCoverageService.plan": "test_city_coverage_preserves_ids_and_never_invents_relations",
        "app.services.market_coverage.MarketCoverageService._plan_city": "test_city_coverage_preserves_ids_and_never_invents_relations",
        "app.services.market_coverage.MarketCoverageService._select": "test_city_coverage_preserves_ids_and_never_invents_relations",
        "app.services.market_lifecycle.MarketLifecycleService.refresh": "test_retention_prunes_v1_unavailable_fleet_and_expiring_offers",
        "app.services.market_lifecycle.MarketLifecycleService._retained": "test_retention_prunes_v1_unavailable_fleet_and_expiring_offers",
        "app.services.market_lifecycle.MarketLifecycleService._store": "test_refill_uses_separate_transaction_and_rolls_back_only_new_offers",
        "app.services.market_lifecycle.MarketLifecycleService.present": "test_retention_prunes_v1_unavailable_fleet_and_expiring_offers",
        "app.services.market_lifecycle.MarketLifecycleService.prune_in_transaction": "test_same_city_dispatch_preserves_departure_and_prunes_atomically",
        "app.services.market_lifecycle.MarketLifecycleService.refill_after_commit": "test_refill_failure_cannot_undo_committed_dispatch",
    }
)


FUNCTION_TESTS.update(
    {
        "app.domain.game.OwnedVehicle.restore_location": (
            "test_dispatch_resolves_only_missing_exact_facility_snapshot"
        ),
    }
)


FUNCTION_TESTS.update(
    {
        "app.main.vehicle_catalogue_error": "test_market_reference_errors_have_explicit_http_responses",
        "app.main.unresolved_vehicle_model": "test_market_reference_errors_have_explicit_http_responses",
    }
)

FUNCTION_TESTS["app.domain.market_calculations.biased_load_factor"] = (
    "test_load_distribution_rejects_invalid_inputs_and_preserves_endpoints"
)

FUNCTION_TESTS.update(
    {
        "app.domain.economics.whole_euros": "test_purchase_costs_charge_only_planned_energy_and_reconcile",
        "app.domain.economics.VehicleCostProfile.__post_init__": "test_cost_values_reject_invalid_or_inconsistent_components",
        "app.domain.economics.EnergyPurchase.__post_init__": "test_cost_values_reject_invalid_or_inconsistent_components",
        "app.domain.economics.CostBreakdown.__post_init__": "test_cost_values_reject_invalid_or_inconsistent_components",
        "app.domain.economics.journey_costs": "test_cost_values_reject_invalid_or_inconsistent_components",
        "app.domain.tariffs.FreightTariff.__post_init__": "test_tariff_uses_concrete_nhm_and_explicit_maintenance",
        "app.domain.tariffs.freight_tariff": "test_tariff_uses_concrete_nhm_and_explicit_maintenance",
        "app.services.cost_profiles.VehicleCostResolver.resolve": "test_tariff_uses_concrete_nhm_and_explicit_maintenance",
        "app.repositories.transport_mapping.load_cost_breakdown": "test_cost_values_reject_invalid_or_inconsistent_components",
        "app.repositories.market_startup.SqliteMarketStartupStore.transaction": "test_startup_rebuild_is_global_atomic_and_does_not_route",
        "app.repositories.market_startup.SqliteMarketStartupStore.player_ids": "test_startup_rebuild_is_global_atomic_and_does_not_route",
        "app.services.market_startup.MarketStartupService.rebuild": "test_startup_rebuild_is_global_atomic_and_does_not_route",
        "app.bootstrap.build_market_startup": "test_startup_rebuild_is_global_atomic_and_does_not_route",
        "app.bootstrap.build_market_startup.lifecycle": "test_startup_rebuild_is_global_atomic_and_does_not_route",
        "app.bootstrap.build_preferences": "test_preferences_are_account_scoped_persistent_and_palette_validated",
        "app.repositories.preferences.SqlitePreferenceStore.__init__": "test_preferences_are_account_scoped_persistent_and_palette_validated",
        "app.repositories.preferences.SqlitePreferenceStore.transaction": "test_preferences_are_account_scoped_persistent_and_palette_validated",
        "app.repositories.preferences.SqlitePreferenceStore.color": "test_preferences_are_account_scoped_persistent_and_palette_validated",
        "app.repositories.preferences.SqlitePreferenceStore.save_color": "test_preferences_are_account_scoped_persistent_and_palette_validated",
        "app.services.preferences.PreferenceService.read": "test_preferences_are_account_scoped_persistent_and_palette_validated",
        "app.services.preferences.PreferenceService.update": "test_preferences_are_account_scoped_persistent_and_palette_validated",
        "app.domain.analytics_labels.vehicle_labels": "test_analytics_labels_keep_identity_and_disambiguate_current_names",
        "app.api.v1.auth.preferences": "test_color_preference_http_validation_and_session_isolation",
        "app.api.v1.auth.update_preferences": "test_color_preference_http_validation_and_session_isolation",
    }
)

FUNCTION_TESTS["app.domain.economy_audit.audit_economy_case"] = (
    "test_economy_audit_uses_actual_distribution_and_separates_cashflow"
)


FUNCTION_TESTS.update(
    {
        "app.repositories.cached_vehicle_catalogue.CachedVehicleCatalogue.__init__": "test_vehicle_reference_cache_retries_failure_then_reuses_revision",
        "app.repositories.cached_vehicle_catalogue.CachedVehicleCatalogue.list_models": "test_vehicle_reference_cache_retries_failure_then_reuses_revision",
    }
)

FUNCTION_TESTS.update(
    {
        "app.domain.routing_anchors.RoutingAnchor.__post_init__": (
            "test_certified_access_is_stable_and_legacy_access_is_only_candidate"
        ),
        "app.providers.routing_anchor.ValhallaTruckAnchorLocator.__init__": (
            "test_candidates_never_publish_before_connection_proof"
        ),
        "app.providers.routing_anchor.ValhallaTruckAnchorLocator.locate": (
            "test_routing_anchor_provider_temporarily_offline"
        ),
        "app.providers.routing_anchor.ValhallaTruckAnchorLocator._correlated_location": (
            "test_candidates_never_publish_before_connection_proof"
        ),
        "app.providers.routing_anchor.ValhallaTruckAnchorLocator._revision": (
            "test_candidates_never_publish_before_connection_proof"
        ),
        "app.repositories.routing_anchors.SqliteRoutingAnchorRepository.__init__": (
            "test_routing_anchor_repository_roundtrip"
        ),
        "app.repositories.routing_anchors.SqliteRoutingAnchorRepository.get": (
            "test_routing_anchor_repository_roundtrip"
        ),
        "app.repositories.routing_anchors.SqliteRoutingAnchorRepository.put": (
            "test_routing_anchor_repository_roundtrip"
        ),
        "app.services.routing_anchors.RoutingAnchorResolver.__init__": (
            "test_candidates_never_publish_before_connection_proof"
        ),
        "app.services.routing_anchors.RoutingAnchorResolver.resolve": (
            "test_address_and_missing_coordinate_fallbacks_are_bounded"
        ),
    }
)

FUNCTION_TESTS["app.bootstrap.build_routing_anchor_resolver"] = (
    "test_candidates_never_publish_before_connection_proof"
)

# routing-anchor-standards-2026-09-26
FUNCTION_TESTS.update(
    {
        "app.domain.routing_anchors.RoutingAnchor.__post_init__": (
            "test_routing_anchor_rejects_coordinate_status_mismatches"
        ),
        "app.providers.routing_anchor.ValhallaTruckAnchorLocator.__init__": (
            "test_truck_anchor_locator_uses_real_locate_edge_shape"
        ),
        "app.providers.routing_anchor.ValhallaTruckAnchorLocator.locate": (
            "test_truck_anchor_locator_uses_real_locate_edge_shape"
        ),
        "app.providers.routing_anchor.ValhallaTruckAnchorLocator._correlated_location": (
            "test_truck_anchor_locator_rejects_missing_or_malformed_edges"
        ),
        "app.providers.routing_anchor.ValhallaTruckAnchorLocator._revision": (
            "test_truck_anchor_locator_uses_real_locate_edge_shape"
        ),
        "app.repositories.routing_anchors.SqliteRoutingAnchorRepository.__init__": (
            "test_routing_anchor_repository_roundtrip"
        ),
        "app.repositories.routing_anchors.SqliteRoutingAnchorRepository.get": (
            "test_routing_anchor_repository_rejects_unknown_persisted_status"
        ),
        "app.repositories.routing_anchors.SqliteRoutingAnchorRepository.put": (
            "test_routing_anchor_repository_roundtrip"
        ),
        "app.services.routing_anchors.RoutingAnchorResolver.__init__": (
            "test_routing_anchor_resolver_rejects_nonpositive_snap_limit"
        ),
        "app.services.routing_anchors.RoutingAnchorResolver.resolve": (
            "test_address_and_missing_coordinate_fallbacks_are_bounded"
        ),
        "app.bootstrap.build_routing_anchor_resolver": (
            "test_build_game_service_wires_real_provider_adapters"
        ),
        "app.services.dispatch_planning.DispatchPlanningService.route": (
            "test_dispatch_approach_uses_facility_identity_not_display_coordinate"
        ),
        "app.services.dispatch_planning.DispatchPlanningService._route_between": (
            "test_dispatch_routing_uses_anchors_not_display_coordinates"
        ),
    }
)


FUNCTION_TESTS.update(
    {
        "app.api.v1.analytics_projection.project_analytics": "test_analytics_scalars_do_not_hydrate_routes",
        "app.api.v1.contracts.project_market": "test_vehicle_projection_api_enforces_owned_idle_selection",
        "app.bootstrap.build_economy_audit": "test_economy_audit_is_typed_and_reproducible",
        "app.services.analytics.dimension_value": "test_analytics_scalars_do_not_hydrate_routes",
        "app.services.economy_audit.EconomyAuditService.__init__": "test_economy_audit_is_typed_and_reproducible",
        "app.services.economy_audit.EconomyAuditService._rows": "test_economy_audit_is_typed_and_reproducible",
        "app.services.economy_audit.EconomyAuditService.matrix": "test_economy_audit_is_typed_and_reproducible",
        "app.services.economy_audit.audit_vehicle": "test_economy_audit_is_typed_and_reproducible",
        "app.services.economy_audit.summarize_economy": "test_economy_audit_is_typed_and_reproducible",
        "app.services.game.GameService.vehicle_coverage": "test_vehicle_projection_api_enforces_owned_idle_selection",
        "app.services.market_lifecycle.MarketLifecycleService.vehicle_diagnostics": "test_vehicle_projection_api_enforces_owned_idle_selection",
        "app.services.market_preparation.MarketPreparationService._bind_in_transaction": "test_reference_replacement_owns_rollback",
        "app.services.market_preparation.MarketPreparationService._ready_candidates": "test_vehicle_readiness_requires_approach_and_excludes_stale",
        "app.services.market_preparation.MarketPreparationService.demand_state": "test_exhausted_negative_demand_requeues_after_revision",
        "app.services.market_preparation.MarketPreparationService.preparable_candidates": "test_worker_completes_vehicle_gaps_and_exhausts_failed_approaches",
        "app.services.market_preparation.MarketPreparationService.ready_candidates": "test_vehicle_readiness_requires_approach_and_excludes_stale",
        "app.services.market_preparation.MarketPreparationService.ready_context": "test_vehicle_readiness_requires_approach_and_excludes_stale",
        "app.services.preparation_batch.MarketPreparationBatchService.__init__": "test_worker_completes_vehicle_gaps_and_exhausts_failed_approaches",
        "app.services.preparation_batch.MarketPreparationBatchService._ready": "test_worker_completes_vehicle_gaps_and_exhausts_failed_approaches",
        "app.services.preparation_batch.MarketPreparationBatchService.plan": "test_worker_completes_vehicle_gaps_and_exhausts_failed_approaches",
        "app.services.preparation_batch.MarketPreparationBatchService.process": "test_departure_during_preparation_cannot_publish_stale_vehicle_coverage",
        "app.services.preparation_worker.MarketPreparationWorker._iteration": "test_worker_recovers_entire_iteration",
        "app.services.vehicle_coverage.VehicleCoverageService.diagnose": "test_shared_planned_offers_cover_identical_vehicles_once",
        "app.services.vehicle_coverage.VehicleCoverageService.extend": "test_vehicle_coverage_fills_small_vehicle_after_city_is_full",
        "app.services.vehicle_coverage.restrict_candidate": "test_vehicle_coverage_fills_small_vehicle_after_city_is_full",
        "app.services.vehicle_coverage.vehicle_candidates": "test_shared_planned_offers_cover_identical_vehicles_once",
        "app.services.vehicle_coverage.vehicle_offers": "test_vehicle_coverage_fills_small_vehicle_after_city_is_full",
    }
)

FUNCTION_TESTS.update(
    {
        "app.services.market_lifecycle.MarketLifecycleService._vehicle_diagnostics_in_transaction": "test_vehicle_projection_api_enforces_owned_idle_selection",
    }
)

FUNCTION_TESTS["app.services.game.GameService.market_presentation"] = (
    "test_vehicle_projection_api_enforces_owned_idle_selection"
)
FUNCTION_TESTS["app.domain.market_preparation.required_relations"] = (
    "test_approaches_precede_delivery_batches_without_starvation"
)

FUNCTION_TESTS.update(
    {
        "app.repositories.analytics.validate_scalars": "test_analytics_rejects_invalid_sql_scalars",
        "app.repositories.analytics.map_ongoing": "test_analytics_rejects_invalid_sql_scalars",
    }
)


FUNCTION_TESTS.update(
    {
        "app.domain.routing_anchors.distance_m": "test_search_budget_is_transient_and_successful_direct_path_is_certified",
        "app.domain.routing_connections.connection_identity": "test_reverse_requests_cancellation_and_expired_leases",
        "app.domain.routing_connections.connection_leases": "test_reverse_requests_cancellation_and_expired_leases",
        "app.domain.routing_connections.anchor_identity": "test_anchor_fingerprints_survive_sqlite_numeric_normalization",
        "app.services.routing_anchors.RoutingAnchorResolver._locate": "test_candidate_bound_uses_original_location_even_after_address_snap",
        "app.services.routing_connections.RoutingConnectionValidator.validate": "test_connection_deadline_is_transient_for_direct_planning",
        "app.services.routing_connections.RoutingConnectionValidator._search": "test_search_budget_is_transient_and_successful_direct_path_is_certified",
        "app.services.routing_connections.RoutingConnectionValidator._route": "test_no_direction_is_published_without_matching_return_geometry",
        "app.services.routing_connections.RoutingConnectionValidator._anchor": "test_wolfsburg_real_candidates_recover_without_changing_facility",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore.connected": "test_cache_versions_ttls_and_broken_reverse_evidence",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore.publish_connection": "test_connection_publication_rolls_back_both_directions_and_anchors",
    }
)

# Runtime/preparation isolation and historical metadata repair.
FUNCTION_TESTS.update(
    {
        "app.api.v1.dependencies.get_runtime_reader": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.api.v1.dependencies.get_runtime_view": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.api.v1.runtime.get_route_geometry": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.api.v1.runtime.get_runtime": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.api.v1.runtime.parse_route_reference": "test_route_references_reject_malformed_or_unsupported_identifiers",
        "app.api.v1.runtime.project_runtime": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.api.v1.runtime.project_runtime_transport": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.api.v1.runtime.project_traffic_summary": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.api.v1.runtime.route_reference": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.bootstrap.build_runtime_reader": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.bootstrap.build_runtime_view": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.bootstrap.build_transport_repair": "test_repair_rejects_unknown_damage_and_removes_failed_outputs",
        "app.domain.runtime_views.RuntimeTransport.__post_init__": "test_runtime_projection_rejects_corrupt_scalars_without_reading_history",
        "app.launcher.parent_eof": "test_role_selection_parent_eof_and_runtime_cleanup",
        "app.launcher.run_prewarm": "test_prewarm_resources_close_when_worker_start_fails",
        "app.launcher.run_role": "test_role_selection_parent_eof_and_runtime_cleanup",
        "app.launcher.run_runtime": "test_role_selection_parent_eof_and_runtime_cleanup",
        "app.launcher.serve_http": "test_role_selection_parent_eof_and_runtime_cleanup",
        "app.launcher.start_child": "test_child_creation_and_bounded_shutdown",
        "app.launcher.stop_child": "test_child_creation_and_bounded_shutdown",
        "app.launcher.supervise": "test_supervisor_restarts_only_worker_and_closes_children",
        "app.repositories.game_database.SqliteGameDatabase.read_transaction": "test_wal_read_snapshot_rejects_writes_and_resets_after_failure",
        "app.repositories.game_state.SqliteGameUnitOfWork.read_transaction": "test_runtime_never_builds_candidates_and_worker_plans_outside_writer",
        "app.repositories.market_preparation.SqlitePreparationStore.diagnostics": "test_durable_demand_coalesces_and_fences_stale_diagnostics",
        "app.repositories.market_preparation.SqlitePreparationStore.ensure": "test_durable_demand_coalesces_and_fences_stale_diagnostics",
        "app.repositories.market_preparation.SqlitePreparationStore.invalidate": "test_durable_demand_coalesces_and_fences_stale_diagnostics",
        "app.repositories.market_preparation.SqlitePreparationStore.publish_diagnostics": "test_durable_demand_coalesces_and_fences_stale_diagnostics",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore._payload_document": "test_payload_validation_cache_detects_changes_and_worker_fences_failure",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore.holds": "test_payload_validation_cache_detects_changes_and_worker_fences_failure",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore.payload_available": "test_payload_validation_cache_detects_changes_and_worker_fences_failure",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore.read_transaction": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
        "app.repositories.routing_readiness.decode_route_payload": "test_payload_validation_cache_detects_changes_and_worker_fences_failure",
        "app.repositories.runtime_views.SqliteRuntimeReader.__init__": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.repositories.runtime_views.SqliteRuntimeReader.geometry": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.repositories.runtime_views.SqliteRuntimeReader.read": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.repositories.runtime_views.SqliteRuntimeReader.traffic": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.repositories.runtime_views.SqliteRuntimeReader.visible": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.repositories.runtime_views.load_runtime_traffic": "test_runtime_projection_rejects_corrupt_scalars_without_reading_history",
        "app.repositories.runtime_views.load_runtime_transport": "test_runtime_projection_rejects_corrupt_scalars_without_reading_history",
        "app.repositories.runtime_views.validate_runtime_envelope": "test_runtime_projection_rejects_corrupt_scalars_without_reading_history",
        "app.repositories.state_snapshots.dataclass_document": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.repositories.transport_repair.TransportRepairRepository.__init__": "test_repair_rejects_unknown_damage_and_removes_failed_outputs",
        "app.repositories.transport_repair.TransportRepairRepository._apply": "test_repair_rejects_unknown_damage_and_removes_failed_outputs",
        "app.repositories.transport_repair.TransportRepairRepository._compare": "test_repair_reconciliation_and_archive_reject_any_unapproved_change",
        "app.repositories.transport_repair.TransportRepairRepository._inventory": "test_repair_rejects_unknown_damage_and_removes_failed_outputs",
        "app.repositories.transport_repair.TransportRepairRepository._validate": "test_repair_rejects_unknown_damage_and_removes_failed_outputs",
        "app.repositories.transport_repair.TransportRepairRepository._verify_archive": "test_repair_reconciliation_and_archive_reject_any_unapproved_change",
        "app.repositories.transport_repair.TransportRepairRepository.inspect": "test_repair_rejects_unknown_damage_and_removes_failed_outputs",
        "app.repositories.transport_repair.TransportRepairRepository.repair_to": "test_repair_rejects_unknown_damage_and_removes_failed_outputs",
        "app.repositories.transport_repair.repaired_transport": "test_repair_rejects_unknown_damage_and_removes_failed_outputs",
        "app.repositories.transport_repair.table_digest": "test_repair_reconciliation_and_archive_reject_any_unapproved_change",
        "app.services.market_lifecycle.MarketLifecycleService._publication_evidence": "test_publication_revision_change_and_concurrent_arrival_are_fenced",
        "app.services.market_lifecycle.MarketLifecycleService.published": "test_runtime_never_builds_candidates_and_worker_plans_outside_writer",
        "app.services.market_preparation.MarketPreparationService.request": "test_durable_demand_coalesces_and_fences_stale_diagnostics",
        "app.services.preparation_batch.MarketPreparationBatchService._plan_snapshot": "test_worker_completes_vehicle_gaps_and_exhausts_failed_approaches",
        "app.services.preparation_lease.PreparationLease.__init__": "test_worker_lease_excludes_competitors_and_cancels_on_loss",
        "app.services.preparation_lease.PreparationLease._heartbeat": "test_worker_lease_excludes_competitors_and_cancels_on_loss",
        "app.services.preparation_lease.PreparationLease.claim": "test_worker_lease_excludes_competitors_and_cancels_on_loss",
        "app.services.preparation_lease.PreparationLease.close": "test_worker_lease_excludes_competitors_and_cancels_on_loss",
        "app.services.preparation_lease.PreparationLease.owned": "test_worker_lease_excludes_competitors_and_cancels_on_loss",
        "app.services.preparation_lease.PreparationLease.run": "test_worker_lease_excludes_competitors_and_cancels_on_loss",
        "app.services.routing_readiness.RoutingReadinessService._current": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
        "app.services.routing_readiness.RoutingReadinessService.reading": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
        "app.services.runtime_views.RuntimeViewService.read": "test_runtime_reads_exclude_geometry_and_keep_private_energy",
        "app.services.vehicle_coverage.trade_key": "test_shared_planned_offers_cover_identical_vehicles_once",
    }
)

FUNCTION_TESTS["app.launcher.execute_role"] = (
    "test_role_selection_parent_eof_and_runtime_cleanup"
)


FUNCTION_TESTS.update(
    {
        "app.bootstrap.build_market_stock_upgrade": "test_market_upgrade_preserves_source_history_and_only_converts_live_offers",
        "app.domain.market_compatibility.planning_vehicle": "test_demand_models_and_owned_capacity_remain_separate",
        "app.domain.market_stock.PreparedTemplate.__post_init__": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.domain.market_stock.StockPolicy.__post_init__": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.repositories.market_stock.SqliteMarketStockStore.__init__": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.repositories.market_stock.SqliteMarketStockStore.add": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.repositories.market_stock.SqliteMarketStockStore.arrivals": "test_arrival_projection_rejects_inconsistent_locations_and_idle_vehicle",
        "app.repositories.market_stock.SqliteMarketStockStore.bindings": "test_templates_are_shared_but_consumption_is_once_per_account",
        "app.repositories.market_stock.SqliteMarketStockStore.checkpoint": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.repositories.market_stock.SqliteMarketStockStore.consume": "test_templates_are_shared_but_consumption_is_once_per_account",
        "app.repositories.market_stock.SqliteMarketStockStore.cursor": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.repositories.market_stock.SqliteMarketStockStore.initialize": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.repositories.market_stock.SqliteMarketStockStore.issue": "test_templates_are_shared_but_consumption_is_once_per_account",
        "app.repositories.market_stock.SqliteMarketStockStore.pending": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.repositories.market_stock.SqliteMarketStockStore.templates": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.repositories.market_stock.SqliteMarketStockStore.used": "test_templates_are_shared_but_consumption_is_once_per_account",
        "app.repositories.market_stock_upgrade.MarketStockUpgradeRepository.__init__": "test_market_upgrade_preserves_source_history_and_only_converts_live_offers",
        "app.repositories.market_stock_upgrade.MarketStockUpgradeRepository._apply": "test_market_upgrade_preserves_source_history_and_only_converts_live_offers",
        "app.repositories.market_stock_upgrade.MarketStockUpgradeRepository._compare": "test_market_upgrade_reconciliation_detects_unapproved_changes",
        "app.repositories.market_stock_upgrade.MarketStockUpgradeRepository._counts": "test_market_upgrade_preserves_source_history_and_only_converts_live_offers",
        "app.repositories.market_stock_upgrade.MarketStockUpgradeRepository._validate": "test_market_upgrade_rejects_unknown_schema_and_rolls_back_bad_output",
        "app.repositories.market_stock_upgrade.MarketStockUpgradeRepository.inspect": "test_market_upgrade_preserves_source_history_and_only_converts_live_offers",
        "app.repositories.market_stock_upgrade.MarketStockUpgradeRepository.upgrade_to": "test_market_upgrade_preserves_source_history_and_only_converts_live_offers",
        "app.services.market_demand.MarketDemandResolver.resolve": "test_arrival_stock_starts_at_dispatch_without_early_settlement",
        "app.services.market_selection.MarketSelectionService.select": "test_stock_policy_selection_and_corrupt_storage_are_rejected",
        "app.services.market_templates.MarketTemplateService.materialize": "test_templates_are_shared_but_consumption_is_once_per_account",
        "app.services.stock_planning.StockPlanningService.choose": "test_stock_rotation_prioritizes_unserved_vehicles_and_resumes_work",
        "app.services.stock_planning.StockPlanningService.order": "test_stock_rotation_prioritizes_unserved_vehicles_and_resumes_work",
        "app.services.stock_planning.StockPlanningService.targets": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.stock_planning.StockTarget.key": "test_stock_rotation_prioritizes_unserved_vehicles_and_resumes_work",
        "app.services.stock_preparation.StockPreparationBatch._ready": "test_partial_connection_resumes_after_restart_and_never_releases_early",
        "app.services.stock_preparation.StockPreparationBatch._result": "test_stale_evidence_reuses_offers_and_backoff_never_releases_stock",
        "app.services.stock_preparation.StockPreparationBatch._runnable": "test_failed_approaches_and_changed_publication_do_not_create_ready_offers",
        "app.services.stock_preparation.StockPreparationBatch._select": "test_failed_approaches_and_changed_publication_do_not_create_ready_offers",
        "app.services.stock_preparation.StockPreparationBatch._waiting": "test_stale_evidence_reuses_offers_and_backoff_never_releases_stock",
        "app.services.stock_preparation.StockPreparationBatch.process": "test_stock_fences_lease_loss_and_stale_routes_without_partial_issuance",
        "app.services.stock_publication.StockPublicationService.publish": "test_reserve_replacement_and_publication_failure_keep_atomic_state",
        "app.services.stock_publication.StockPublicationService.read": "test_catalogue_changes_block_old_supply_without_deleting_terms",
        "app.services.stock_publication.StockPublicationService.unchanged": "test_stock_fences_lease_loss_and_stale_routes_without_partial_issuance",
        "app.bootstrap.build_game_database": "test_postgres_backend_selection",
        "app.repositories.game_database.SqliteGameDatabase.close": "test_sqlite_close_is_noop",
        "app.repositories.postgres_database.require_schema_name": "test_postgres_sql_translation_contract",
        "app.repositories.postgres_database._json_path": "test_postgres_sql_translation_contract",
        "app.repositories.postgres_database._json_extract_sql": "test_postgres_sql_translation_contract",
        "app.repositories.postgres_database._json_type_sql": "test_postgres_sql_translation_contract",
        "app.repositories.postgres_database.translate_sql": "test_postgres_sql_translation_contract",
        "app.repositories.postgres_database.HybridRow.__init__": "test_postgres_row_contract",
        "app.repositories.postgres_database.HybridRow.keys": "test_postgres_row_contract",
        "app.repositories.postgres_database.HybridRow.__getitem__": "test_postgres_row_contract",
        "app.repositories.postgres_database.HybridRow.__iter__": "test_postgres_row_contract",
        "app.repositories.postgres_database.HybridRow.__len__": "test_postgres_row_contract",
        "app.repositories.postgres_database.PostgresCursorAdapter.__init__": "test_postgres_cursor_contract",
        "app.repositories.postgres_database.PostgresCursorAdapter.rowcount": "test_postgres_cursor_contract",
        "app.repositories.postgres_database.PostgresCursorAdapter._names": "test_postgres_cursor_contract",
        "app.repositories.postgres_database.PostgresCursorAdapter._row": "test_postgres_cursor_contract",
        "app.repositories.postgres_database.PostgresCursorAdapter.fetchone": "test_postgres_cursor_contract",
        "app.repositories.postgres_database.PostgresCursorAdapter.fetchall": "test_postgres_cursor_contract",
        "app.repositories.postgres_database.PostgresCursorAdapter.__iter__": "test_postgres_cursor_contract",
        "app.repositories.postgres_database.PostgresConnectionAdapter.__init__": "test_postgres_connection_adapter_contract",
        "app.repositories.postgres_database.PostgresConnectionAdapter.execute": "test_postgres_connection_adapter_contract",
        "app.repositories.postgres_database.PostgresConnectionAdapter.executemany": "test_postgres_connection_adapter_contract",
        "app.repositories.postgres_database.PostgresConnectionAdapter.executescript": "test_postgres_connection_adapter_contract",
        "app.repositories.postgres_database.PostgresConnectionAdapter.commit": "test_postgres_connection_adapter_contract",
        "app.repositories.postgres_database.PostgresConnectionAdapter.rollback": "test_postgres_connection_adapter_contract",
        "app.repositories.postgres_database.PostgresGameDatabase.__init__": "test_postgres_database_lifecycle",
        "app.repositories.postgres_database.PostgresGameDatabase.connect": "test_postgres_database_lifecycle",
        "app.repositories.postgres_database.PostgresGameDatabase.read_transaction": "test_postgres_database_lifecycle",
        "app.repositories.postgres_database.PostgresGameDatabase.transaction": "test_postgres_database_lifecycle",
        "app.repositories.postgres_database.PostgresGameDatabase.initialize": "test_postgres_schema_validation_failures",
        "app.repositories.postgres_database.PostgresGameDatabase.close": "test_postgres_database_lifecycle",
        "app.repositories.postgres_catalogues._catalogue_conninfo": "test_postgres_catalogue_connection_contract",
        "app.repositories.postgres_catalogues.PostgresWorldCatalogue.__init__": "test_postgres_catalogue_connection_contract",
        "app.repositories.postgres_catalogues.PostgresWorldCatalogue.read": "test_postgres_catalogue_connection_contract",
        "app.repositories.postgres_catalogues.PostgresVehicleCatalogue.__init__": "test_postgres_catalogue_connection_contract",
        "app.repositories.postgres_catalogues.PostgresVehicleCatalogue.list_models": "test_postgres_catalogue_connection_contract",
        "app.api.v1.auth.auth_config": "test_auth_config_exposes_only_browser_safe_values",
        "app.providers.supabase_auth.TracingJwkClient.fetch_data": "test_supabase_jwks_client_is_cached_and_refreshes_through_pyjwt",
        "app.providers.supabase_auth.SupabaseJwtVerifier.__init__": "test_supabase_jwks_client_is_cached_and_refreshes_through_pyjwt",
        "app.providers.supabase_auth.SupabaseJwtVerifier.verify": "test_supabase_jwt_verification_accepts_only_stable_valid_identity",
        "app.repositories.accounts.AccountRepository.ensure_external_user": "test_migrated_email_uses_existing_password_and_compact_player_id",
    }
)


FUNCTION_TESTS.update(
    {
        "app.domain.market_preparation.delivery_relations": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.repositories.market_preparation.SqlitePreparationStore.has_incomplete": "test_preparation_generation_and_reference_rollback",
        "app.repositories.market_stock.SqliteMarketStockStore.levels": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.repositories.market_stock.SqliteMarketTemplateStore.__init__": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.repositories.market_stock.SqliteMarketTemplateStore.add": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.repositories.market_stock.SqliteMarketTemplateStore.levels": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.repositories.market_stock.SqliteMarketTemplateStore.templates": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.repositories.market_stock._load_template": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.repositories.routing_anchors.SqliteRoutingAnchorRepository._decode": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
        "app.repositories.routing_anchors.SqliteRoutingAnchorRepository.get_many": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore._valid_payload": "test_payload_validation_cache_detects_changes_and_worker_fences_failure",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore.available_payloads": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore.connected_references": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
        "app.repositories.routing_readiness.SqliteRoutingReadinessStore.get_many": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
        "app.repositories.routing_readiness._load_relation": "test_global_lease_fences_expired_and_competing_writers",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._filled": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._choose": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._log": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._next_context": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._plan": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._prepare": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._publish": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._result": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch._runnable": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.global_stock_preparation.GlobalStockPreparationBatch.process": "test_all_catalogue_models_get_reserves_without_overloading_small_truck",
        "app.services.market_demand.MarketDemandResolver.catalogue": "test_demand_models_and_owned_capacity_remain_separate",
        "app.services.market_preparation.MarketPreparationService._prepare_relations": "test_preparation_failures_backoff_fencing_and_worker_cleanup",
        "app.services.preparation_worker.MarketPreparationWorker._process_background": "test_worker_pauses_global_stock_for_every_incomplete_player",
        "app.services.routing_readiness.RoutingReadinessService._preload": "test_readiness_read_view_reuses_facts_but_never_crosses_publication",
    }
)
