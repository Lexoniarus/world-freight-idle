import { prepareRoute, routePose } from "../geometry.js";
import { transportProgress } from "../journey.js";

/** Cache total drawing geometry and each separately routed section. */
export function prepareTransportRoute(trip) {
  const geometry =
    trip.route_geojson.type === "Feature" ? trip.route_geojson.geometry : trip.route_geojson;
  return {
    ...prepareRoute(geometry.coordinates),
    legs: (trip.route_legs ?? []).map((leg) => ({
      ...leg,
      route: prepareRoute(leg.coordinates),
    })),
  };
}

/** Interpolate within the active leg using saved road kilometres. */
export function transportRoutePose(route, trip, now) {
  const progress = transportProgress(trip, now);
  const leg = route.legs.find((part) => progress.distanceKm < part.end_km) ?? route.legs.at(-1);
  if (!leg) return routePose(route, progress.fraction);
  return routePose(leg.route, (progress.distanceKm - leg.start_km) / (leg.end_km - leg.start_km));
}
