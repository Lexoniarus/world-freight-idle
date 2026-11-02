/** Add saved, preview and selected route presentation.
 * @param {import('maplibre-gl').Map} map
 * @returns {void}
 */
export function addRouteLayers(map) {
  map.addLayer({
    id: "routes",
    type: "line",
    source: "routes",
    paint: {
      "line-color": ["case", ["==", ["get", "id"], ""], "#f6bc43", "#267e9a"],
      "line-width": ["case", ["==", ["get", "id"], ""], 6, 3],
      "line-opacity": 0.85,
    },
  });
  map.addLayer({
    id: "preview",
    type: "line",
    source: "preview",
    paint: { "line-color": "#d58b16", "line-width": 5, "line-dasharray": [2, 1] },
  });
  map.addLayer({
    id: "selected-route",
    type: "line",
    source: "selected-route",
    paint: { "line-color": "#8b25b5", "line-width": 5, "line-opacity": 0.95 },
  });
}
