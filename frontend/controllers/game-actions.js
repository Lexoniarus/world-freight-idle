import { LatestRequest } from "../state.js";
import { requiredElement } from "../ui/dom.js";

/** Execute game use cases; views only emit action names and resource IDs. */
export class GameActions {
  /** @param {{request: import('../types.js').RequestJson, state: import("../state.js").GameState, panel: import("./panel-controller.js").PanelController, map: import("../map/world-map.js").WorldMap | null, contractMarket: import("./contract-market-controller.js").ContractMarketController, notify: import('../types.js').Notify, navigate: import('../types.js').Navigate, refresh: () => Promise<void>, logout: () => Promise<void>}} dependencies */
  constructor({ request, state, panel, map, contractMarket, notify, navigate, refresh, logout }) {
    this.request = request;
    this.state = state;
    this.panel = panel;
    this.map = map;
    this.contractMarket = contractMarket;
    this.notify = notify;
    this.navigate = navigate;
    this.refresh = refresh;
    this.logout = logout;
    this.quoteRequest = new LatestRequest();
    this.disposed = false;
  }
  /** Route a UI action to a single-purpose handler.
   * @param {string} action
   */
  handle(action, id = "") {
    const actions = {
      close: () => this.navigate("/"),
      "focus-fleet": () => this.map?.focusFleet(),
      "focus-quote": () =>
        this.panel.view.quote && this.map?.focusRoute(this.panel.view.quote.route_geojson),
      "focus-trip": () => this.focusTransport(id),
      "retry-panel": () => this.panel.loadDetails(),
      retry: () => this.refresh(),
      quote: () => this.calculateQuote(),
      buy: () => this.runMutation(() => this.purchaseVehicle(id)),
      dispatch: () => this.runMutation(() => this.dispatchTransport(), false),
      "refresh-market": () => this.runMutation(() => this.refreshMarket()),
      logout: () => this.runMutation(() => this.logout(), false),
    };
    return actions[action]?.();
  }
  /** Show the route for an active transport if it still exists.
   * @param {string} id
   */
  focusTransport(id) {
    const trip = this.state.data?.transports.find((item) => item.id === id);
    if (trip) this.map?.focusRoute(trip.route_geojson);
  }
  /** Cancel the old selection's quote without blocking the new selection. */
  cancelQuote() {
    this.quoteRequest.cancel();
    this.panel.view.quoting = false;
  }
  /** Select a vehicle and discard economics belonging to its predecessor.
   * @param {string} vehicleId
   */
  selectVehicle(vehicleId) {
    this.cancelQuote();
    this.panel.view.selectedVehicle = vehicleId;
    this.panel.view.quote = null;
    this.map?.setPreview(null);
    this.panel.render();
  }
  /** Request a quote and publish it only for the current selection. */
  async calculateQuote() {
    if (this.disposed || this.panel.view.busy) return;
    const contractId = this.panel.view.url.pathname.split("/").at(-1);
    const vehicleId = this.panel.view.selectedVehicle || null;
    const request = this.quoteRequest.start();
    this.panel.view.quoting = true;
    this.panel.render();
    try {
      const quote = await this.request("/contracts/" + contractId + "/quote", {
        method: "POST",
        signal: request.signal,
        body: JSON.stringify({ vehicle_id: vehicleId }),
      });
      if (!request.isCurrent() || vehicleId !== (this.panel.view.selectedVehicle || null)) return;
      this.panel.view.quote = quote;
      this.map?.setPreview(quote);
      this.map?.focusRoute(quote.route_geojson);
    } catch (error) {
      if (request.isCurrent() && error.name !== "AbortError") this.notify(error.message);
    } finally {
      if (request.isCurrent()) {
        this.panel.view.quoting = false;
        this.panel.render();
      }
    }
  }
  /** Serialize writes and reconcile even if a response was lost.
   * @param {() => Promise<void>} operation
   * @param {boolean} [reconcile]
   */
  async runMutation(operation, reconcile = true) {
    if (this.disposed || this.panel.view.busy) return;
    this.panel.view.mutating = true;
    this.panel.render();
    try {
      await operation();
      if (reconcile && !this.disposed) await this.state.afterMutation();
    } catch (error) {
      if (!this.disposed && error.name !== "AbortError") this.notify(error.message);
      if (!this.disposed) {
        try {
          await this.state.afterMutation();
        } catch (refreshError) {
          if (!this.disposed && refreshError.name !== "AbortError")
            this.notify("Spielstand konnte nicht aktualisiert werden. Bitte erneut laden.");
        }
      }
    } finally {
      this.panel.view.mutating = false;
      if (!this.disposed) this.panel.render();
    }
  }
  /** Purchase one server-priced vehicle model.
   * @param {string} modelId
   */
  async purchaseVehicle(modelId) {
    await this.request("/fleet/purchase", {
      method: "POST",
      body: JSON.stringify({ model_id: modelId }),
    });
    if (!this.disposed) this.notify("Dein neuer Lkw ist in Berlin Westhafen einsatzbereit.");
  }
  /** Dispatch the selected vehicle and follow the resulting transport. */
  async dispatchTransport() {
    const path = this.panel.view.url.href;
    const contractId = this.panel.view.url.pathname.split("/").at(-1);
    const choice = /** @type {HTMLSelectElement} */ (requiredElement("#vehicle-choice"));
    if (!this.panel.view.quote || this.panel.view.quote.vehicle_id !== choice.value) return;
    const trip = await this.request("/contracts/" + contractId + "/accept", {
      method: "POST",
      body: JSON.stringify({ vehicle_id: choice.value }),
    });
    if (this.disposed) return;
    this.notify("Transport gestartet. Gute Fahrt!");
    await this.state.afterMutation();
    if (!this.disposed && path === this.panel.view.url.href) {
      this.navigate("/transports/" + trip.id);
      this.map?.focusRoute(trip.route_geojson);
    }
  }
  /** Replace the player's available contract market. */
  async refreshMarket() {
    await this.contractMarket.forceRefresh();
    if (!this.disposed) this.notify("Neue Aufträge sind verfügbar.");
  }
  /** Invalidate pending quotes and suppress late action results. */
  destroy() {
    this.disposed = true;
    this.cancelQuote();
  }
}
