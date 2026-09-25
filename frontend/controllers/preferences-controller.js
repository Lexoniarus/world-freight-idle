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
  }
  /** Bind preference actions and refresh visibility-sensitive state. */
  start() {
    this.page.addEventListener(
      "click",
      (event) => {
        const button =
          event.target instanceof Element ? event.target.closest("[data-company-color]") : null;
        if (button) void this.save(button.getAttribute("data-company-color"));
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
    const task = this.pending.start();
    try {
      const result = await this.request("/auth/preferences", { signal: task.signal });
      if (!task.isCurrent()) return;
      this.panel.view.companyPalette = result.palette;
      this.publish(result.company_color);
    } catch (error) {
      if (task.isCurrent() && error.name !== "AbortError") this.notify(error.message);
    }
  }
  /** Persist a curated selection through the account API.
   * @param {string} color
   */
  async save(color) {
    if (this.saving) return;
    this.saving = true;
    const task = this.pending.start();
    try {
      const result = await this.request("/auth/preferences", {
        method: "PUT",
        body: JSON.stringify({ company_color: color }),
        signal: task.signal,
      });
      if (task.isCurrent()) this.publish(result.company_color);
    } catch (error) {
      if (task.isCurrent() && error.name !== "AbortError") this.notify(error.message);
    } finally {
      this.saving = false;
    }
  }
  /** Publish one confirmed color to all presentation owners.
   * @param {string} color
   */
  publish(color) {
    this.panel.view.user.company_color = color;
    document.documentElement.style.setProperty("--company-color", color);
    this.map?.setCompanyColor(color);
    this.panel.render();
  }
  /** Abort preference requests and owned DOM listeners. */
  destroy() {
    this.pending.cancel();
    this.lifetime.abort();
  }
}
