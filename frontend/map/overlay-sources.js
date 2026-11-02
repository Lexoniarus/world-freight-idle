import { collection } from "../geometry.js";

const sourceNames = [
  "hubs",
  "orders",
  "parked",
  "vehicles",
  "multiplayer-vehicles",
  "routes",
  "preview",
  "companies",
  "depots",
  "selection",
  "selected-locations",
  "selected-route",
];

/** Register empty overlay sources before their presentation layers.
 * @param {import('maplibre-gl').Map} map
 * @returns {void}
 */
export function addOverlaySources(map) {
  for (const name of sourceNames)
    map.addSource(name, {
      type: "geojson",
      data: collection(),
      ...(name === "hubs" ? { cluster: true, clusterRadius: 45, clusterMaxZoom: 8 } : {}),
    });
}
