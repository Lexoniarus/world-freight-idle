import { VEHICLE_SIZE_STOPS } from "./vehicle-footprint.js";

function addVehiclePair(map, source, layer) {
  map.addLayer({
    id: `${layer}-fallback`,
    type: "circle",
    source,
    filter: ["==", ["get", "hasIcon"], false],
    paint: {
      "circle-radius": 9,
      "circle-color": ["coalesce", ["get", "playerColor"], "#f6bc43"],
      "circle-stroke-width": 3,
      "circle-stroke-color": "#102b3c",
    },
  });
  map.addLayer({
    id: layer,
    type: "symbol",
    source,
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
}

function addIdleVariant(map, id) {
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

/** Add private, multiplayer and selected vehicle presentation.
 * @param {import('maplibre-gl').Map} map
 * @returns {void}
 */
export function addVehicleLayers(map) {
  addVehiclePair(map, "multiplayer-vehicles", "multiplayer-vehicles");
  addVehiclePair(map, "vehicles", "vehicles");
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
  for (const id of ["vehicles", "multiplayer-vehicles", "selected-vehicle-assets"])
    addIdleVariant(map, id);
}
