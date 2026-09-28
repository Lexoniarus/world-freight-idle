import { VEHICLE_SIZE_STOPS } from "./vehicle-footprint.js";
import { collection } from "../geometry.js";
import { ZOOM_TIERS } from "./grouping.js";

export function addOverlayLayers(map) {
  for (const name of [
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
    id: "orders",
    type: "circle",
    source: "orders",
    minzoom: ZOOM_TIERS.assets,
    paint: {
      "circle-radius": 5,
      "circle-color": "#f6bc43",
      "circle-stroke-width": 2,
      "circle-stroke-color": "#102b3c",
    },
  });
  map.addLayer({
    id: "parked",
    type: "circle",
    source: "parked",
    minzoom: ZOOM_TIERS.assets,
    paint: {
      "circle-radius": 6,
      "circle-color": "#26a983",
      "circle-stroke-width": 2,
      "circle-stroke-color": "#fff",
    },
  });
  map.addLayer({
    id: "multiplayer-vehicles-fallback",
    type: "circle",
    source: "multiplayer-vehicles",
    filter: ["==", ["get", "hasIcon"], false],
    paint: {
      "circle-radius": 9,
      "circle-color": ["coalesce", ["get", "playerColor"], "#f6bc43"],
      "circle-stroke-width": 3,
      "circle-stroke-color": "#102b3c",
    },
  });
  map.addLayer({
    id: "multiplayer-vehicles",
    type: "symbol",
    source: "multiplayer-vehicles",
    filter: ["==", ["get", "hasIcon"], true],
    layout: {
      "icon-image": ["get", "iconImage"],
      "icon-rotate": ["get", "bearing"],
      "icon-rotation-alignment": "map",
      "icon-pitch-alignment": "map",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
      "icon-size": ["interpolate", ["linear"], ["zoom"], ...VEHICLE_SIZE_STOPS],
    },
  });
  map.addLayer({
    id: "vehicles-fallback",
    type: "circle",
    source: "vehicles",
    filter: ["==", ["get", "hasIcon"], false],
    paint: {
      "circle-radius": 9,
      "circle-color": ["coalesce", ["get", "playerColor"], "#f6bc43"],
      "circle-stroke-width": 3,
      "circle-stroke-color": "#102b3c",
    },
  });
  map.addLayer({
    id: "vehicles",
    type: "symbol",
    source: "vehicles",
    filter: ["==", ["get", "hasIcon"], true],
    layout: {
      "icon-image": ["get", "iconImage"],
      "icon-rotate": ["get", "bearing"],
      "icon-rotation-alignment": "map",
      "icon-pitch-alignment": "map",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
      "icon-size": ["interpolate", ["linear"], ["zoom"], ...VEHICLE_SIZE_STOPS],
    },
  });
  map.addLayer({
    id: "selected-route",
    type: "line",
    source: "selected-route",
    paint: { "line-color": "#8b25b5", "line-width": 5, "line-opacity": 0.95 },
  });
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
  map.addLayer({
    id: "selected-vehicle-assets",
    type: "symbol",
    source: "selection",
    filter: ["==", ["get", "hasIcon"], true],
    layout: {
      "icon-image": ["get", "iconImage"],
      "icon-rotate": ["get", "bearing"],
      "icon-rotation-alignment": "map",
      "icon-size": 1,
      "icon-allow-overlap": true,
    },
  });
  for (const id of ["vehicles", "multiplayer-vehicles", "selected-vehicle-assets"]) {
    const original = map.getLayer(id);
    const idle = original.serialize();
    idle.id = id + "-idle";
    idle.filter = ["all", ["==", ["get", "hasIcon"], true], ["==", ["get", "idle"], true]];
    idle.layout["icon-rotate"] = 0;
    idle.layout["icon-rotation-alignment"] = "viewport";
    idle.layout["icon-pitch-alignment"] = "viewport";
    map.setFilter(id, ["all", ["==", ["get", "hasIcon"], true], ["!=", ["get", "idle"], true]]);
    map.addLayer(idle);
  }
  for (const name of ["companies", "depots"])
    map.addLayer({
      id: name,
      type: "circle",
      source: name,
      paint: { "circle-color": "#7595ae", "circle-radius": 7 },
    });
}
