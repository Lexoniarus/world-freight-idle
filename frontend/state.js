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

  /** Read shared traffic while retaining the last valid map snapshot on failure.
   * @returns {Promise<{transports: import('./types.js').PublicTransport[], available: boolean}>}
   */
  async loadTraffic() {
    try {
      const result = await this.request("/map/traffic", {
        signal: this.lifetime.signal,
      });
      return { transports: result.transports, available: true };
    } catch (error) {
      if (error.name === "AbortError") throw error;
      console.warn("Shared traffic unavailable:", error.message);
      return {
        transports: this.data?.traffic ?? [],
        available: false,
      };
    }
  }

  /** Fetch the lightweight game snapshot without loading the market. */
  async loadSnapshot() {
    const started = Date.now() / 1000;
    const [dashboard, fleet, traffic] = await Promise.all([
      this.request("/dashboard", { signal: this.lifetime.signal }),
      this.request("/fleet", { signal: this.lifetime.signal }),
      this.loadTraffic(),
    ]);
    this.offset = dashboard.server_time - (started + Date.now() / 1000) / 2;
    if (this.disposed) return this.data;
    const previous = this.data;
    this.data = {
      ...dashboard,
      vehicles: fleet.vehicles,
      contracts: this.data?.contracts ?? [],
      available_contracts: this.data?.contracts?.length ?? 0,
      traffic: traffic.transports,
      trafficAvailable: traffic.available,
    };
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { previous, current: this.data },
      }),
    );
    return this.data;
  }

  /** Replace only the lazy market slice.
   * @param {import('./types.js').Contract[]} contracts
   */
  replaceContracts(contracts) {
    if (this.disposed || !this.data) return;
    const previous = this.data;
    this.data = {
      ...this.data,
      contracts,
      available_contracts: contracts.length,
    };
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { previous, current: this.data },
      }),
    );
  }

  /** Abort reads and prevent late snapshots from publishing. */
  destroy() {
    this.disposed = true;
    this.lifetime.abort();
  }

  /** Require a read started after any pre-mutation request finishes. */
  async afterMutation() {
    await this.pending?.catch(() => {});
    return this.refresh();
  }
}

/** Cancel and invalidate selection-specific async work. */
export class LatestRequest {
  cancel() {
    this.controller?.abort();
    this.version++;
  }

  constructor() {
    this.version = 0;
  }

  start() {
    this.controller?.abort();
    this.controller = new AbortController();
    const version = ++this.version;
    return {
      signal: this.controller.signal,
      isCurrent: () => this.version === version,
    };
  }
}
