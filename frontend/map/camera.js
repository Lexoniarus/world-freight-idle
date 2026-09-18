import { LngLatBounds } from "maplibre-gl";
import { nearestLongitude } from "../geometry.js";

/** Shift a continuous route as a unit into the closest repeated world.
 * @param {number[][]} points
 * @param {number} reference
 * @returns {number[][]}
 */
export function shiftRoute(points, reference) {
  if (!points.length) return [];
  const [min, max] = points.reduce(
    ([min, max], [lon]) => [Math.min(min, lon), Math.max(max, lon)],
    [Infinity, -Infinity],
  );
  const center = (min + max) / 2;
  const shift = nearestLongitude(center, reference) - center;
  return points.map(([lon, lat]) => [lon + shift, lat]);
}

/** Find the smallest circular interval containing unrelated fleet positions.
 * @param {number[][]} points
 * @param {number} reference
 * @returns {number[][]}
 */
export function frameFleet(points, reference) {
  if (!points.length) return [];
  const normalized = points.map(([lon, lat]) => [((lon % 360) + 360) % 360, lat]);
  const sorted = normalized.map(([lon]) => lon).sort((a, b) => a - b);
  let gap = -1;
  let start = sorted[0];
  sorted.forEach((lon, index) => {
    const next = sorted[(index + 1) % sorted.length] + (index === sorted.length - 1 ? 360 : 0);
    if (next - lon > gap) {
      gap = next - lon;
      start = next % 360;
    }
  });
  return shiftRoute(
    normalized.map(([lon, lat]) => [lon < start ? lon + 360 : lon, lat]),
    reference,
  );
}

/** Frame overlays without changing the persistent map instance. */
export class MapCamera {
  /** @param {Pick<import('maplibre-gl').Map, 'getCenter' | 'fitBounds'>} map
   * @param {() => boolean} reducedMotion
   * @param {() => {width: number, height: number, panelOpen: boolean}} viewport
   */
  constructor(map, reducedMotion, viewport) {
    this.map = map;
    this.reducedMotion = reducedMotion;
    this.viewport = viewport;
  }
  /** Frame an already unwrapped continuous route. @param {number[][]} points */
  fitRoute(points) {
    this.fitBounds(shiftRoute(points, this.map.getCenter().lng));
  }
  /** Frame unrelated vehicle positions. @param {number[][]} points */
  fitCoordinates(points) {
    this.fitBounds(frameFleet(points, this.map.getCenter().lng));
  }
  /** Apply panel padding and the user's motion preference. @param {number[][]} points */
  fitBounds(points) {
    if (!points.length) return;
    const bounds = points.reduce(
      (box, point) => box.extend(/** @type {[number, number]} */ (point)),
      new LngLatBounds(),
    );
    const { width, height, panelOpen } = this.viewport();
    const mobile = width < 760;
    this.map.fitBounds(bounds, {
      maxZoom: 12,
      duration: this.reducedMotion() ? 0 : 700,
      padding: {
        top: 140,
        left: mobile ? 45 : 130,
        right: !mobile && panelOpen ? 470 : 65,
        bottom: mobile && panelOpen ? Math.min(height * 0.62, 480) : 100,
      },
    });
  }
}
