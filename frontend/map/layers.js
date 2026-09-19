import { collection } from "../geometry.js";

/** Register independent game sources and their presentation layers.
 * @param {import("maplibre-gl").Map} map */
export function addOverlayLayers(map) {
  for (const name of [
    "hubs",
    "orders",
    "parked",
    "vehicles",
    "routes",
    "preview",
    "companies",
    "depots",
  ]) {
    map.addSource(name, {
      type: "geojson",
      data: collection(),
      ...(name === "hubs" ? { cluster: true, clusterRadius: 45, clusterMaxZoom: 8 } : {}),
    });
  }
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
  map.addLayer({
    id: "hub-labels",
    type: "symbol",
    source: "hubs",
    filter: ["!", ["has", "point_count"]],
    layout: {
      "icon-image": ["get", "labelImage"],
      "icon-anchor": "top",
      "icon-offset": [0, 16],
      "icon-size": 0.5,
    },
  });
  map.addLayer({
    id: "orders",
    type: "circle",
    source: "orders",
    paint: {
      "circle-radius": 5,
      "circle-color": "#f6bc43",
      "circle-translate": [15, -15],
      "circle-stroke-width": 2,
      "circle-stroke-color": "#102b3c",
    },
  });
  map.addLayer({
    id: "parked",
    type: "circle",
    source: "parked",
    paint: {
      "circle-radius": 6,
      "circle-color": "#26a983",
      "circle-translate": [-15, -15],
      "circle-stroke-width": 2,
      "circle-stroke-color": "#fff",
    },
  });
  map.addLayer({
    id: "vehicles",
    type: "circle",
    source: "vehicles",
    paint: {
      "circle-radius": 9,
      "circle-color": "#f6bc43",
      "circle-stroke-width": 3,
      "circle-stroke-color": "#102b3c",
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

/** Draw one public-hub label; canvas text never becomes HTML.
 * @param {import("maplibre-gl").Map} map
 * @param {import("../types.js").Hub} hub
 * @param {import("../types.js").MapState} data
 */
export function updateHubLabel(map, hub, data) {
  const count = data.vehicles.filter((v) => v.hub_id === hub.id && v.status === "idle").length;
  const orders = data.contracts.filter((c) => c.origin_hub_id === hub.id).length;
  const canvas = document.createElement("canvas");
  canvas.width = 400;
  canvas.height = 104;
  const context = canvas.getContext("2d");
  context.fillStyle = "#102b3c";
  context.beginPath();
  context.roundRect(2, 2, 396, 100, 16);
  context.fill();
  context.textAlign = "center";
  context.fillStyle = "#ffffff";
  context.font = "600 28px Inter, sans-serif";
  const title = hub.label.length > 28 ? hub.label.slice(0, 27) + "…" : hub.label;
  context.fillText(title, 200, 40, 376);
  context.font = "22px Inter, sans-serif";
  context.fillStyle = "#a9c1cf";
  context.fillText(`${hub.city} · ${count} Lkw · ${orders} Aufträge`, 200, 76, 376);
  const image = context.getImageData(0, 0, 400, 104);
  const id = "label-" + hub.id;
  if (map.hasImage(id)) map.updateImage(id, image);
  else map.addImage(id, image);
}
