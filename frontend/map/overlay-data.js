import { collection, pointFeature, prepareRoute, routePosition, unwrapRoute } from "../geometry.js";
import { routeProgress } from "../time.js";

/** Normalize the two supported server route envelopes.
 * @param {import('../types.js').RouteGeometry} route
 * @returns {import("geojson").LineString}
 */
export const routeGeometry = (route) => (route.type === "Feature" ? route.geometry : route);

/** Cache immutable routes and project server state into map-independent GeoJSON. */
export class OverlayData {
  constructor() {
    this.hubs = [];
    this.routes = new Map();
    this.state = { vehicles: [], contracts: [], transports: [] };
  }
  /** Retain only real resolved coordinates.
   * @param {import('../types.js').Hub[]} hubs
   */
  setHubs(hubs) {
    this.hubs = hubs.filter(
      (hub) =>
        hub.resolution_status === "resolved" &&
        Number.isFinite(hub.lon) &&
        Number.isFinite(hub.lat),
    );
  }
  /** Refresh the route cache for the authoritative active transport set.
   * @param {import('../types.js').MapState} state
   */
  update(state) {
    this.state = state;
    const active = new Set(state.transports.map((trip) => trip.id));
    for (const id of this.routes.keys()) if (!active.has(id)) this.routes.delete(id);
    for (const trip of state.transports)
      if (!this.routes.has(trip.id))
        this.routes.set(trip.id, prepareRoute(routeGeometry(trip.route_geojson).coordinates));
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
  /** Project the prepared, continuous route for each active transport. */
  routeFeatures() {
    return collection(
      this.state.transports.map((trip) => ({
        type: "Feature",
        properties: { id: trip.id },
        geometry: { type: "LineString", coordinates: this.routes.get(trip.id).points },
      })),
    );
  }
  /** Project moving vehicle positions using server-adjusted time.
   * @param {number} now
   * @returns {import("geojson").FeatureCollection<import("geojson").Point>}
   */
  vehicleFeatures(now) {
    return collection(
      this.state.transports.flatMap((trip) => {
        const route = this.routes.get(trip.id);
        const coordinate =
          route && routePosition(route, routeProgress(now, trip.departed_at, trip.arrives_at));
        return coordinate ? [pointFeature(coordinate, { id: trip.id })] : [];
      }),
    );
  }
  /** Return parked and moving vehicle coordinates for camera framing.
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
