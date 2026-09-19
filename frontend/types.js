/** Public browser-side projections of API v1. The server owns validation.
 * @typedef {{url: string, source_url: string, author: string, license_name: string, license_url: string, attribution: string, scope: string}} VehicleImage
 * @typedef {string | number | boolean | Node | null | undefined | DomValue[]} DomValue
 * @typedef {{url: string, role: string, verified_at: string | null, precision?: string | null, provider?: string | null}} SourceReference
 * @typedef {{facilities: Hub[], catalogue_version: string, unavailable_count: number}} FacilityResponse
 * @typedef {{facility_uid?: string, company_uid?: string | null, aliases?: string[], catalogue_version?: string, coordinate_evidence?: SourceReference[], id: string, city: string, label: string, address: string, lat?: number, lon?: number, resolution_status?: string}} Hub
 * @typedef {{facility_uid?: string, location_snapshot?: Hub, id: string, name: string, hub_id: string, capacity_tons: number, mode: string, status: string, hub: Hub, model_id?: string, image?: VehicleImage | null, operating_cost_eur_per_km?: number}} Vehicle
 * @typedef {{payload_band?: "light" | "medium" | "heavy", cargo_basis?: "documented" | "simulated", origin_facility_uid?: string, destination_facility_uid?: string, id: string, cargo: string, tons: number, mode: string, origin_hub_id: string, origin: Hub, destination: Hub, shipper_name: string, consignee_name: string}} Contract
 * @typedef {import('geojson').LineString | import('geojson').Feature<import('geojson').LineString>} RouteGeometry
 * @typedef {{distance_km: number, duration_seconds: number, payout_eur: number, operating_cost_eur: number, profit_eur: number, route_geojson: RouteGeometry, vehicle_id: string | null, operating_cost_eur_per_km: number}} Quote
 * @typedef {Omit<Quote, "operating_cost_eur_per_km"> & {origin_snapshot?: Hub, destination_snapshot?: Hub, id: string, vehicle_id: string, departed_at: number, arrives_at: number, origin: Hub, destination: Hub, contract: Contract}} Transport
 * @typedef {{id: string, vehicle_id: string, model_id: string, username: string, player_color: string, is_own: boolean, departed_at: number, arrives_at: number, route_geojson: RouteGeometry}} PublicTransport
 * @typedef {{cash: number, completed: number, reputation: number}} Player
 * @typedef {{username: string, completed: number}} RankedPlayer
 * @typedef {{id: string, name: string, capacity_tons: number, price_eur: number, manufacturer: string, powertrain: string, operating_cost_eur_per_km: number, unlock_reputation: number, image?: VehicleImage | null}} VehicleModel
 * @typedef {{models: VehicleModel[], delivery_hub: string}} Catalogue
 * @typedef {{vehicles: Vehicle[], contracts: Contract[], transports: Transport[], traffic?: PublicTransport[]}} MapState
 * @typedef {MapState & {player: Player, server_time: number, time_scale: number, idle_vehicles: number, active_transports: number}} GameSnapshot
 * @typedef {{url: URL, state: GameSnapshot | null, user: {username: string}, quote: Quote | null, selectedVehicle: string, mutating: boolean, quoting: boolean, readonly busy: boolean, rankings: RankedPlayer[] | null, catalogue: Catalogue | null, panelError: boolean, now?: number}} PanelView
 * @typedef {(path: string, options?: RequestInit) => Promise<any>} RequestJson
 * @typedef {(message: string, kind?: string) => void} Notify
 * @typedef {(path: string) => void} Navigate
 * @typedef {() => number} Clock
 * @typedef {{points: number[][], distances: number[], total: number}} PreparedRoute
 */
export {};
