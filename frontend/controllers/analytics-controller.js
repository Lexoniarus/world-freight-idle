import { LatestRequest } from "../latest-request.js";

/** Load private analytics only while its management view is open. */
export class AnalyticsController {
  /** @param {{request: import('../types.js').RequestJson, panel: import('./panel-controller.js').PanelController}} dependencies */
  constructor({ request, panel }) {
    this.request = request;
    this.panel = panel;
    this.pending = new LatestRequest();
  }
  /** Load the current analytics selection with stale-response protection.
   * @returns {Promise<void>}
   */
  async refresh() {
    const view = this.panel.view;
    const pending = this.pending.start();
    if (view.url.pathname !== "/company") return;
    const params = new URLSearchParams({
      days: view.url.searchParams.get("days") ?? "30",
      scope: view.url.searchParams.get("scope") ?? "company",
    });
    if (view.url.searchParams.has("scope_id"))
      params.set("scope_id", view.url.searchParams.get("scope_id"));
    this.panel.presentation.beginAnalyticsLoad();
    this.panel.render();
    try {
      const result = await this.request("/company/analytics?" + params, { signal: pending.signal });
      if (!pending.isCurrent()) return;
      this.panel.presentation.publishAnalytics(result);
    } catch (error) {
      if (!pending.isCurrent() || error.name === "AbortError") return;
      this.panel.presentation.failAnalyticsLoad();
    } finally {
      if (pending.isCurrent()) {
        this.panel.presentation.finishAnalyticsLoad();
        this.panel.render();
      }
    }
  }
  /** Release owned resources and reject late updates.
   * @returns {void}
   */
  destroy() {
    this.pending.cancel();
  }
}
