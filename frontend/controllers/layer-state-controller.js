import { layerPresets, presetFor } from "../layer-presets.js";

/** Account-ID-scoped presentation preferences; temporary focus is not persisted. */
export class LayerStateController {
  constructor({ userId, map, storage = localStorage }) {
    this.map = map;
    this.storage = storage;
    this.key = "world-freight:layers:v2:" + userId;
    this.preset = "world";
    this.overrides = {};
    this.grouping = true;
    try {
      const saved = JSON.parse(storage.getItem(this.key) ?? "{}");
      for (const name of Object.keys(layerPresets)) {
        this.overrides[name] = {};
        for (const layer of Object.keys(layerPresets[name]))
          if (typeof saved.overrides?.[name]?.[layer] === "boolean")
            this.overrides[name][layer] = saved.overrides[name][layer];
      }
      this.grouping = saved.grouping !== false;
    } catch {
      /* Storage may be disabled; preferences still work in memory. */
    }
  }
  effective() {
    return { ...layerPresets[this.preset], ...this.overrides[this.preset] };
  }
  select(url) {
    this.preset = presetFor(url);
    this.apply();
  }
  set(name, visible) {
    this.overrides[this.preset] ??= {};
    this.overrides[this.preset][name] = visible;
    this.persist();
    this.apply();
  }
  reset() {
    delete this.overrides[this.preset];
    this.persist();
    this.apply();
  }
  setGrouping(value) {
    this.grouping = value;
    this.persist();
    this.apply();
  }
  persist() {
    try {
      this.storage.setItem(
        this.key,
        JSON.stringify({ overrides: this.overrides, grouping: this.grouping }),
      );
    } catch {
      /* Private browsing can deny local storage. */
    }
  }
  apply() {
    for (const [name, visible] of Object.entries(this.effective())) {
      this.map?.toggle(name, visible);
      const input = document.querySelector(`[data-layer="${name}"]`);
      if (input instanceof HTMLInputElement) input.checked = visible;
    }
    this.map?.setGrouping(this.grouping);
    const input = document.querySelector("#object-grouping");
    if (input instanceof HTMLInputElement) input.checked = this.grouping;
    this.map?.setPreset(this.preset);
  }
  destroy() {}
}
