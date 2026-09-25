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
    this.started = false;
    this.disposed = false;
  }

  start() {
    this.started = true;
  }

  async refresh() {
    if (!this.started || this.disposed || !this.state.data) return;
    const path = this.currentUrl().pathname;
    if (path === "/contracts") {
      await this.loadList(false);
      return;
    }
    if (path.startsWith("/contracts/")) {
      await this.loadDetail(path.split("/")[2]);
      return;
    }
    this.pending.cancel();
    if (this.state.data.contracts.length) this.state.replaceContracts([]);
  }

  async forceRefresh() {
    if (!this.started || this.disposed || !this.state.data) return;
    if (this.currentUrl().pathname !== "/contracts") return;
    await this.loadList(true);
  }

  async loadList(force) {
    const request = this.pending.start();
    const path = force ? "/contracts/refresh" : "/contracts";
    try {
      const result = await this.request(path, {
        method: force ? "POST" : "GET",
        signal: request.signal,
      });
      if (request.isCurrent()) {
        this.state.replaceContracts(result.contracts);
      }
    } catch (error) {
      if (request.isCurrent() && error.name !== "AbortError") {
        this.notify(error.message);
      }
    }
  }

  async loadDetail(id) {
    const request = this.pending.start();
    try {
      const contract = await this.request("/contracts/" + encodeURIComponent(id), {
        signal: request.signal,
      });
      if (request.isCurrent()) this.state.replaceContracts([contract]);
    } catch (error) {
      if (request.isCurrent() && error.name !== "AbortError") {
        if (error.status === 404) this.state.replaceContracts([]);
        this.notify(error.message);
      }
    }
  }

  destroy() {
    this.disposed = true;
    this.pending.cancel();
  }
}
