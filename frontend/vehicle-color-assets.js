import { colorizeVehicleSvg, normalizeVehicleColor } from "./map/vehicle-assets.js";
import { getVehicleAssets } from "./vehicle-assets.js";

/** Own shared SVG sources and reference-counted colored object URLs. */
export class VehicleColorAssets {
  /** @param {(path: string) => Promise<string>} load */
  constructor(load) {
    this.load = load;
    this.sources = new Map();
    this.variants = new Map();
    this.disposed = false;
  }
  /** Read a registered local role through the shared source cache.
   * @param {string} model
   * @param {string} role
   * @param {string} color
   */
  async source(model, role, color) {
    const path = getVehicleAssets(model)?.[role];
    if (!path) throw new Error("Fahrzeugasset nicht verfügbar.");
    if (!this.sources.has(path)) {
      const pending = this.load(path).catch((error) => {
        this.sources.delete(path);
        throw error;
      });
      this.sources.set(path, pending);
    }
    return colorizeVehicleSvg(await this.sources.get(path), color);
  }
  /** @param {string} model @param {string} role @param {string} color */
  key(model, role, color) {
    const path = getVehicleAssets(model)?.[role] ?? model;
    return `${path}:${role}:${normalizeVehicleColor(color)}`;
  }
  /** @param {string} model @param {string} role @param {string} color */
  peek(model, role, color) {
    return this.variants.get(this.key(model, role, color))?.url;
  }
  /** Acquire an image lease; disposal during loading cannot retain a URL.
   * @param {string} model
   * @param {string} role
   * @param {string} color
   */
  async acquire(model, role, color) {
    if (this.disposed) throw new Error("Asset registry disposed");
    const key = this.key(model, role, color);
    let entry = this.variants.get(key);
    if (!entry) {
      entry = { users: 0, url: null, pending: null };
      entry.pending = this.source(model, role, color).then((svg) => {
        if (this.disposed) throw new Error("Asset registry disposed");
        entry.url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
        return entry.url;
      });
      this.variants.set(key, entry);
    }
    entry.users++;
    let released = false;
    const release = () => {
      if (released) return;
      released = true;
      if (--entry.users === 0) {
        if (entry.url) URL.revokeObjectURL(entry.url);
        this.variants.delete(key);
      }
    };
    try {
      return { url: await entry.pending, release };
    } catch (error) {
      release();
      throw error;
    }
  }
  /** Release all owned URLs and invalidate in-flight source loads. */
  destroy() {
    this.disposed = true;
    for (const entry of this.variants.values()) if (entry.url) URL.revokeObjectURL(entry.url);
    this.variants.clear();
    this.sources.clear();
  }
}
