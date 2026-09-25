import { LatestRequest } from "../state.js";

/** Own account preference requests and publish one shared company color. */
export class PreferencesController {
  /** @param {{request: import('../types.js').RequestJson, panel: import('./panel-controller.js').PanelController, map: import('../map/world-map.js').WorldMap | null, notify: import('../types.js').Notify, page?: Document}} dependencies */
  constructor({ request, panel, map, notify, page = document }) {
    this.request = request;
    this.panel = panel;
    this.map = map;
    this.notify = notify;
    this.page = page;
    this.pending = new LatestRequest();
    this.lifetime = new AbortController();
    this.saving = false;
    this.confirmed = panel.view.user.company_color;
    this.desired = null;
    this.disposed = false;
  }
  /** Bind preference actions and refresh visibility-sensitive state. */
  start() {
    this.page.addEventListener(
      "click",
      (event) => {
        const button =
          event.target instanceof Element ? event.target.closest("[data-company-color]") : null;
        if (button) void this.save(button.getAttribute("data-company-color"));
        if (event.target instanceof Element && event.target.closest("[data-preference-retry]"))
          void this.refresh();
      },
      { signal: this.lifetime.signal },
    );
    this.page.addEventListener(
      "visibilitychange",
      () => {
        if (!this.page.hidden && !this.saving) void this.refresh();
      },
      { signal: this.lifetime.signal },
    );
    void this.refresh();
  }
  /** Publish only the latest successful preference read. */
  async refresh() {
    if (this.saving || this.disposed) return;
    const task = this.pending.start();
    this.panel.view.preferenceStatus = "loading";
    this.panel.render();
    try {
      const result = await this.request("/auth/preferences", { signal: task.signal });
      if (!task.isCurrent()) return;
      this.panel.view.preferenceStatus = "ready";
      this.panel.view.companyPalette = result.palette;
      this.confirmed = result.company_color;
      this.publish(result.company_color);
    } catch (error) {
      if (task.isCurrent() && error.name !== "AbortError") {
        this.panel.view.preferenceStatus = "error";
        this.panel.render();
      }
    }
  }
  /** Persist a curated selection through the account API.
   * @param {string} color
   */
  async save(color) {
    if (this.disposed || !this.panel.view.companyPalette?.includes(color)) return;
    this.pending.cancel();
    this.desired = color;
    this.panel.view.preferenceSaveError = false;
    this.publish(color);
    if (this.saving) return;
    this.saving = true;
    try {
      while (this.desired !== null && !this.disposed) {
        const requested = this.desired;
        this.desired = null;
        await this.persist(requested);
      }
    } finally {
      this.saving = false;
    }
  }
  /** Persist one serialized selection, without overwriting a newer preview. */
  async persist(color) {
    try {
      const result = await this.request("/auth/preferences", {
        method: "PUT",
        body: JSON.stringify({ company_color: color }),
        signal: this.lifetime.signal,
      });
      if (this.disposed) return;
      this.confirmed = result.company_color;
      if (this.desired === null) this.publish(this.confirmed);
    } catch (error) {
      if (this.disposed || error.name === "AbortError") return;
      if (this.desired === null) {
        this.panel.view.preferenceSaveError = true;
        this.publish(this.confirmed);
        this.notify("Firmenfarbe konnte nicht gespeichert werden.");
      }
    }
  }
  /** Publish the current confirmed or optimistic color to presentation owners.
   * @param {string} color
   */
  publish(color) {
    this.panel.view.user.company_color = color;
    this.page.documentElement.style.setProperty("--company-color", color);
    this.map?.setCompanyColor(color);
    this.panel.render();
  }
  /** Abort preference requests and owned DOM listeners. */
  destroy() {
    this.disposed = true;
    this.desired = null;
    this.pending.cancel();
    this.lifetime.abort();
  }
}
