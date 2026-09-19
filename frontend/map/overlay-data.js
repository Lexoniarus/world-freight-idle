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
    this.availableVehicleModels = new Set();
    this.state = { vehicles: [], contracts: [], transports: [] };
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
  /** Publish only vehicle models whose map sprite loaded successfully.
   * @param {Set<string>} modelIds */
  setVehicleModels(modelIds) {
    this.availableVehicleModels = new Set(modelIds);
  }
  /** Refresh the route cache for the authoritative active transport set.
   * @param {import('../types.js').MapState} state
   */
  update(state) {
    this.state = state;
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
  /** Project moving vehicle positions and headings using server-adjusted time.
   * @param {number} now
   * @returns {import("geojson").FeatureCollection<import("geojson").Point>}
   */
  vehicleFeatures(now) {
    const vehiclesById = new Map(this.state.vehicles.map((vehicle) => [vehicle.id, vehicle]));
    return collection(
      this.state.transports.flatMap((trip) => {
        const route = this.routes.get(trip.id);
        const pose =
          route && routePose(route, routeProgress(now, trip.departed_at, trip.arrives_at));
        if (!pose) return [];
        const vehicle = vehiclesById.get(trip.vehicle_id);
        const modelId = vehicle?.model_id ?? "";
        const hasIcon = this.availableVehicleModels.has(modelId);
        return [
          pointFeature(pose.coordinate, {
            id: trip.id,
            vehicleId: trip.vehicle_id,
            modelId,
            iconImage: hasIcon ? vehicleIconId(modelId) : "",
            hasIcon,
            bearing: pose.bearing,
          }),
        ];
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
