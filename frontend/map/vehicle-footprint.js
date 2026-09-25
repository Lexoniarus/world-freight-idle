/** Shared rendering stops; clustering has no zoom threshold. */
export const VEHICLE_SIZE_STOPS = [5, 0.55, 9, 0.75, 13, 1, 17, 1.15];

/** Evaluate the same linear scale used by MapLibre's symbol layer.
 * @param {number} zoom @returns {number} */
export function vehicleIconScale(zoom) {
  for (let i = 2; i < VEHICLE_SIZE_STOPS.length; i += 2) {
    if (zoom <= VEHICLE_SIZE_STOPS[i]) {
      const fraction = Math.max(
        0,
        (zoom - VEHICLE_SIZE_STOPS[i - 2]) / (VEHICLE_SIZE_STOPS[i] - VEHICLE_SIZE_STOPS[i - 2]),
      );
      return (
        VEHICLE_SIZE_STOPS[i - 1] +
        fraction * (VEHICLE_SIZE_STOPS[i + 1] - VEHICLE_SIZE_STOPS[i - 1])
      );
    }
  }
  return VEHICLE_SIZE_STOPS.at(-1);
}

/** Measure the visible alpha silhouette relative to the centered icon anchor.
 * @param {ImageData} image @returns {number[]}
 */
export function spriteBounds(image) {
  let left = image.width,
    right = 0,
    top = image.height,
    bottom = 0;
  for (let y = 0; y < image.height; y++)
    for (let x = 0; x < image.width; x++) {
      if (!image.data[(y * image.width + x) * 4 + 3]) continue;
      left = Math.min(left, x);
      right = Math.max(right, x + 1);
      top = Math.min(top, y);
      bottom = Math.max(bottom, y + 1);
    }
  return right > left
    ? [
        (left - image.width / 2) / 2,
        (top - image.height / 2) / 2,
        (right - image.width / 2) / 2,
        (bottom - image.height / 2) / 2,
      ]
    : [0, 0, 0, 0];
}

/** Project the visible rotated asset rectangle, excluding transparent padding.
 * @param {{properties: {hasIcon?: boolean, iconBounds?: number[], idle?: boolean, bearing?: number}}} feature
 * @param {{x: number, y: number}} point @param {number} [zoom]
 * @param {number} [mapBearing] @returns {{x: number, y: number}[]}
 */
export function vehicleFootprint(feature, point, zoom = 13, mapBearing = 0) {
  const props = feature.properties;
  const bounds = props.hasIcon ? (props.iconBounds ?? [-16, -32, 16, 32]) : [-9, -9, 9, 9];
  const scale = props.hasIcon ? vehicleIconScale(zoom) : 1;
  const angle = ((props.idle ? 0 : (props.bearing ?? 0) - mapBearing) * Math.PI) / 180;
  const [left, top, right, bottom] = bounds;
  return [
    [left, top],
    [right, top],
    [right, bottom],
    [left, bottom],
  ].map(([x, y]) => ({
    x: point.x + scale * (x * Math.cos(angle) - y * Math.sin(angle)),
    y: point.y + scale * (x * Math.sin(angle) + y * Math.cos(angle)),
  }));
}

/** Test rotated screen rectangles using separating axes, not center distance.
 * @param {{x: number, y: number}[]} a @param {{x: number, y: number}[]} b
 * @returns {boolean}
 */
export function footprintsOverlap(a, b) {
  for (const polygon of [a, b])
    for (let i = 0; i < 2; i++) {
      const edge = { x: polygon[i + 1].x - polygon[i].x, y: polygon[i + 1].y - polygon[i].y };
      const projection = (points) => points.map((point) => -edge.y * point.x + edge.x * point.y);
      const pa = projection(a),
        pb = projection(b);
      if (Math.max(...pa) <= Math.min(...pb) || Math.max(...pb) <= Math.min(...pa)) return false;
    }
  return true;
}
