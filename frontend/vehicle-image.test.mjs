import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { renderVehicleImage } from "./ui/vehicle-image.js";
import { InputController } from "./controllers/input-controller.js";

const vehicle = {
  name: "IVECO",
  capacity_tons: 24.2,
  image: {
    url: "https://upload.wikimedia.org/example.jpg",
    source_url: "https://commons.wikimedia.org/wiki/File:example.jpg",
    author: "Photographer",
    attribution: "Photo <script>alert(1)</script>",
    license_name: "CC0 1.0",
    license_url: "https://creativecommons.org/publicdomain/zero/1.0/",
    scope: "model_family",
  },
};

test("photos keep provenance, safe text, independent credential policy and illustration fallback", () => {
  document.body.replaceChildren(renderVehicleImage(vehicle));
  const image = document.querySelector("img");
  assert.equal(image.crossOrigin, "anonymous");
  assert.equal(image.getAttribute("referrerpolicy"), "no-referrer");
  assert.match(image.alt, /Modellfamilie/);
  assert.equal(document.querySelector("script"), null);
  assert.match(document.querySelector("figcaption").textContent, /<script>/);
  assert.equal(document.querySelectorAll("figcaption a").length, 2);
  assert.equal(renderVehicleImage({ ...vehicle, image: null }).querySelector("img"), null);
});

test("photo handlers reveal successful loads, describe failures and dispose listeners", () => {
  document.body.replaceChildren(renderVehicleImage(vehicle));
  const input = new InputController({ page: document });
  input.start();
  const image = document.querySelector("img");
  const figure = document.querySelector("figure");
  image.dispatchEvent(new Event("load"));
  assert.equal(figure.dataset.imageState, "loaded");
  image.dispatchEvent(new Event("error"));
  assert.equal(figure.dataset.imageState, "failed");
  input.destroy();
  image.dispatchEvent(new Event("load"));
  assert.equal(figure.dataset.imageState, "failed");
});

test("panel refresh preserves loaded and failed photo nodes but replaces changed metadata", async () => {
  const { PanelController } = await import("./controllers/panel-controller.js");
  const { html } = await import("./ui/dom.js");
  document.body.replaceChildren(
    html`<aside id="panel">
      <h2 id="panel-title"></h2>
      <div id="panel-content"></div>
    </aside>`,
  );
  const view = {
    url: new URL("http://test/fleet"),
    state: {
      vehicles: [{ ...vehicle, id: "truck_01", hub: { label: "Berlin" } }],
      transports: [],
      idle_vehicles: 1,
      active_transports: 0,
    },
  };
  const controller = new PanelController({ view, now: () => 0 });
  controller.replaceContent();
  const original = document.querySelector("img");
  original.closest("figure").dataset.imageState = "loaded";
  for (let i = 0; i < 3; i++) controller.replaceContent();
  assert.equal(document.querySelector("img"), original);
  view.state.idle_vehicles = 0; // Other panel data changes.
  controller.replaceContent();
  assert.equal(document.querySelector("img"), original);
  assert.equal(original.closest("figure").dataset.imageState, "loaded");
  original.closest("figure").dataset.imageState = "failed";
  controller.replaceContent();
  assert.equal(document.querySelector("img"), original);
  assert.equal(original.closest("figure").dataset.imageState, "failed");
  view.state.vehicles[0] = {
    ...vehicle,
    image: { ...vehicle.image, attribution: "Changed credit" },
    hub: { label: "Berlin" },
  };
  controller.replaceContent();
  assert.notEqual(document.querySelector("img"), original);
  assert.match(document.querySelector("figcaption").textContent, /Changed credit/);
  controller.destroy();
});
