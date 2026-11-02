import { marketVehicle } from "../market-context.js";
import { LatestRequest } from "../latest-request.js";

/** Own city-market reads independently of map navigation. */
export class ContractMarketController {
  /** @param {{state: import("../game-state.js").GameState, api: import("../api.js").GameApiClient, notify: import("../types.js").Notify, currentUrl: () => URL}} dependencies */
  constructor({ state, api, notify, currentUrl }) {
    this.state = state;
    this.api = api;
    this.notify = notify;
    this.currentUrl = currentUrl;
    this.pending = new LatestRequest();
    this.detailPending = new LatestRequest();
    this.started = false;
    this.disposed = false;
    /** @type {{key: string, promise: Promise<boolean>} | null} */
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
    const vehicle =
      path === "/contracts" ? marketVehicle(this.state.data, this.currentUrl()) : null;
    if (vehicle) tasks.push(this.loadList(false, vehicle.id));
    else if (this.listRead) {
      this.pending.cancel();
      this.listRead = null;
    }
    if (detailId) tasks.push(this.loadDetail(detailId));
    else if (this.detailRead) {
      this.detailPending.cancel();
      this.detailRead = null;
    }
    await Promise.all(tasks);
  }

  /** Request preparation and read the preserved market on explicit refresh.
   * @returns {Promise<boolean>}
   */
  async forceRefresh() {
    if (!this.started || this.disposed || !this.state.data) return false;
    const url = this.currentUrl();
    if (url.pathname !== "/contracts") return false;
    const vehicle = marketVehicle(this.state.data, url);
    if (!vehicle) return false;
    return this.loadList(true, vehicle.id);
  }

  /** Load and publish the authoritative selection for the current vehicle.
   * @param {boolean} force
   * @param {string} vehicleId
   * @returns {Promise<boolean>}
   */
  async loadList(force, vehicleId) {
    if (!force && this.listRead?.key === vehicleId) return this.listRead.promise;
    const read = { key: vehicleId, promise: this.readList(force, vehicleId) };
    this.listRead = read;
    try {
      return await read.promise;
    } finally {
      if (this.listRead === read) this.listRead = null;
    }
  }

  /** Execute one list revision; only explicit replacement aborts it.
   * @param {boolean} force
   * @param {string} vehicleId
   * @returns {Promise<boolean>}
   */
  async readList(force, vehicleId) {
    const request = this.pending.start();
    try {
      const result = force
        ? await this.api.requestFreightRefill(vehicleId, request.signal)
        : await this.api.loadFreightOffers(vehicleId, request.signal);
      if (request.isCurrent()) {
        this.state.replaceContracts(result.contracts, result.preparation, result.vehicle_coverage);
        return true;
      }
    } catch (error) {
      if (request.isCurrent() && error.name !== "AbortError") {
        this.notify(error.message);
      }
    }
    return false;
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
