import { ZOOM_TIERS } from "./grouping.js";

function addAssetLayer(map, id, color, radius, stroke) {
  map.addLayer({
    id,
    type: "circle",
    source: id,
    minzoom: ZOOM_TIERS.assets,
    paint: {
      "circle-radius": radius,
      "circle-color": color,
      "circle-stroke-width": 2,
      "circle-stroke-color": stroke,
    },
  });
}

/** Add facilities, opportunities and selection markers.
 * @param {import('maplibre-gl').Map} map
 * @returns {void}
 */
export function addLocationLayers(map) {
  map.addLayer({
    id: "hub-clusters",
    type: "circle",
    source: "hubs",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": "#163d52",
      "circle-radius": ["step", ["get", "point_count"], 19, 3, 24],
      "circle-stroke-width": 4,
      "circle-stroke-color": "#f6bc43",
    },
  });
  map.addLayer({
    id: "hub-points",
    type: "circle",
    source: "hubs",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-color": "#102b3c",
      "circle-radius": 9,
      "circle-stroke-width": 3,
      "circle-stroke-color": "#fff",
    },
  });
  addAssetLayer(map, "orders", "#f6bc43", 5, "#102b3c");
  addAssetLayer(map, "parked", "#26a983", 6, "#fff");
  map.addLayer({
    id: "selection",
    type: "circle",
    source: "selection",
    paint: {
      "circle-radius": 25,
      "circle-color": "#ffffff",
      "circle-opacity": 0.12,
      "circle-stroke-color": "#a624ec",
      "circle-stroke-width": 4,
    },
  });
  map.addLayer({
    id: "selected-locations",
    type: "circle",
    source: "selected-locations",
    paint: {
      "circle-radius": 13,
      "circle-color": "#963fad",
      "circle-stroke-color": "#fff",
      "circle-stroke-width": 4,
    },
  });
  for (const name of ["companies", "depots"])
    map.addLayer({
      id: name,
      type: "circle",
      source: name,
      paint: { "circle-color": "#7595ae", "circle-radius": 7 },
    });
}
