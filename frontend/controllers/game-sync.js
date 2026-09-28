import { marketMapState } from "../market-context.js";
import { requiredElement, html } from "../ui/dom.js";
import { energyDisplay } from "../ui/vehicle-energy.js";
import { money } from "../format.js";
import { progressDisplay } from "../views/transports.js";

/** Synchronize global game state with the HUD, panels and map. */
export class GameSync {
  /** @param {{state: import("../state.js").GameState, panel: import("./panel-controller.js").PanelController, map: import("../types.js").GameMap | null, notify: import("../types.js").Notify}} dependencies */
  constructor({ state, panel, map, notify }) {
    this.state = state;
    this.panel = panel;
    this.map = map;
    this.notify = notify;
    this.disposed = false;
    this.panelRevision = "";
    this.onChange = (event) => this.publish(event.detail);
  }

  /** Register owned listeners for this controller.
   * @returns {void}
   */
  start() {
    this.state.addEventListener("change", this.onChange);
  }

  /** Publish a state revision to HUD, panel and map.
   * @param {{previous: import('../types.js').GameSnapshot | null, current: import('../types.js').GameSnapshot, mapOnly?: boolean}} change
   * @returns {void}
   */
  publish({ previous, current, mapOnly = false }) {
    if (this.disposed) return;
    this.panel.view.state = current;
    if (current.trafficAvailable === false && previous?.trafficAvailable !== false)
      this.notify(
        "Gemeinsamer Live-Verkehr ist momentan nicht erreichbar. Der letzte bekannte Kartenstand bleibt sichtbar.",
        "map",
      );
    if (current.trafficAvailable === true && previous?.trafficAvailable === false)
      this.notify("Gemeinsamer Live-Verkehr ist wieder verbunden.", "map");
    if (mapOnly) {
      this.updateMap();
      return;
    }
    this.panel.view.detailContract = this.state.contractDetail;
    this.panel.view.detailId = this.state.contractDetailId;
    this.panel.view.marketLoaded = this.state.marketLoaded;
    this.panel.view.marketStale = this.state.marketStale;
    requiredElement("#cash").textContent = money(current.player.cash);
    requiredElement("#reputation").textContent = String(current.player.reputation);
    requiredElement("#fleet-count").textContent = String(current.vehicles.length);
    const fleetStatus = document.querySelector("#fleet-state");
    if (fleetStatus)
      fleetStatus.textContent = `${current.vehicles.filter((v) => v.status === "idle").length} bereit · ${current.vehicles.filter((v) => v.status === "enroute").length} unterwegs`;
    requiredElement("#connection").textContent = "Spielstand synchronisiert";
    requiredElement("#sync-notice").hidden = true;
    if (previous && current.player.completed > previous.player.completed)
      this.notify(
        `${current.player.completed - previous.player.completed} Lieferung(en) abgeschlossen. Erlöse wurden gutgeschrieben.`,
      );
    this.updateMap();
    const path = this.panel.view.url.pathname;
    if (path.startsWith("/contracts/"))
      this.map?.select(path.split("/")[2], this.state.contractDetail);
    const revision = JSON.stringify({
      player: current.player,
      vehicles: current.vehicles.map(({ energy_level: _energy, ...vehicle }) => vehicle),
      transports: current.transports.map(
        ({ route_geojson: _shape, route_legs: _legs, progress: _progress, ...trip }) => trip,
      ),
      contracts: current.contracts,
      preparation: current.market_preparation,
      coverage: current.vehicle_coverage,
      detail: this.state.contractDetail,
      detailId: this.state.contractDetailId,
      marketLoaded: this.state.marketLoaded,
      marketStale: this.state.marketStale,
    });
    if (!this.panel.view.busy && revision !== this.panelRevision) {
      this.panelRevision = revision;
      this.panel.render();
    }
    this.updateProgress();
  }

  /** Project current route eligibility without moving the camera.
   * @returns {void}
   */
  updateMap() {
    if (this.disposed || !this.state.data) return;
    this.map?.update({
      ...marketMapState(this.state.data, this.panel.view.url),
      marketLoaded: this.state.marketLoaded,
    });
  }

  /** Refresh player state and display connection failures.
   * @returns {Promise<void>}
   */
  async refreshGameState() {
    if (this.disposed) return;
    try {
      await this.state.refresh();
    } catch (error) {
      if (this.disposed || error.name === "AbortError") return;
      const unavailable = error.status === 503;
      requiredElement("#connection").textContent = unavailable
        ? "Spielstand derzeit nicht verfügbar"
        : "Verbindung unterbrochen";
      const notice = requiredElement("#sync-notice");
      notice.replaceChildren(
        html`<span
            >${unavailable ? "Der Server konnte deinen Spielstand nicht laden. Bitte erneut versuchen." : "Verbindung zum Server nicht herstellbar. Bitte erneut versuchen."}</span
          ><button data-action="retry">Erneut versuchen</button>`,
      );
      notice.hidden = false;
    }
  }

  /** Update live transport progress from the server clock.
   * @returns {void}
   */
  updateProgress() {
    if (this.disposed || !this.state.data) return;
    this.updateEnergyMeters();
    document.querySelectorAll("[data-phase-trip]").forEach((element) => {
      const trip = this.state.data.transports.find(
        (item) => item.id === element.getAttribute("data-phase-trip"),
      );
      if (trip) element.textContent = progressDisplay(trip, this.state.now()).phase;
    });
    document.querySelectorAll("[data-trip]").forEach((element) => {
      const trip = this.state.data.transports.find(
        (item) => item.id === element.getAttribute("data-trip"),
      );
      if (!trip) return;
      const { percent, eta } = progressDisplay(trip, this.state.now());
      requiredElement(".eta", element).textContent = eta;
      requiredElement(".percentage", element).textContent = percent + "%";
      element.querySelector("progress").value = percent;
    });
  }

  /** Update only meter values and text, preserving vehicle image nodes.
   * @returns {void}
   */
  updateEnergyMeters() {
    document.querySelectorAll("[data-energy-vehicle]").forEach((element) => {
      const vehicle = this.state.data.vehicles.find(
        (item) => item.id === element.getAttribute("data-energy-vehicle"),
      );
      if (!vehicle) return;
      const trip = this.state.data.transports.find((item) => item.vehicle_id === vehicle.id);
      const display = energyDisplay(vehicle, trip, this.state.now());
      element.querySelector("meter").value = display.level;
      requiredElement(".energy-value", element).textContent = display.text;
    });
  }

  /** Release owned resources and reject late updates.
   * @returns {void}
   */
  destroy() {
    this.disposed = true;
    this.state.removeEventListener("change", this.onChange);
  }
}
