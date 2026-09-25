import { selectFleetGroups } from "../fleet-selection.js";
import { prepareTransportRoute, transportRoutePose } from "./route-plan.js";
import { cityLocations } from "../city-context.js";

/** Project finite location snapshots to map coordinates. */
function coordinates(locations) {
  return locations
    .filter((item) => Number.isFinite(item?.lon) && Number.isFinite(item?.lat))
    .map((item) => [item.lon, item.lat]);
}

/** Locate a vehicle using its journey rather than its departure checkpoint. */
export function vehiclePosition(state, vehicle, now) {
  const trip = state.transports.find((item) => item.vehicle_id === vehicle.id);
  if (!trip) return coordinates([vehicle.location_snapshot ?? vehicle.hub]);
  const pose = transportRoutePose(prepareTransportRoute(trip), trip, now);
  return pose ? [pose.coordinate] : [];
}

/** Include the saved entire route and the current journey position. */
export function transportCoordinates(trip, now) {
  const route = prepareTransportRoute(trip);
  const pose = transportRoutePose(route, trip, now);
  return [
    ...route.points,
    ...coordinates([trip.start, trip.origin, trip.destination]),
    ...(pose ? [pose.coordinate] : []),
  ];
}

/** Resolve a navigation target; null means its detail has not arrived yet.
 * @param {any} state @param {URL} url @param {number} now
 * @param {any} detail @param {string} cityUid @param {any[]} cities
 * @returns {number[][] | null}
 */
export function focusCoordinates(state, url, now, detail, cityUid, cities) {
  const [, section, id] = url.pathname.split("/");
  if (section === "fleet") {
    if (id) {
      const vehicle = state.vehicles.find((item) => item.id === id);
      return vehicle ? vehiclePosition(state, vehicle, now) : [];
    }
    const groups = selectFleetGroups(state, url, cityUid);
    const vehicles = new Map(
      groups
        .flatMap((group) => [...group.stationed, ...group.inbound, ...group.outbound])
        .map(({ vehicle }) => [vehicle.id, vehicle]),
    );
    return [...vehicles.values()].flatMap((vehicle) => vehiclePosition(state, vehicle, now));
  }
  if (section === "transports")
    return state.transports
      .filter((trip) => !id || trip.id === id)
      .flatMap((trip) => transportCoordinates(trip, now));
  if (section === "contracts" && id) {
    const offer = detail?.id === id ? detail : state.contracts.find((item) => item.id === id);
    return offer ? coordinates([offer.origin, offer.destination]) : null;
  }
  if (section === "contracts" && cityUid)
    return coordinates(
      [...cityLocations(state), ...cities].filter((city) => city.city_uid === cityUid),
    );
  return [];
}
