import { collection, pointFeature, unwrapRoute } from "../geometry.js";
import { transportRoutePose } from "./route-plan.js";
import { collectResolvedHubs, mergeOwnTraffic, synchronizeRoutePlans } from "./overlay-state.js";
import { vehicleIconId } from "./vehicle-icon-registry.js";

export const routeGeometry = (route) => (route.type === "Feature" ? route.geometry : route);

export class OverlayData {
  constructor() {
    this.hubs = [];
    this.companyColor = undefined;
    this.routes = new Map();
    this.trafficRoutes = new Map();
    this.availableVehicleIcons = new Set();
    this.iconBounds = new Map();
    this.state = { vehicles: [], contracts: [], transports: [], traffic: [], marketLoaded: false };
  }

  setVehicleIcons(imageIds, bounds = new Map()) {
    this.iconBounds = new Map(bounds);
    this.availableVehicleIcons = new Set(imageIds);
  }

  update(state) {
    this.state = mergeOwnTraffic(state, this.companyColor);
    this.hubs = collectResolvedHubs(this.state);
    synchronizeRoutePlans(this.routes, this.state.transports);
    synchronizeRoutePlans(this.trafficRoutes, this.state.traffic, this.routes);
  }

  /** Suppress facilities only beneath rendered own idle representatives. */
  hubFeatures(rendered = []) {
    const occupied = new Set(
      rendered
        .filter((feature) => feature.properties.isOwn && feature.properties.idle)
        .map((feature) => feature.geometry.coordinates.join(",")),
    );
    return collection(
      this.hubs
        .filter((hub) => !occupied.has([hub.lon, hub.lat].join(",")))
        .map((hub) => pointFeature([hub.lon, hub.lat], this.hubProperties(hub))),
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
      cityUid: hub.city_uid,
      idleTruckCount: this.state.vehicles.filter(
        (vehicle) => vehicle.status === "idle" && vehicle.hub_id === hub.id,
      ).length,
      orderCount:
        this.state.marketLoaded === false
          ? null
          : this.state.contracts.filter((contract) => contract.origin_hub_id === hub.id).length,
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
    const moving = this.trafficFeatures(now, true);
    const idle = this.state.vehicles
      .filter(
        (vehicle) =>
          vehicle.status === "idle" &&
          !this.state.transports.some((trip) => trip.vehicle_id === vehicle.id),
      )
      .flatMap((vehicle) => {
        const location = vehicle.location_snapshot ?? vehicle.hub;
        if (!Number.isFinite(location?.lon) || !Number.isFinite(location?.lat)) return [];
        const iconImage = vehicleIconId(vehicle.model_id, this.companyColor, "front");
        return [
          pointFeature([location.lon, location.lat], {
            id: vehicle.id,
            key: "own:" + vehicle.id,
            vehicleId: vehicle.id,
            modelId: vehicle.model_id,
            modelName: vehicle.name,
            iconImage,
            hasIcon: this.availableVehicleIcons.has(iconImage),
            iconBounds: this.iconBounds.get(iconImage),
            bearing: 0,
            playerColor: this.companyColor,
            isOwn: true,
            idle: true,
            movementState: "idle",
          }),
        ];
      });
    return collection([...moving.features, ...idle]);
  }

  multiplayerVehicleFeatures(now) {
    return this.trafficFeatures(now, false);
  }

  trafficFeatures(now, isOwn) {
    return collection(
      this.state.traffic.flatMap((trip) => {
        if (trip.is_own !== isOwn) return [];
        const route = this.trafficRoutes.get(trip.id);
        const pose = route && transportRoutePose(route, trip, now);
        if (!pose) return [];
        const color = trip.is_own ? (this.companyColor ?? trip.player_color) : trip.player_color;
        const iconImage = vehicleIconId(trip.model_id, color);
        const hasIcon = Boolean(iconImage && this.availableVehicleIcons.has(iconImage));
        return [
          pointFeature(pose.coordinate, {
            id: trip.id,
            key: (trip.is_own ? "own:" : trip.username + ":") + trip.vehicle_id,
            vehicleId: trip.vehicle_id,
            modelId: trip.model_id,
            modelName: trip.model_name,
            iconImage: hasIcon ? iconImage : "",
            hasIcon,
            iconBounds: this.iconBounds.get(iconImage),
            bearing: pose.bearing,
            movementState: "enroute",
            idle: false,
            playerColor: color,
            username: trip.username,
            isOwn: trip.is_own,
          }),
        ];
      }),
    );
  }

  fleetCoordinates(now) {
    return [
      ...new Map(
        this.vehicleFeatures(now).features.map((feature) => [
          feature.geometry.coordinates.join(","),
          feature.geometry.coordinates,
        ]),
      ).values(),
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
