import { collection, pointFeature, prepareRoute, routePose, unwrapRoute } from "../geometry.js";
import { transportProgress } from "../journey.js";
import { vehicleIconId } from "./vehicle-assets.js";

export const routeGeometry = (route) => (route.type === "Feature" ? route.geometry : route);

export class OverlayData {
  constructor() {
    this.hubs = [];
    this.routes = new Map();
    this.trafficRoutes = new Map();
    this.availableVehicleIcons = new Set();
    this.state = { vehicles: [], contracts: [], transports: [], traffic: [] };
  }

  setVehicleIcons(imageIds) {
    this.availableVehicleIcons = new Set(imageIds);
  }

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
        snapshots.map((facility) => [facility.facility_uid ?? facility.id, facility]),
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

  hubFeatures() {
    return collection(
      this.hubs.map((hub) => pointFeature([hub.lon, hub.lat], this.hubProperties(hub))),
    );
  }

  locationFeatures(items, key) {
    return collection(
      this.hubs
        .filter((hub) => items.some((item) => item[key] === hub.id))
        .map((hub) => pointFeature([hub.lon, hub.lat], this.hubProperties(hub))),
    );
  }

  hubProperties(hub) {
    return {
      id: hub.id,
      label: hub.label,
      city: hub.city,
      idleTruckCount: this.state.vehicles.filter(
        (vehicle) => vehicle.status === "idle" && vehicle.hub_id === hub.id,
      ).length,
      orderCount: this.state.contracts.filter((contract) => contract.origin_hub_id === hub.id)
        .length,
    };
  }

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

  vehicleFeatures(now) {
    return this.trafficFeatures(now, true);
  }

  multiplayerVehicleFeatures(now) {
    return this.trafficFeatures(now, false);
  }

  trafficFeatures(now, isOwn) {
    return collection(
      this.state.traffic.flatMap((trip) => {
        if (trip.is_own !== isOwn) return [];
        const route = this.trafficRoutes.get(trip.id);
        const pose = route && routePose(route, transportProgress(trip, now).fraction);
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
