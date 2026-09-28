/** Keep game controls independent of loading and constructing the renderer. */
export class DeferredMap extends EventTarget {
  /** @param {{create: () => Promise<import('../types.js').GameMap | null>, notify: import('../types.js').Notify, frame?: typeof requestAnimationFrame, cancelFrame?: typeof cancelAnimationFrame}} dependencies */
  constructor({
    create,
    notify,
    frame = globalThis.requestAnimationFrame.bind(globalThis),
    cancelFrame = globalThis.cancelAnimationFrame.bind(globalThis),
  }) {
    super();
    this.create = create;
    this.notify = notify;
    this.frame = frame;
    this.cancelFrame = cancelFrame;
    /** @type {import('../types.js').GameMap | null} */
    this.renderer = null;
    /** @type {Map<string, (map: import('../types.js').GameMap) => void>} */
    this.pending = new Map();
    this.started = false;
    this.disposed = false;
    this.frameId = 0;
    this.loaded = () => this.dispatchEvent(new Event("ready"));
  }

  /** @returns {boolean} */
  get ready() {
    return this.renderer?.ready ?? false;
  }

  /** Start only after the first game state has had an opportunity to paint.
   * @returns {void}
   */
  start() {
    if (this.started || this.disposed) return;
    this.started = true;
    this.frameId = this.frame(() => {
      this.frameId = this.frame(() => {
        this.frameId = 0;
        void this.load();
      });
    });
  }

  /** Own asynchronous renderer creation and reject late completion.
   * @returns {Promise<void>}
   */
  async load() {
    try {
      const renderer = await this.create();
      if (this.disposed) {
        renderer?.destroy();
        return;
      }
      this.renderer = renderer;
      if (!renderer) return;
      renderer.addEventListener("ready", this.loaded);
      for (const apply of this.pending.values()) apply(renderer);
      this.pending.clear();
      if (renderer.ready) this.loaded();
    } catch {
      if (!this.disposed)
        this.notify(
          "Die Karte konnte nicht geladen werden. Flotte und Aufträge bleiben bedienbar.",
          "map",
        );
    }
  }

  /** Coalesce retained presentation state while the renderer is loading.
   * @param {string} key
   * @param {(map: import('../types.js').GameMap) => void} effect
   * @returns {void}
   */
  apply(key, effect) {
    if (this.disposed) return;
    if (this.renderer) effect(this.renderer);
    else this.pending.set(key, effect);
  }

  /** @param {import('../types.js').MapState} state
   * @returns {void}
   */
  update(state) {
    this.apply("state", (map) => map.update(state));
    this.start();
  }

  /** @param {string} color
   * @returns {void}
   */
  setCompanyColor(color) {
    this.apply("color", (map) => map.setCompanyColor(color));
  }

  /** @param {boolean} value
   * @returns {void}
   */
  setGrouping(value) {
    this.apply("grouping", (map) => map.setGrouping(value));
  }

  /** @param {string} value
   * @returns {void}
   */
  setPreset(value) {
    this.apply("preset", (map) => map.setPreset(value));
  }

  /** @param {import('../types.js').Quote | null} quote
   * @returns {void}
   */
  setPreview(quote) {
    this.apply("preview", (map) => map.setPreview(quote));
  }

  /** @param {string} id @param {import('../types.js').Contract | null} [contract]
   * @returns {void}
   */
  select(id, contract = null) {
    this.apply("selection", (map) => map.select(id, contract));
  }

  /** @param {string} name @param {boolean} visible
   * @returns {void}
   */
  toggle(name, visible) {
    this.apply("layer:" + name, (map) => map.toggle(name, visible));
  }

  /** @param {number[][]} points
   * @returns {void}
   */
  fitCoordinates(points) {
    this.apply("focus", (map) => map.fitCoordinates(points));
  }

  /** @param {import('../types.js').RouteGeometry} route
   * @returns {void}
   */
  focusRoute(route) {
    this.apply("focus", (map) => map.focusRoute(route));
  }

  /** Focus the most recent fleet projection when available.
   * @returns {void}
   */
  focusFleet() {
    this.apply("focus", (map) => map.focusFleet());
  }

  /** Release scheduled creation, subscriptions and the eventual renderer.
   * @returns {void}
   */
  destroy() {
    if (this.disposed) return;
    this.disposed = true;
    this.cancelFrame(this.frameId);
    this.pending.clear();
    this.renderer?.removeEventListener("ready", this.loaded);
    this.renderer?.destroy();
  }
}
