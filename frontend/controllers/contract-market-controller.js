import { LatestRequest } from "../state.js";

/** Own city-market reads independently of map navigation. */
export class ContractMarketController {
  /** @param {{state: import("../state.js").GameState, api: import("../api.js").GameApiClient, notify: import("../types.js").Notify, currentUrl: () => URL}} dependencies */
  constructor({ state, api, notify, currentUrl }) {
    this.state = state;
    this.api = api;
    this.notify = notify;
    this.currentUrl = currentUrl;
    this.pending = new LatestRequest();
    this.detailPending = new LatestRequest();
    this.started = false;
    this.disposed = false;
    /** @type {{key: string, promise: Promise<void>} | null} */
    this.listRead = null;
    /** @type {{id: string, promise: Promise<void>} | null} */
    this.detailRead = null;
  }

  /** Register owned listeners for this controller.
   * @returns {void}
   */
  start() {
    this.started = true;
  }

  /** Load offers only for the dedicated freight-market route.
   * @returns {Promise<void>}
   */
  async refresh() {
    if (!this.started || this.disposed || !this.state.data) return;
    const path = this.currentUrl().pathname;
    const detailId = path.startsWith("/contracts/") ? path.split("/")[2] : "";
    const tasks = [];
    if (path === "/contracts") tasks.push(this.loadList(false));
    if (detailId) tasks.push(this.loadDetail(detailId));
    else if (this.detailRead) {
      this.detailPending.cancel();
      this.detailRead = null;
    }
    await Promise.all(tasks);
  }

  /** Request preparation and read the preserved market on explicit refresh.
   * @returns {Promise<void>}
   */
  async forceRefresh() {
    if (!this.started || this.disposed || !this.state.data) return;
    if (this.currentUrl().pathname !== "/contracts") return;
    await this.loadList(true);
  }

  /** Load and publish the authoritative selection for the current vehicle.
   * @param {boolean} force
   * @returns {Promise<void>}
   */
  async loadList(force) {
    const url = this.currentUrl();
    const key = url.pathname === "/contracts" ? (url.searchParams.get("vehicle") ?? "") : "";
    if (!force && this.listRead?.key === key) return this.listRead.promise;
    const read = { key, promise: this.readList(force, key) };
    this.listRead = read;
    try {
      await read.promise;
    } finally {
      if (this.listRead === read) this.listRead = null;
    }
  }

  /** Execute one list revision; only explicit replacement aborts it.
   * @param {boolean} force
   * @param {string} vehicleId
   * @returns {Promise<void>}
   */
  async readList(force, vehicleId) {
    const request = this.pending.start();
    try {
      const result = force
        ? await this.api.requestFreightRefill(vehicleId, request.signal)
        : await this.api.loadFreightOffers(vehicleId, request.signal);
      if (request.isCurrent()) {
        this.state.replaceContracts(result.contracts, result.preparation, result.vehicle_coverage);
      }
    } catch (error) {
      if (request.isCurrent() && error.name !== "AbortError") {
        this.notify(error.message);
      }
    }
  }

  /** Load one selected offer without accepting stale responses.
   * @param {string} id
   * @returns {Promise<void>}
   */
  async loadDetail(id) {
    if (this.detailRead?.id === id) return this.detailRead.promise;
    const read = { id, promise: this.readDetail(id) };
    this.detailRead = read;
    try {
      await read.promise;
    } finally {
      if (this.detailRead === read) this.detailRead = null;
    }
  }

  /** Execute one selected offer request and reject obsolete navigation.
   * @param {string} id
   * @returns {Promise<void>}
   */
  async readDetail(id) {
    const request = this.detailPending.start();
    try {
      const contract = await this.api.loadFreightOffer(id, request.signal);
      if (request.isCurrent()) this.state.replaceContractDetail(contract, id);
    } catch (error) {
      if (request.isCurrent() && error.name !== "AbortError") {
        if (error.status === 404) this.state.replaceContractDetail(null, id);
        this.notify(error.message);
      }
    }
  }

  /** Release owned resources and reject late updates.
   * @returns {void}
   */
  destroy() {
    this.disposed = true;
    this.pending.cancel();
    this.detailPending.cancel();
  }
}
