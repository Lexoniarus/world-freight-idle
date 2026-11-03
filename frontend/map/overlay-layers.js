import { addLocationLayers } from "./location-layers.js";
import { addOverlaySources } from "./overlay-sources.js";
import { addRouteLayers } from "./route-layers.js";
import { addVehicleLayers } from "./vehicle-layers.js";

/** Assemble overlay sources and focused presentation layers.
 * @param {import('maplibre-gl').Map} map
 * @returns {void}
 */
export function addOverlayLayers(map) {
  addOverlaySources(map);
  addRouteLayers(map);
  addLocationLayers(map);
  addVehicleLayers(map);
}
