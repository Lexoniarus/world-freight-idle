import "./test-dom.mjs";
import assert from "node:assert/strict";
import test from "node:test";
import { VehicleGroups } from "./map/vehicle-groups.js";
import { groupVehicles } from "./map/grouping.js";

const vehicle = (id, isOwn = true) => ({
  geometry: { coordinates: [13.4, 52.5] },
  properties: {
    id: `transport-${id}`,
    idle: true,
    isOwn,
    key: `${isOwn ? "own" : "other"}:${id}`,
    modelName: `Truck ${id}`,
    username: "Other player",
    vehicleId: id,
  },
});

class PopupDouble {
  setLngLat(coordinate) {
    this.coordinate = coordinate;
    return this;
  }
  setDOMContent(content) {
    this.content = content;
    return this;
  }
  addTo(map) {
    map.popup = this;
    document.body.append(this.content);
    return this;
  }
  remove() {
    this.removed = true;
    this.content?.remove();
  }
}

const setup = (zoom = 17) => {
  const map = {
    zoom,
    getZoom() {
      return this.zoom;
    },
    easeTo(options) {
      this.ease = options;
      this.zoom = options.zoom;
    },
  };
  const selections = [];
  const groups = new VehicleGroups(
    map,
    (value) => selections.push(value),
    () => true,
    {
      createPopup: () => new PopupDouble(),
    },
  );
  return { groups, map, selections };
};

test("group activation zooms toward the expansion limit", () => {
  const { groups, map } = setup(14);
  groups.markers.set("own:a", {
    marker: { getLngLat: () => ({ lng: 13.4, lat: 52.5 }) },
    members: [vehicle("a"), vehicle("b")],
  });

  groups.activateGroup("own:a");

  assert.deepEqual(map.ease, {
    center: { lng: 13.4, lat: 52.5 },
    zoom: 16,
    duration: 0,
  });
});

test("group activation opens the vehicle list at the expansion limit", () => {
  const { groups, map } = setup();
  groups.markers.set("own:a", {
    marker: { getLngLat: () => ({ lng: 13.4, lat: 52.5 }) },
    members: [vehicle("a"), vehicle("b")],
  });

  groups.activateGroup("own:a");

  assert.equal(map.popup.content.className, "map-object-list");
  assert.equal(map.popup.content.querySelectorAll("button").length, 2);
});

test("vehicle list focuses the first selectable vehicle", () => {
  const { groups } = setup();

  groups.showVehicleList([vehicle("foreign", false), vehicle("own")], [13.4, 52.5]);

  assert.equal(document.activeElement.textContent, "Truck own · own");
});

test("vehicle selection emits the own-vehicle payload", () => {
  const { groups, selections } = setup();
  groups.showVehicleList([vehicle("a")], [13.4, 52.5]);

  groups.popup.content.querySelector("button").click();

  assert.deepEqual(selections, [
    {
      kind: "own-vehicle",
      idle: true,
      vehicleId: "a",
      transportId: "transport-a",
    },
  ]);
  assert.equal(groups.popup.removed, true);
});

test("throttled groups update the existing representative pose", () => {
  const positions = [];
  const button = document.createElement("button");
  const first = vehicle("a");
  first.properties.idle = false;
  first.properties.movementState = "enroute";
  first.properties.bearing = 137;
  const entry = {
    button,
    members: [first, vehicle("b")],
    marker: { setLngLat: (position) => positions.push(position) },
  };
  const groups = {
    map: { getCenter: () => ({ lng: 0 }) },
    markers: new Map([["own:a", entry]]),
  };
  const moved = structuredClone(first);
  moved.geometry.coordinates = [12, 0];
  moved.properties.bearing = 271;

  VehicleGroups.prototype.updatePoses.call(groups, [moved, vehicle("b")]);
  VehicleGroups.prototype.renderVisual(button, entry.members);

  assert.deepEqual(positions, [[12, 0]]);
  assert.equal(entry.members[0], moved);
  assert.equal(button.dataset.representative, "own:a");
  assert.equal(button.dataset.movement, "enroute");
  assert.equal(button.textContent, "2");
});

test("group visual keeps a stable representative and separates owners", () => {
  const model = "iveco_sway_500";
  const members = ["one", "two"].map((username, index) => ({
    properties: {
      key: username,
      username,
      modelId: index ? model : "unknown",
      playerColor: "#e45756",
      idle: true,
    },
    geometry: { coordinates: [13, 52] },
  }));
  assert.equal(groupVehicles(members, () => ({ x: 0, y: 0 })).length, 2);

  const button = document.createElement("button");
  VehicleGroups.prototype.renderVisual(button, members);
  assert.equal(button.dataset.representative, "one");
  assert.equal(button.dataset.movement, "idle");
  assert.equal(button.querySelector("img"), null);
  assert.equal(button.querySelector(".vehicle-group-count").textContent, "2");

  const badge = button.querySelector(".vehicle-group-count");
  VehicleGroups.prototype.renderVisual(button, members);
  assert.equal(button.querySelector(".vehicle-group-count"), badge);
});
