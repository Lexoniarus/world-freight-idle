/** @template {import("geojson").Geometry} [G=import("geojson").Geometry]
 * @param {import("geojson").Feature<G>[]} [features]
 * @returns {import("geojson").FeatureCollection<G>} */
export const collection = (features = []) => ({ type: "FeatureCollection", features });
/** @param {number[]} coordinates
 * @param {Record<string, unknown>} properties
 * @returns {import("geojson").Feature<import("geojson").Point>} */
export const pointFeature = (coordinates, properties) => ({
  type: "Feature",
  geometry: { type: "Point", coordinates },
  properties,
});
/** @param {number} longitude
 * @param {number} reference
 * @returns {number} */
export const nearestLongitude = (longitude, reference) =>
  longitude + 360 * Math.round((reference - longitude) / 360);

/** @param {number[][]} coordinates
 * @returns {number[][]} */
export function unwrapRoute(coordinates) {
  return coordinates.reduce((points, [longitude, latitude]) => {
    points.push([
      points.length ? nearestLongitude(longitude, points.at(-1)[0]) : longitude,
      latitude,
    ]);
    return points;
  }, /** @type {number[][]} */ ([]));
}

// Cumulative great-circle distances are computed once per immutable trip.
/** @param {number[][]} coordinates
 * @returns {import('./types.js').PreparedRoute} */
export function prepareRoute(coordinates) {
  const points = unwrapRoute(coordinates);
  const distances = [0];
  const rad = Math.PI / 180;
  for (let index = 1; index < points.length; index++) {
    const [a, b] = [points[index - 1], points[index]];
    const haversine =
      Math.sin(((b[1] - a[1]) * rad) / 2) ** 2 +
      Math.cos(a[1] * rad) * Math.cos(b[1] * rad) * Math.sin(((b[0] - a[0]) * rad) / 2) ** 2;
    distances.push(distances.at(-1) + 2 * Math.asin(Math.sqrt(Math.min(1, haversine))));
  }
  return { points, distances, total: distances.at(-1) };
}

/** @param {import('./types.js').PreparedRoute} route
 * @param {number} fraction
 * @returns {number[] | null} */
export function routePosition(route, fraction) {
  const { points, distances, total } = route;
  if (!points.length) return null;
  if (!total || fraction <= 0) return points[0];
  if (fraction >= 1) return points.at(-1);
  const target = total * fraction;
  let low = 1;
  let high = points.length - 1;
  while (low < high) {
    const mid = (low + high) >> 1;
    if (distances[mid] < target) low = mid + 1;
    else high = mid;
  }
  const length = distances[low] - distances[low - 1];
  const ratio = length ? (target - distances[low - 1]) / length : 0;
  return points[low].map(
    (value, axis) => points[low - 1][axis] + (value - points[low - 1][axis]) * ratio,
  );
}

/** @param {import('./types.js').Vehicle[]} vehicles
 * @param {import('./types.js').Contract} contract */
export function eligibleVehicles(vehicles, contract) {
  return vehicles.filter(
    (vehicle) =>
      vehicle.status === "idle" &&
      (vehicle.facility_uid ?? vehicle.hub_id) ===
        (contract.origin_facility_uid ?? contract.origin_hub_id) &&
      vehicle.capacity_tons >= contract.tons &&
      vehicle.mode === contract.mode,
  );
}

/** Match a stable facility UID or an explicitly retained old URL alias.
 * @param {import('./types.js').Hub} facility
 * @param {string | null} identifier
 * @returns {boolean}
 */
export function matchesFacility(facility, identifier) {
  return (
    !identifier ||
    (facility.facility_uid ?? facility.id) === identifier ||
    (facility.aliases ?? []).includes(identifier)
  );
}
