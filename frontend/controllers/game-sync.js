import { requiredElement, html } from "../ui/dom.js";
import { money } from "../format.js";
import { progressDisplay } from "../views/transports.js";

/** Synchronize the server snapshot with the HUD, panels and map. */
export class GameSync {
  /** @param {{state: import("../state.js").GameState, request: import('../types.js').RequestJson, panel: import("./panel-controller.js").PanelController, map: import("../map/world-map.js").WorldMap | null, notify: import('../types.js').Notify}} dependencies */
  constructor({ state, request, panel, map, notify }) {
    this.state = state;
    this.request = request;
    this.panel = panel;
    this.map = map;
    this.notify = notify;
    this.disposed = false;
    this.onChange = (event) => this.publish(event.detail);
  }
  /** Subscribe to authoritative snapshots. */
  start() {
    this.state.addEventListener("change", this.onChange);
  }
  /** Project one completed snapshot into the visible surfaces.
   * @param {{previous: import('../types.js').GameSnapshot | null, current: import('../types.js').GameSnapshot}} snapshot
   */
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
    this.map?.update(current);
    if (!this.panel.view.busy) this.panel.render();
  }
  /** Refresh the authoritative state and present recoverable connection errors. */
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
  /** Load real public-hub coordinates, preserving partial failures. */
  async loadHubs() {
    try {
      const result = await this.request("/map/facilities");
      if (this.disposed) return;
      this.map?.setHubs(result.facilities);
      if (result.unavailable_count > 0)
        this.notify(
          `${result.unavailable_count} Frachtstandorte ohne geprüften Koordinatennachweis werden nicht angezeigt.`,
          "map",
        );
    } catch (error) {
      if (!this.disposed && error.name !== "AbortError")
        this.notify(
          "Frachtstandorte konnten nicht geladen werden. Lade die Seite erneut, um es noch einmal zu versuchen.",
          "map",
        );
    }
  }
  /** Update visible countdowns without replacing controls or settling trips. */
  updateProgress() {
    if (this.disposed || !this.state.data) return;
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
  /** Stop future snapshot delivery. */
  destroy() {
    this.disposed = true;
    this.state.removeEventListener("change", this.onChange);
  }
}
