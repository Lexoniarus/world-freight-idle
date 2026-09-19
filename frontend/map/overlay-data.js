import { collection, pointFeature, prepareRoute, routePose, unwrapRoute } from "../geometry.js";
import { routeProgress } from "../time.js";
import { vehicleIconId } from "./vehicle-assets.js";

/** Normalize the two supported server route envelopes.
 * @param {import('../types.js').RouteGeometry} route
 * @returns {import("geojson").LineString}
 */
export const routeGeometry = (route) => (route.type === "Feature" ? route.geometry : route);

/** Cache immutable routes and project server state into map-independent GeoJSON. */
export class OverlayData {
  constructor() {
    this.hubs = [];
    this.catalogueHubs = [];
    this.routes = new Map();
    this.trafficRoutes = new Map();
    this.availableVehicleIcons = new Set();
    this.state = { vehicles: [], contracts: [], transports: [], traffic: [] };
  }
  /** Retain only real resolved coordinates.
   * @param {import('../types.js').Hub[]} hubs
   */
  setHubs(hubs) {
    this.catalogueHubs = hubs.filter(
      (hub) =>
        hub.resolution_status === "resolved" &&
        Number.isFinite(hub.lon) &&
        Number.isFinite(hub.lat),
    );
    this.hubs = this.catalogueHubs;
  }
  /** Publish MapLibre image IDs that loaded successfully.
   * @param {Set<string>} imageIds
   */
  setVehicleIcons(imageIds) {
    this.availableVehicleIcons = new Set(imageIds);
  }
  /** Refresh route caches for private routes and shared live traffic.
   * @param {import('../types.js').MapState} state
   */
  update(state) {
    this.state = { ...state, traffic: state.traffic ?? [] };
    const snapshots = [
      ...state.transports.flatMap((trip) => [
        trip.origin_snapshot ?? trip.origin,
        trip.destination_snapshot ?? trip.destination,
      ]),
      ...state.vehicles.map((vehicle) => vehicle.location_snapshot ?? vehicle.hub),
      ...state.contracts.flatMap((contract) => [contract.origin, contract.destination]),
    ].filter(
      (facility) =>
        facility?.resolution_status === "resolved" &&
        Number.isFinite(facility.lat) &&
        Number.isFinite(facility.lon),
    );
    this.hubs = [
      ...new Map(
        [...this.catalogueHubs, ...snapshots].map((facility) => [
          facility.facility_uid ?? facility.id,
          facility,
        ]),
      ).values(),
    ];
    const active = new Set(state.transports.map((trip) => trip.id));
    for (const id of this.routes.keys()) if (!active.has(id)) this.routes.delete(id);
    for (const trip of state.transports)
      if (!this.routes.has(trip.id))
        this.routes.set(trip.id, prepareRoute(routeGeometry(trip.route_geojson).coordinates));

    const activeTraffic = new Set(this.state.traffic.map((trip) => trip.id));
    for (const id of this.trafficRoutes.keys())
      if (!activeTraffic.has(id)) this.trafficRoutes.delete(id);
    for (const trip of this.state.traffic)
      if (!this.trafficRoutes.has(trip.id))
        this.trafficRoutes.set(
          trip.id,
          prepareRoute(routeGeometry(trip.route_geojson).coordinates),
        );
  }
  /** Project public-hub markers with locally rendered label references. */
  hubFeatures() {
    return collection(
      this.hubs.map((hub) =>
        pointFeature([hub.lon, hub.lat], { id: hub.id, labelImage: "label-" + hub.id }),
      ),
    );
  }
  /** Aggregate co-located orders or parked vehicles by hub.
   * @param {(import("../types.js").Vehicle | import("../types.js").Contract)[]} items
   * @param {"hub_id" | "origin_hub_id"} key
   */
  locationFeatures(items, key) {
    return collection(
      this.hubs
        .filter((hub) => items.some((item) => item[key] === hub.id))
        .map((hub) => pointFeature([hub.lon, hub.lat], { id: hub.id })),
    );
  }
  /** Project only the authenticated player's route lines. */
  routeFeatures() {
    return collection(
      this.state.transports.flatMap((trip) => {
        const route = this.routes.get(trip.id);
        return route
          ? [
              {
                type: "Feature",
                properties: { id: trip.id },
                geometry: { type: "LineString", coordinates: route.points },
              },
            ]
          : [];
      }),
    );
  }
  /** Project the authenticated player's moving vehicle positions.
   * @param {number} now
   * @returns {import("geojson").FeatureCollection<import("geojson").Point>}
   */
  vehicleFeatures(now) {
    return this.trafficFeatures(now, true);
  }

  /** Project moving vehicles owned by other players.
   * @param {number} now
   * @returns {import("geojson").FeatureCollection<import("geojson").Point>}
   */
  multiplayerVehicleFeatures(now) {
    return this.trafficFeatures(now, false);
  }

  /** Project one ownership slice of shared traffic.
   * @param {number} now
   * @param {boolean} isOwn
   * @returns {import("geojson").FeatureCollection<import("geojson").Point>}
   */
  trafficFeatures(now, isOwn) {
    return collection(
      this.state.traffic.flatMap((trip) => {
        if (trip.is_own !== isOwn) return [];
        const route = this.trafficRoutes.get(trip.id);
        const pose =
          route && routePose(route, routeProgress(now, trip.departed_at, trip.arrives_at));
        if (!pose) return [];
        const iconImage = vehicleIconId(trip.model_id, trip.player_color);
        const hasIcon = Boolean(iconImage && this.availableVehicleIcons.has(iconImage));
        return [
          pointFeature(pose.coordinate, {
            id: trip.id,
            vehicleId: trip.vehicle_id,
            modelId: trip.model_id,
            modelName: trip.model_name,
            iconImage: hasIcon ? iconImage : "",
            hasIcon,
            bearing: pose.bearing,
            playerColor: trip.player_color,
            username: trip.username,
            isOwn: trip.is_own,
          }),
        ];
      }),
    );
  }
  /** Return only the authenticated player's fleet coordinates for framing.
   * @param {number} now
   * @returns {number[][]}
   */
  fleetCoordinates(now) {
    return [
      ...this.hubs
        .filter((hub) =>
          this.state.vehicles.some(
            (vehicle) => vehicle.status === "idle" && vehicle.hub_id === hub.id,
          ),
        )
        .map((hub) => [hub.lon, hub.lat]),
      ...this.vehicleFeatures(now).features.map((feature) => feature.geometry.coordinates),
    ];
  }
}

/** Convert a selected quote into a route preview without changing game state.
 * @param {import('../types.js').Quote | null} quote
 */
export function previewFeatures(quote) {
  return collection(
    quote
      ? [
          {
            type: "Feature",
            properties: {},
            geometry: {
              type: "LineString",
              coordinates: unwrapRoute(routeGeometry(quote.route_geojson).coordinates),
            },
          },
        ]
      : [],
  );
}
