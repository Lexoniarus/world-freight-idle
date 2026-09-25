/** Public browser-side projections of API v1. The server owns validation.
 * @typedef {{url: string, source_url: string, author: string, license_name: string, license_url: string, attribution: string, scope: string}} VehicleImage
 * @typedef {string | number | boolean | Node | null | undefined | DomValue[]} DomValue
 * @typedef {{kind: "diesel" | "gas" | "electric", unit: "l" | "kg" | "kWh", capacity: number, consumption_per_100km: number, stop_minutes: number, reserve_fraction: number}} EnergyProfile
 * @typedef {{phase: "driving" | "refuelling" | "charging", starts_at: number, ends_at: number, start_km: number, end_km: number, start_energy?: number | null, end_energy?: number | null}} JourneySegment
 * @typedef {{distance_km: number, energy?: EnergyProfile | null, segments: JourneySegment[]}} JourneyPlan
 * @typedef {{url: string, role: string, verified_at: string | null, precision?: string | null, provider?: string | null}} SourceReference
 * @typedef {{facilities: Hub[], catalogue_version: string, unavailable_count: number}} FacilityResponse
 * @typedef {{company_uid: string, legal_name: string, display_name: string, country: string}} CompanyIdentity
 * @typedef {{city_uid?: string, country?: string, facility_uid?: string, company_uid?: string | null, company?: CompanyIdentity | null, aliases?: string[], catalogue_version?: string, coordinate_evidence?: SourceReference[], id: string, city: string, label: string, address: string, lat?: number, lon?: number, resolution_status?: string}} Hub
 * @typedef {{energy: EnergyProfile, energy_level: number, top_speed_kmh: number, facility_uid?: string, location_snapshot?: Hub, id: string, name: string, hub_id: string, capacity_tons: number, mode: string, status: string, hub: Hub, model_id?: string, image?: VehicleImage | null, operating_cost_eur_per_km?: number}} Vehicle
 * @typedef {{cargo_basis?: "documented" | "derived", cargo_code?: string, cargo_system?: "NHM2026", market_model?: "nhm_v1" | "nhm_v2", eligible_vehicle_ids?: string[], distance_band?: "short" | "medium" | "long", estimated_distance_km?: number, transport_class?: string, generated_for_vehicle_scale?: string, generated_capacity_tons?: number, cargo_value_eur_per_t?: number, cargo_value_eur?: number, rate_eur_per_km_ton?: number, trade_match_type?: "exact" | "ancestor", origin_facility_uid?: string, destination_facility_uid?: string, id: string, cargo: string, tons: number, mode: string, origin_hub_id: string, origin: Hub, destination: Hub, shipper_name: string, consignee_name: string}} Contract
 * @typedef {import('geojson').LineString | import('geojson').Feature<import('geojson').LineString>} RouteGeometry
 * @typedef {{purpose: "approach" | "delivery", start_km: number, end_km: number, routing_duration_seconds: number, coordinates: number[][]}} RouteLeg
 * @typedef {{start?: Hub, approach_distance_km?: number, delivery_distance_km?: number, route_legs?: RouteLeg[], journey: JourneyPlan | null, total_duration_seconds: number | null, driving_seconds: number | null, pause_seconds: number | null, energy_stop_count: number | null, energy_consumption: number | null, distance_km: number, duration_seconds: number, payout_eur: number, operating_cost_eur: number, profit_eur: number, route_geojson: RouteGeometry, vehicle_id: string | null, operating_cost_eur_per_km: number}} Quote
 * @typedef {{phase: "driving" | "refuelling" | "charging" | "arrived", distance_km: number, fraction: number, energy_level: number | null, phase_remaining_seconds: number}} JourneyProgress
 * @typedef {{start?: Hub, approach_distance_km?: number, delivery_distance_km?: number, route_legs?: RouteLeg[], journey: JourneyPlan, progress: JourneyProgress | null, distance_km: number, routing_duration_seconds: number, provider: string, payout_eur: number, operating_cost_eur: number, profit_eur: number, route_geojson: RouteGeometry, origin_snapshot?: Hub, destination_snapshot?: Hub, id: string, vehicle_id: string, departed_at: number, arrives_at: number, origin: Hub, destination: Hub, contract: Contract}} Transport
 * @typedef {{route_legs?: RouteLeg[], journey: JourneyPlan, id: string, vehicle_id: string, model_id: string, model_name: string, username: string, player_color: string, is_own: boolean, departed_at: number, arrives_at: number, route_geojson: RouteGeometry}} PublicTransport
 * @typedef {{cash: number, completed: number, reputation: number}} Player
 * @typedef {{username: string, completed: number}} RankedPlayer
 * @typedef {{energy: EnergyProfile, top_speed_kmh: number, id: string, name: string, capacity_tons: number, price_eur: number, manufacturer: string, powertrain: string, operating_cost_eur_per_km: number, unlock_reputation: number, image?: VehicleImage | null}} VehicleModel
 * @typedef {{models: VehicleModel[], delivery_hub: string}} Catalogue
 * @typedef {{vehicles: Vehicle[], contracts: Contract[], transports: Transport[], traffic?: PublicTransport[], trafficAvailable?: boolean}} MapState
 * @typedef {MapState & {player: Player, server_time: number, time_scale: number, idle_vehicles: number, active_transports: number, available_contracts?: number, featured_contracts?: Contract[]}} GameSnapshot
 * @typedef {{cityUid?: string, cities?: any[], activeCities?: string[], analytics?: any, analyticsChoices?: any, analyticsLoading?: boolean, analyticsError?: boolean, detailId?: string, marketStale?: boolean, marketLoaded?: boolean, detailContract?: any, url: URL, state: GameSnapshot | null, user: {id?: string, username: string}, quote: Quote | null, selectedVehicle: string, mutating: boolean, quoting: boolean, readonly busy: boolean, rankings: RankedPlayer[] | null, catalogue: Catalogue | null, panelError: boolean, now?: number}} PanelView
 * @typedef {(path: string, options?: RequestInit) => Promise<any>} RequestJson
 * @typedef {(message: string, kind?: string) => void} Notify
 * @typedef {(path: string) => void} Navigate
 * @typedef {() => number} Clock
 * @typedef {{points: number[][], distances: number[], total: number}} PreparedRoute
 */
export {};
