export const DEFAULT_VEHICLE_COLOR = "#f6bc43";
const SAFE_COLOR = /^#[0-9a-f]{6}$/i;

/** Normalize untrusted map color input to one supported hex value.
 * @param {string | undefined} color
 * @returns {string}
 */
export function normalizeVehicleColor(color) {
  return color && SAFE_COLOR.test(color) ? color.toLowerCase() : DEFAULT_VEHICLE_COLOR;
}
