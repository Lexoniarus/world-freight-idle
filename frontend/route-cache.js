/** Own bounded, prioritized downloads of immutable transport geometry. */
export class RouteCache {
  /** @param {import('./types.js').RequestJson} request */
  constructor(request) {
    this.request = request;
    /** @type {Map<string, {route_geojson: import('./types.js').RouteGeometry, route_legs: import('./types.js').RouteLeg[]}>} */
    this.values = new Map();
    /** @type {Map<string, {priority: number, running: boolean, promise: Promise<void>, resolve: () => void, reject: (error: Error) => void}>} */
    this.pending = new Map();
    this.active = 0;
    this.lifetime = new AbortController();
  }

  /** Read cached geometry without creating a request. @param {string} reference */
  get(reference) {
    const value = this.values.get(reference);
    if (value) {
      this.values.delete(reference);
      this.values.set(reference, value);
    }
    return value;
  }

  /** Coalesce downloads; selected routes precede own and public routes.
   * @param {string} reference
   * @param {number} [priority]
   * @returns {Promise<void>}
   */
  load(reference, priority = 1) {
    if (this.lifetime.signal.aborted)
      return Promise.reject(new DOMException("Route cache closed", "AbortError"));
    if (this.get(reference)) return Promise.resolve();
    const pending = this.pending.get(reference);
    if (pending) {
      pending.priority = Math.min(priority, pending.priority);
      return pending.promise;
    }
    let resolve;
    let reject;
    const promise = new Promise((done, fail) => {
      resolve = done;
      reject = fail;
    });
    this.pending.set(reference, { priority, running: false, promise, resolve, reject });
    this.drain();
    return promise;
  }

  /** Start at most four requests while retaining stable priority order. */
  drain() {
    if (this.lifetime.signal.aborted) return;
    const queued = [...this.pending]
      .filter(([, entry]) => !entry.running)
      .sort((a, b) => a[1].priority - b[1].priority);
    for (const [reference, entry] of queued) {
      if (this.active >= 4) break;
      this.active++;
      entry.running = true;
      void this.download(reference)
        .then(entry.resolve, entry.reject)
        .finally(() => {
          this.pending.delete(reference);
          this.active--;
          this.drain();
        });
    }
  }

  /** Fetch through the shared API boundary and retain a single geometry.
   * @param {string} reference
   */
  async download(reference) {
    const payload = await this.request("/map/routes/" + encodeURIComponent(reference), {
      signal: this.lifetime.signal,
    });
    if (this.lifetime.signal.aborted) return;
    this.values.set(reference, {
      route_geojson: { type: "LineString", coordinates: payload.coordinates },
      route_legs: payload.legs.map(({ start_index, end_index, ...leg }) => ({
        ...leg,
        coordinates: payload.coordinates.slice(start_index, end_index),
      })),
    });
    while (this.values.size > 200) this.values.delete(this.values.keys().next().value);
  }

  /** Abort downloads and discard account-bound geometry and queued work. */
  destroy() {
    this.lifetime.abort();
    const error = new DOMException("Route cache closed", "AbortError");
    for (const entry of this.pending.values()) entry.reject(error);
    this.pending.clear();
    this.values.clear();
  }
}
