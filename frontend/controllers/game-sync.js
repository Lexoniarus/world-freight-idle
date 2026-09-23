import { requiredElement, html } from "../ui/dom.js";
import { energyDisplay } from "../ui/vehicle-energy.js";
import { money } from "../format.js";
import { progressDisplay } from "../views/transports.js";

/** Synchronize global game state with the HUD, panels and map. */
export class GameSync {
  /** @param {{state: import("../state.js").GameState, panel: import("./panel-controller.js").PanelController, map: import("../map/world-map.js").WorldMap | null, notify: import("../types.js").Notify}} dependencies */
  constructor({ state, panel, map, notify }) {
    this.state = state;
    this.panel = panel;
    this.map = map;
    this.notify = notify;
    this.disposed = false;
    this.onChange = (event) => this.publish(event.detail);
  }

  start() {
    this.state.addEventListener("change", this.onChange);
  }

  publish({ previous, current }) {
    if (this.disposed) return;
    this.panel.view.state = current;
    requiredElement("#cash").textContent = money(current.player.cash);
    requiredElement("#reputation").textContent = String(current.player.reputation);
    requiredElement("#fleet-count").textContent = String(current.vehicles.length);
    requiredElement("#connection").textContent = "Spielstand synchronisiert";
    requiredElement("#sync-notice").hidden = true;
    if (previous && current.player.completed > previous.player.completed)
      this.notify(
        `${current.player.completed - previous.player.completed} Lieferung(en) abgeschlossen. Erlöse wurden gutgeschrieben.`,
      );
    if (current.trafficAvailable === false && previous?.trafficAvailable !== false)
      this.notify(
        "Gemeinsamer Live-Verkehr ist momentan nicht erreichbar. Der letzte bekannte Kartenstand bleibt sichtbar.",
        "map",
      );
    if (current.trafficAvailable === true && previous?.trafficAvailable === false)
      this.notify("Gemeinsamer Live-Verkehr ist wieder verbunden.", "map");
    this.map?.update(current);
    if (!this.panel.view.busy) this.panel.render();
  }

  async refreshGameState() {
    if (this.disposed) return;
    try {
      await this.state.refresh();
    } catch (error) {
      if (this.disposed || error.name === "AbortError") return;
      requiredElement("#connection").textContent = "Verbindung unterbrochen";
      const notice = requiredElement("#sync-notice");
      notice.replaceChildren(
        html`<span>Spielstand konnte nicht aktualisiert werden.</span
          ><button data-action="retry">Erneut versuchen</button>`,
      );
      notice.hidden = false;
    }
  }

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

  /** Update only meter values and text, preserving vehicle image nodes. */
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

  destroy() {
    this.disposed = true;
    this.state.removeEventListener("change", this.onChange);
  }
}
