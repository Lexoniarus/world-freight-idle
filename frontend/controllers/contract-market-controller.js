import { LatestRequest } from "../state.js";

/** Own city-market reads independently of map navigation. */
export class ContractMarketController {
  /** @param {{state: import("../state.js").GameState, request: import("../types.js").RequestJson, notify: import("../types.js").Notify, currentUrl: () => URL}} dependencies */
  constructor({ state, request, notify, currentUrl }) {
    this.state = state;
    this.request = request;
    this.notify = notify;
    this.currentUrl = currentUrl;
    this.pending = new LatestRequest();
    this.detailPending = new LatestRequest();
    this.started = false;
    this.disposed = false;
    this.ordersVisible = () => false;
  }

  /** Register owned listeners for this controller.
   * @returns {void}
   */
  start() {
    this.started = true;
  }

  /** Load offers required by the current route or visible map layer.
   * @returns {Promise<void>}
   */
  async refresh() {
    if (!this.started || this.disposed || !this.state.data) return;
    const path = this.currentUrl().pathname;
    const detailId = path.startsWith("/contracts/") ? path.split("/")[2] : "";
    const tasks = [];
    if (path === "/contracts" || this.ordersVisible()) tasks.push(this.loadList(false));
    else this.pending.cancel();
    if (detailId) tasks.push(this.loadDetail(detailId));
    else this.detailPending.cancel();
    await Promise.all(tasks);
  }

  /** Replace the market for an explicit user refresh.
   * @returns {Promise<void>}
   */
  async forceRefresh() {
    if (!this.started || this.disposed || !this.state.data) return;
    if (this.currentUrl().pathname !== "/contracts") return;
    await this.loadList(true);
  }

  /** Load and publish the current shared offer pool.
   * @param {boolean} force
   * @returns {Promise<void>}
   */
  async loadList(force) {
    const request = this.pending.start();
    const path = force ? "/contracts/refresh" : "/contracts";
    try {
      const result = await this.request(path, {
        method: force ? "POST" : "GET",
        signal: request.signal,
      });
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
    const request = this.detailPending.start();
    try {
      const contract = await this.request("/contracts/" + encodeURIComponent(id), {
        signal: request.signal,
      });
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
