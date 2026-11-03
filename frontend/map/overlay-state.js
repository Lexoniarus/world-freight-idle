import { prepareTransportRoute } from "./route-plan.js";

/** Merge private transport details into public traffic without duplicates. */
export function mergeOwnTraffic(state, companyColor) {
  const publicOwn = new Map(
    (state.traffic ?? []).filter((trip) => trip.is_own).map((trip) => [trip.id, trip]),
  );
  const otherTraffic = (state.traffic ?? []).filter((trip) => !trip.is_own);
  const ownTraffic = state.transports.map((trip) => {
    const vehicle = state.vehicles.find((item) => item.id === trip.vehicle_id);
    const published = publicOwn.get(trip.id);
    return {
      ...published,
      ...trip,
      model_id: vehicle?.model_id ?? published?.model_id,
      model_name: vehicle?.name ?? published?.model_name,
      is_own: true,
      username: published?.username ?? "",
      player_color: companyColor ?? published?.player_color,
    };
  });
  return { ...state, traffic: [...otherTraffic, ...ownTraffic] };
}

/** Collect each resolved facility once from the current overlay state. */
export function collectResolvedHubs(state) {
  const snapshots = [
    ...state.transports.flatMap((trip) => [
      trip.start,
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
  return [
    ...new Map(
      snapshots.map((facility) => [facility.facility_uid ?? facility.id, facility]),
    ).values(),
  ];
}

/** Retain active route plans and prepare only newly observed transports. */
export function synchronizeRoutePlans(routes, transports, fallbackRoutes = new Map()) {
  const active = new Set(transports.map((trip) => trip.id));
  for (const id of routes.keys()) if (!active.has(id)) routes.delete(id);
  for (const trip of transports) {
    if (routes.has(trip.id) || routeCoordinates(trip).length < 2) continue;
    routes.set(trip.id, fallbackRoutes.get(trip.id) ?? prepareTransportRoute(trip));
  }
}

function routeCoordinates(transport) {
  const route = transport.route_geojson;
  return (route.type === "Feature" ? route.geometry : route).coordinates;
}
