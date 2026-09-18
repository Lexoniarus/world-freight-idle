/** Hold authoritative snapshots and coalesce refreshes independently of UI. */
export class GameState extends EventTarget {
  /** @param {import('./types.js').RequestJson} request */
  constructor(request) {
    super();
    this.request = request;
    /** @type {import('./types.js').GameSnapshot | null} */
    this.data = null;
    this.offset = 0;
    /** @type {Promise<import('./types.js').GameSnapshot> | null} */
    this.pending = null;
    this.disposed = false;
    this.lifetime = new AbortController();
  }

  /** Return server-adjusted epoch seconds. @returns {number} */
  now() {
    return Date.now() / 1000 + this.offset;
  }

  /** Coalesce simultaneous snapshot reads. */
  refresh() {
    if (this.disposed) return Promise.resolve(this.data);
    if (this.pending) return this.pending;
    this.pending = this.loadSnapshot().finally(() => {
      this.pending = null;
    });
    return this.pending;
  }

  /** Fetch a complete snapshot after reconciling arrivals on the server. */
  async loadSnapshot() {
    const started = Date.now() / 1000;
    // Dashboard reconciles arrivals before the dependent fleet and market reads.
    const dashboard = await this.request("/dashboard", { signal: this.lifetime.signal });
    this.offset = dashboard.server_time - (started + Date.now() / 1000) / 2;
    const [fleet, contracts] = await Promise.all([
      this.request("/fleet", { signal: this.lifetime.signal }),
      this.request("/contracts", { signal: this.lifetime.signal }),
    ]);
    if (this.disposed) return this.data;
    const previous = this.data;
    this.data = { ...dashboard, vehicles: fleet.vehicles, contracts: contracts.contracts };
    this.dispatchEvent(new CustomEvent("change", { detail: { previous, current: this.data } }));
    return this.data;
  }

  /** Abort reads and prevent late snapshots from publishing. */
  destroy() {
    this.disposed = true;
    this.lifetime.abort();
  }

  /** Require a read started after any pre-mutation request finishes. */
  async afterMutation() {
    // A pre-action read cannot serve as the post-action refresh.
    await this.pending?.catch(() => {});
    return this.refresh();
  }
}

/** Cancel and invalidate selection-specific async work. */
export class LatestRequest {
  /** Invalidate even a transport that ignores AbortSignal. */
  cancel() {
    this.controller?.abort();
    this.version++;
  }
  constructor() {
    this.version = 0;
  }
  /** Begin the next selection request and invalidate its predecessor. */
  start() {
    this.controller?.abort();
    this.controller = new AbortController();
    const version = ++this.version;
    return { signal: this.controller.signal, isCurrent: () => this.version === version };
  }
}
