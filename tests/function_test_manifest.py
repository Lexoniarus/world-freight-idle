FUNCTION_TESTS = {
    "app.domain.transports.RouteSnapshot.__post_init__": "test_route_snapshot_rejects_invalid_measurements_and_geometry",
    "app.domain.transports.ActiveTransport.__post_init__": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
    "app.domain.transports.ActiveTransport.is_due": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
    "app.domain.transports.ActiveTransport.settle": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
    "app.repositories.transport_mapping.load_transport": "test_transport_lifecycle_rejects_invalid_and_duplicate_settlement",
    "app.services.game.GameService._get_player": "test_relational_game_use_cases_preserve_atomic_settlement",
    "app.services.game.GameService._active_transports": "test_relational_game_use_cases_preserve_atomic_settlement",
    "app.domain.contracts.ContractOffer.__post_init__": "test_contract_offer_domain_rules",
    "app.domain.validation.require_finite": "test_domain_value_validators_reject_invalid_values",
    "app.domain.validation.require_integer": "test_domain_value_validators_reject_invalid_values",
    "app.domain.validation.require_identity": "test_domain_value_validators_reject_invalid_values",
    "app.simulation.build_payload_bands": "test_payload_bands_cover_catalogue_and_reject_invalid_capacities",
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
    "app.repositories.sqlite_store.SqliteStore.connect": "test_store_connect_and_initialize",
    "app.repositories.sqlite_store.SqliteStore.delete_state_keys": "test_store_json_roundtrip_and_delete",
    "app.repositories.sqlite_store.SqliteStore.get_geocode": "test_store_geocode_cache_roundtrip",
    "app.repositories.sqlite_store.SqliteStore.get_json": "test_store_json_roundtrip_and_delete",
    "app.repositories.sqlite_store.SqliteStore.has_json": "test_store_json_roundtrip_and_delete",
    "app.repositories.sqlite_store.SqliteStore.get_route": "test_store_route_cache_roundtrip",
    "app.repositories.sqlite_store.SqliteStore.initialize": "test_store_connect_and_initialize",
    "app.repositories.sqlite_store.SqliteStore.put_geocode": "test_store_geocode_cache_roundtrip",
    "app.repositories.sqlite_store.SqliteStore.put_route": "test_store_route_cache_roundtrip",
    "app.repositories.sqlite_store.SqliteStore.set_json": "test_store_json_roundtrip_and_delete",
    "app.services.game.GameService._build_trip": "test_build_trip_contains_tracking_timestamps",
    "app.services.game.GameService._current_market_for_scope": "test_list_and_get_contracts_return_real_addresses",
    "app.services.game.GameService._generate_scoped_market": "test_list_and_get_contracts_return_real_addresses",
    "app.services.game.GameService._store_market": "test_vehicle_catalogue_outage_preserves_only_current_market",
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
    "app.services.game.GameService.now": "test_now_returns_wall_clock",
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
    "app.services.contract_factory.ContractFactory.build": "test_build_contract_has_expiry_and_valid_nhm_cargo",
    "app.services.market.MarketGenerator._select_trade_option": "test_build_contract_has_expiry_and_valid_nhm_cargo",
    "app.services.trade_network.TradeNetwork.__init__": "test_build_contract_has_expiry_and_valid_nhm_cargo",
    "app.services.trade_network.TradeNetwork._build_trade_options": "test_build_contract_has_expiry_and_valid_nhm_cargo",
    "app.services.trade_network.TradeNetwork._index_inbound_profiles": "test_build_contract_has_expiry_and_valid_nhm_cargo",
    "app.services.trade_network.TradeNetwork.options_for": "test_build_contract_has_expiry_and_valid_nhm_cargo",
    "app.services.market.MarketGenerator.generate": "test_every_routable_facility_has_nhm_work_without_generic_freight",
    "app.services.market_scope.MarketScopeResolver.resolve": "test_market_scope_combines_idle_trucks_and_zoomed_viewport",
    "app.services.pricing.PricingService.quote": "test_pricing_quote_uses_distance_and_cargo_rate",
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
        "app.repositories.accounts.AccountRepository.find_user": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.accounts.AccountRepository.revoke_session": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.accounts.AccountRepository.save_session": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.accounts.AccountRepository.session_user": "test_auth_sessions_expire_revoke_and_throttle",
        "app.repositories.sqlite_store.SqliteStore.transaction": "test_transaction_rolls_back_and_namespaces_isolate",
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
        "app.repositories.sqlite_store.SqliteStore.__init__": "test_transaction_rolls_back_and_namespaces_isolate",
        "app.repositories.vehicle_catalogue.SqliteVehicleCatalogue.__init__": "test_catalogue_projects_all_offers_without_writing",
        "app.repositories.vehicle_catalogue.SqliteVehicleCatalogue._read_model": "test_catalogue_failures_are_explicit",
        "app.repositories.vehicle_catalogue.SqliteVehicleCatalogue.list_models": "test_catalogue_projects_all_offers_without_writing",
        "app.services.auth.AuthService.__init__": "test_auth_sessions_expire_revoke_and_throttle",
        "app.services.fleet.FleetService.__init__": "test_purchase_reputation_snapshots_and_rollback",
        "app.services.fleet.FleetService.list_catalogue": "test_catalogue_api_errors_and_vehicle_quote_validation",
        "app.services.game.GameService.__init__": "test_player_service_isolation_and_atomic_purchases",
        "app.services.map_locations.MapLocationService.__init__": "test_map_hubs_resolve_and_preserve_partial_failures",
        "app.services.pricing.PricingService.__init__": "test_pricing_quote_uses_distance_and_cargo_rate",
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
        "app.services.profile_maintenance.validate_active_load": "test_profile_update_preserves_other_players_and_trip_snapshots",
        "app.services.game.GameService.ensure_initial_state": "test_initialization_direct_failure_is_atomic",
        "app.main.lifespan": "test_lifespan_cleans_up_partial_start_and_shutdown",
    }
)

