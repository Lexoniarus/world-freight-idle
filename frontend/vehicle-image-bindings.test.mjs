import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { VehicleImageController } from "./vehicle-image-bindings.js";
import { renderVehicleImage } from "./ui/vehicle-image.js";
import { matchVehicleImages } from "./ui/preserve-vehicle-images.js";
import { model, source, TestColorAssets, tick } from "./test-support/vehicle-color-fixtures.mjs";

function coloredImage(color = "#e45756") {
  const image = document.createElement("img");
  Object.assign(image.dataset, {
    vehicleModel: model,
    vehicleRole: "front",
    vehicleColor: color,
  });
  return image;
}

test("late asset load cannot repaint a disposed binding", async () => {
  let finish;
  const service = new TestColorAssets((path) =>
    path.endsWith("-paint.svg")
      ? Promise.resolve(source)
      : new Promise((resolve) => (finish = resolve)),
  );
  const controller = new VehicleImageController(service);
  const image = coloredImage();
  controller.update([image]);
  controller.update([]);
  finish(source);
  await tick();
  assert.equal(image.getAttribute("src"), null);
  assert.equal(service.variants.size, 0);
  controller.destroy();
  service.destroy();
});

test("image loading waits until the image is visible", async () => {
  let reads = 0;
  let callback;
  const observed = new Set();
  const service = new TestColorAssets(async () => {
    reads++;
    return source;
  });
  const controller = new VehicleImageController(service, (notify) => {
    callback = notify;
    return {
      observe: (image) => observed.add(image),
      unobserve: (image) => observed.delete(image),
      disconnect() {},
    };
  });
  const images = [coloredImage(), coloredImage(), coloredImage()];
  controller.update(images);
  callback([{ target: images[0], isIntersecting: false }]);
  assert.equal(reads, 0);
  callback([{ target: images[0], isIntersecting: true }]);
  await tick();
  assert.equal(reads, 2);
  assert.match(images[0].src, /^blob:/);
  assert.equal(images[1].getAttribute("src"), null);
  assert.equal(observed.size, 2);
  controller.destroy();
  service.destroy();
});

test("removing an observed image prevents its later visibility load", () => {
  let reads = 0;
  let callback;
  const observed = new Set();
  const service = new TestColorAssets(async () => {
    reads++;
    return source;
  });
  const controller = new VehicleImageController(service, (notify) => {
    callback = notify;
    return {
      observe: (image) => observed.add(image),
      unobserve: (image) => observed.delete(image),
      disconnect() {},
    };
  });
  const image = coloredImage();
  controller.update([image]);
  controller.update([]);

  callback([{ target: image, isIntersecting: true }]);

  assert.equal(reads, 0);
  assert.equal(observed.size, 0);
  controller.destroy();
  service.destroy();
});

test("destroy disconnects observation and releases image leases", async () => {
  let disconnected = false;
  const service = new TestColorAssets(async () => source);
  const controller = new VehicleImageController(service, () => ({
    observe() {},
    unobserve() {},
    disconnect: () => (disconnected = true),
  }));
  const image = coloredImage();
  controller.update([image]);
  controller.load(image);
  await tick();

  controller.destroy();
  controller.update([coloredImage()]);

  assert.equal(disconnected, true);
  assert.equal(controller.bindings.size, 0);
  assert.equal(service.variants.size, 0);
  service.destroy();
});

test("panel refresh preserves matching colored image nodes", async () => {
  const service = new TestColorAssets(async () => source);
  const controller = new VehicleImageController(service);
  const vehicle = { model_id: model, name: "Truck", capacity_tons: 24 };
  const current = document.createElement("div");
  current.append(renderVehicleImage(vehicle));
  controller.prepare(current, "#e45756");
  controller.update(current.querySelectorAll("img[data-vehicle-model]"));
  await tick();
  const next = renderVehicleImage(vehicle);
  controller.prepare(next, "#e45756");
  assert.equal(matchVehicleImages(current, next).length, 1);
  const changed = renderVehicleImage(vehicle);
  controller.prepare(changed, "#4c78a8");
  assert.equal(matchVehicleImages(current, changed).length, 0);
  controller.destroy();
  service.destroy();
});

test("replacement acquires its lease before the displayed URL is revoked", async () => {
  const assets = new TestColorAssets(async () => source);
  const controller = new VehicleImageController(assets);
  const root = document.createElement("div");
  root.append(renderVehicleImage({ model_id: model, name: "Truck" }));
  controller.prepare(root, "#e45756");
  controller.update(root.querySelectorAll("img"));
  await tick();
  const oldUrl = root.querySelector("img").src;
  const next = document.createElement("div");
  next.append(renderVehicleImage({ model_id: model, name: "Truck" }));
  controller.prepare(next, "#e45756");
  controller.update(next.querySelectorAll("img"));
  assert.equal(assets.peek(model, "front", "#e45756"), oldUrl);
  assert.equal((await fetch(oldUrl)).status, 200);
  await tick();
  assert.equal(next.querySelector("img").src, oldUrl);
  controller.destroy();
  assets.destroy();
});

test("late old-color result cannot overwrite the current selection", async () => {
  let finish;
  const assets = new TestColorAssets((path) =>
    path.endsWith("-paint.svg")
      ? Promise.resolve(source)
      : new Promise((resolve) => (finish = resolve)),
  );
  const controller = new VehicleImageController(assets);
  const image = coloredImage();
  controller.update([image]);
  image.dataset.vehicleColor = "#4c78a8";
  controller.update([image]);
  finish(source);
  await tick();
  assert.match(await (await fetch(image.src)).text(), /--vehicle-color:#4c78a8/);
  assert.equal(assets.variants.size, 1);
  controller.destroy();
  assets.destroy();
});
