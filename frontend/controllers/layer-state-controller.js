import { layerPresets, presetFor } from "../layer-presets.js";

/** Account-ID-scoped presentation preferences; temporary focus is not persisted. */
export class LayerStateController {
  /** @param {{userId: string, map: import('../map/world-map.js').WorldMap | null, storage?: Storage}} dependencies */
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
  /** Resolve current preset visibility with saved overrides.
   * @returns {Record<string, boolean>}
   */
  effective() {
    return { ...layerPresets[this.preset], ...this.overrides[this.preset] };
  }
  /** Apply the layer preset for a navigation intent.
   * @param {URL} url
   * @returns {void}
   */
  select(url) {
    this.preset = presetFor(url);
    this.apply();
  }
  /** Persist and apply one layer visibility choice.
   * @param {string} name
   * @param {boolean} visible
   * @returns {void}
   */
  set(name, visible) {
    this.overrides[this.preset] ??= {};
    this.overrides[this.preset][name] = visible;
    this.persist();
    this.apply();
  }
  /** Clear overrides for the current preset.
   * @returns {void}
   */
  reset() {
    delete this.overrides[this.preset];
    this.persist();
    this.apply();
  }
  /** Persist and apply vehicle grouping preference.
   * @param {boolean} value
   * @returns {void}
   */
  setGrouping(value) {
    this.grouping = value;
    this.persist();
    this.apply();
  }
  /** Store account-local layer preferences.
   * @returns {void}
   */
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
  /** Synchronize layer controls and map presentation.
   * @returns {void}
   */
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
  /** Complete the lifecycle of this resource-free controller.
   * @returns {void}
   */
  destroy() {}
}
