import { LatestRequest } from "../state.js";

/** Load private analytics only while its management view is open. */
export class AnalyticsController {
  constructor({ request, panel }) {
    this.request = request;
    this.panel = panel;
    this.pending = new LatestRequest();
  }
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
    view.analyticsLoading = true;
    view.analyticsError = false;
    this.panel.render();
    try {
      const result = await this.request("/company/analytics?" + params, { signal: pending.signal });
      if (!pending.isCurrent()) return;
      view.analytics = result;
      if (result.scope.type === "company") view.analyticsChoices = result.breakdowns;
    } catch (error) {
      if (!pending.isCurrent() || error.name === "AbortError") return;
      view.analyticsError = true;
    } finally {
      if (pending.isCurrent()) {
        view.analyticsLoading = false;
        this.panel.render();
      }
    }
  }
  destroy() {
    this.pending.cancel();
  }
}
