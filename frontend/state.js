import { RouteCache } from "./route-cache.js";

/** Hold authoritative snapshots and coalesce refreshes independently of UI. */
export class GameState extends EventTarget {
  /** @param {import('./types.js').RequestJson} request */
  constructor(request) {
    super();
    this.request = request;
    /** @type {import('./types.js').GameSnapshot | null} */
    this.data = null;
    this.contractDetail = null;
    this.contractDetailId = "";
    this.marketLoaded = false;
    this.marketStale = true;
    this.offset = 0;
    /** @type {Promise<import('./types.js').GameSnapshot> | null} */
    this.pending = null;
    this.disposed = false;
    this.lifetime = new AbortController();
    this.routes = new RouteCache(request);
    /** @type {Promise<void> | null} */
    this.trafficPending = null;
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
      const result = await this.request("/map/traffic?representation=summary", {
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
    const dashboard = await this.request("/runtime", { signal: this.lifetime.signal });
    this.offset = dashboard.server_time - (started + Date.now() / 1000) / 2;
    if (this.disposed) return this.data;
    const previous = this.data;
    const fleetKey = (vehicles) =>
      vehicles.map((v) => [v.id, v.status, v.hub_id, v.location?.city_uid]);
    if (
      !previous ||
      JSON.stringify(fleetKey(previous.vehicles)) !== JSON.stringify(fleetKey(dashboard.vehicles))
    )
      this.marketStale = true;
    this.data = {
      ...dashboard,
      transports: dashboard.transports.map((trip) => this.withGeometry(trip)),
      contracts: this.data?.contracts ?? [],
      vehicle_coverage: this.data?.vehicle_coverage ?? [],
      available_contracts: this.marketLoaded ? this.data?.contracts?.length : undefined,
      traffic: this.data?.traffic ?? [],
      trafficAvailable: this.data?.trafficAvailable,
    };
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { previous, current: this.data },
      }),
    );
    this.loadRoutes();
    void this.refreshTraffic();
    return this.data;
  }

  /** Join a summary with already downloaded immutable geometry. */
  withGeometry(trip) {
    return {
      ...trip,
      ...(this.routes.get(trip.route_ref) ?? {
        route_geojson: trip.route_geojson ?? { type: "LineString", coordinates: [] },
        route_legs: trip.route_legs ?? [],
      }),
    };
  }

  /** Update public traffic independently of the playable owner state. */
  refreshTraffic() {
    if (this.trafficPending) return this.trafficPending;
    this.trafficPending = this.loadTraffic()
      .then((traffic) => {
        if (this.disposed || !this.data) return;
        const previous = this.data;
        this.data = {
          ...previous,
          traffic: traffic.transports.map((trip) => this.withGeometry(trip)),
          trafficAvailable: traffic.available,
        };
        this.dispatchEvent(
          new CustomEvent("change", {
            detail: { previous, current: this.data, mapOnly: true },
          }),
        );
        this.loadRoutes();
      })
      .catch((error) => {
        if (error.name !== "AbortError") console.warn("Traffic refresh failed:", error.message);
      })
      .finally(() => {
        this.trafficPending = null;
      });
    return this.trafficPending;
  }

  /** Schedule missing geometry without holding the runtime snapshot open. */
  loadRoutes() {
    const own = this.data?.transports ?? [];
    const visible = this.data?.traffic ?? [];
    /** @type {Map<string, number>} */
    const references = new Map();
    for (const trip of visible) if (trip.route_ref) references.set(trip.route_ref, 1);
    for (const trip of own) if (trip.route_ref) references.set(trip.route_ref, 0);
    for (const [reference, priority] of [...references].sort((a, b) => a[1] - b[1])) {
      if (!reference || this.routes.get(reference)) continue;
      void this.routes
        .load(reference, priority)
        .then(() => {
          this.publishGeometry();
        })
        .catch((error) => {
          if (error.name !== "AbortError") console.warn("Route unavailable:", error.message);
        });
    }
  }

  /** Publish map-only changes; polling never redownloads unchanged routes. */
  publishGeometry() {
    if (this.disposed || !this.data) return;
    const previous = this.data;
    this.data = {
      ...previous,
      transports: previous.transports.map((trip) => this.withGeometry(trip)),
      traffic: (previous.traffic ?? []).map((trip) => this.withGeometry(trip)),
    };
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { previous, current: this.data, mapOnly: true },
      }),
    );
  }

  /** Prioritize a user-selected transport before other pending map work.
   * @param {string} id
   */
  async loadTransportRoute(id) {
    const trip = this.data?.transports.find((item) => item.id === id);
    if (trip?.route_ref) {
      await this.routes.load(trip.route_ref, -1);
      this.publishGeometry();
    }
    return this.data?.transports.find((item) => item.id === id);
  }

  /** Replace only the lazy market slice.
   * @param {import('./types.js').Contract[]} contracts
   */
  replaceContracts(contracts, preparation = null, coverage = []) {
    if (this.disposed || !this.data) return;
    const previous = this.data;
    this.marketLoaded = true;
    this.marketStale = false;
    this.data = {
      ...this.data,
      contracts,
      available_contracts: contracts.length,
      market_preparation: preparation,
      vehicle_coverage: coverage,
    };
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { previous, current: this.data },
      }),
    );
  }

  /** Publish one selected offer without destroying the full market list. */
  replaceContractDetail(contract, id = contract?.id ?? "") {
    this.contractDetail = contract;
    this.contractDetailId = id;
    if (this.data)
      this.dispatchEvent(
        new CustomEvent("change", { detail: { previous: this.data, current: this.data } }),
      );
  }

  /** Abort reads and prevent late snapshots from publishing. */
  destroy() {
    this.disposed = true;
    this.lifetime.abort();
    this.routes.destroy();
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