FUNCTION_TESTS["app.services.game.GameService._commit_dispatch"] = (
    "test_dispatch_reprices_after_concurrent_profile_maintenance"
)

FUNCTION_TESTS.update(
    {
        "app.api.v1.map.list_map_facilities": "test_map_endpoint_requires_session_and_uses_game_provider",
        "app.bootstrap.build_world_catalogue": "test_world_migration_repository_rolls_back_and_cli_requires_backup",
        "app.bootstrap.build_world_maintenance_service": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.bootstrap.build_world_state_migration_service": "test_world_migration_repository_rolls_back_and_cli_requires_backup",
        "app.domain.cargo.NhmProduct.is_compatible_with": "test_nhm_cargo_profiles_follow_parent_hierarchy",
        "app.domain.world.Facility.has_verified_location": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.Facility.location_snapshot": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.Facility.inbound_profiles": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.Facility.is_routable": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.Facility.outbound_profiles": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.FacilityQuery.includes": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.FacilityQuery.parse": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.WorldSnapshot.get_company": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.WorldSnapshot.get_facility": "test_world_snapshot_identity_provenance_and_query",
        "app.domain.world.WorldSnapshot.query": "test_world_snapshot_identity_provenance_and_query",
        "app.main.world_catalogue_error": "test_map_endpoint_requires_session_and_uses_game_provider",
        "app.repositories.cached_world_catalogue.CachedWorldCatalogue.__init__": "test_cached_world_catalogue_reads_source_once",
        "app.repositories.cached_world_catalogue.CachedWorldCatalogue.read": "test_cached_world_catalogue_reads_source_once",
        "app.repositories.world_catalogue.SqliteWorldCatalogue.__init__": "test_world_repository_readonly_and_cleanup",
        "app.repositories.world_catalogue.SqliteWorldCatalogue.read": "test_world_repository_readonly_and_cleanup",
        "app.repositories.world_catalogue.read_cargo": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.read_nhm_ancestors": "test_world_snapshot_identity_provenance_and_query",
        "app.repositories.world_catalogue.read_companies": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.read_facility": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.read_handled_goods": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.read_world_snapshot": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.source_reference": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.validate_uid": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_catalogue.validate_world_schema": "test_world_repository_rejects_incompatible_data",
        "app.repositories.world_maintenance.WorldMaintenanceRepository.__init__": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.WorldMaintenanceRepository.upgrade": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.add_world_identities": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.insert_documented_goods": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.insert_terminal_nhm_profiles": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.insert_facility_evidence": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.insert_legacy_facility": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.insert_reference_company": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.insert_reference_facility": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_maintenance.insert_world_source": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.repositories.world_state_migration.WorldStateMigrationRepository.__init__": "test_world_migration_repository_rolls_back_and_cli_requires_backup",
        "app.repositories.world_state_migration.WorldStateMigrationRepository.transform": "test_world_migration_repository_rolls_back_and_cli_requires_backup",
        "app.services.fleet.resolve_delivery_facility": "test_delivery_requires_verified_catalogue_endpoint",
        "app.services.map_locations.MapLocationService.list_facilities": "test_map_hubs_resolve_and_preserve_partial_failures",
        "app.services.world_maintenance.WorldMaintenanceService.__init__": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.services.world_maintenance.WorldMaintenanceService.prepare": "test_world_preparation_is_atomic_idempotent_and_enforces_identity",
        "app.services.world_maintenance.validate_legacy_evidence": "test_world_evidence_rejects_unverified_candidates",
        "app.services.world_state_migration.WorldStateMigrationService.__init__": "test_world_migration_repository_rolls_back_and_cli_requires_backup",
        "app.services.world_state_migration.WorldStateMigrationService.migrate": "test_world_migration_repository_rolls_back_and_cli_requires_backup",
        "app.services.world_state_migration.WorldStateMigrationService.migrate.convert": "test_world_migration_repository_rolls_back_and_cli_requires_backup",
        "app.services.world_state_migration.endpoint_snapshot": "test_world_migration_preserves_snapshots_and_rejects_unknown_endpoints",
        "app.services.world_state_migration.migrate_contract": "test_world_migration_preserves_snapshots_and_rejects_unknown_endpoints",
        "app.services.world_state_migration.migrate_world_records": "test_world_migration_preserves_snapshots_and_rejects_unknown_endpoints",
        "app.services.world_state_migration.preserve_routing_endpoint": "test_world_migration_preserves_snapshots_and_rejects_unknown_endpoints",
    }
)

FUNCTION_TESTS.update(
    {
        "app.api.v1.dependencies.get_multiplayer_map_service": "test_multiplayer_map_endpoint_requires_login_and_shares_other_players",
        "app.api.v1.map.list_map_traffic": "test_multiplayer_map_endpoint_requires_login_and_shares_other_players",
        "app.bootstrap.build_multiplayer_map_service": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.services.multiplayer_map.MultiplayerMapService.__init__": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.services.multiplayer_map.MultiplayerMapService.list_traffic": "test_multiplayer_map_projects_shared_active_traffic_without_private_economy",
        "app.services.multiplayer_map.player_color": "test_player_color_is_stable_and_changes_between_users",
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
        "app.domain.game.OwnedVehicle.hub_id": "test_entity_construction_and_mutation_are_guarded",
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
