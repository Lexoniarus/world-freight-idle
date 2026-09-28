/** URL-backed presentation controls, isolated from game mutations. */
export class ManagementInput {
  /** @param {{page: Document, view: import('../types.js').PanelView, navigate: import('../types.js').Navigate, layers: import('./layer-state-controller.js').LayerStateController, analytics: import('./analytics-controller.js').AnalyticsController, panel: import('./panel-controller.js').PanelController, market: import('./contract-market-controller.js').ContractMarketController}} dependencies */
  constructor({ page, view, navigate, layers, analytics, panel, market }) {
    this.page = page;
    this.view = view;
    this.navigate = navigate;
    this.layers = layers;
    this.analytics = analytics;
    this.panel = panel;
    this.market = market;
    this.lifetime = new AbortController();
  }
  /** Register owned listeners for this controller.
   * @returns {void}
   */
  start() {
    const options = { signal: this.lifetime.signal };
    this.page.addEventListener("change", (event) => this.change(event), options);
    this.page.addEventListener("click", (event) => this.click(event), options);
  }
  /** Translate management input changes into controller actions.
   * @param {Event} event
   * @returns {void}
   */
  change(event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)) return;
    if (target.dataset.layer) {
      this.layers.set(target.dataset.layer, /** @type {HTMLInputElement} */ (target).checked);
      void this.market.refresh();
    }
    if (target.id === "object-grouping")
      this.layers.setGrouping(/** @type {HTMLInputElement} */ (target).checked);
    if (!target.dataset.filter) return;
    const url = new URL(this.view.url);
    const name = target.dataset.filter;
    url.searchParams.set(name, target.value);
    if (name === "city") url.searchParams.delete("vehicle");
    if (name === "vehicle") url.searchParams.delete("city");
    if (name === "scope") {
      url.searchParams.delete("scope_id");
      if (target.value !== "company") {
        const first = this.view.analyticsChoices?.[target.value]?.[0]?.id;
        if (!first) return;
        url.searchParams.set("scope_id", first);
      }
    }
    this.navigate(url.pathname + url.search);
  }
  /** Dispatch a management button action.
   * @param {MouseEvent} event
   * @returns {void}
   */
  click(event) {
    if (!(event.target instanceof Element)) return;
    const action = event.target.closest("[data-action]")?.getAttribute("data-action");
    if (action === "reset-layers") {
      this.layers.reset();
      void this.market.refresh();
    }
    if (action === "refresh-analytics") void this.analytics.refresh();
    if (action === "panel-mode") {
      const panel = this.panel.panel;
      panel.dataset.mode = panel.dataset.mode === "management" ? "context" : "management";
      document
        .querySelector("#game")
        ?.classList.toggle("management-open", panel.dataset.mode === "management");
    }
    if (action === "more-navigation") {
      const nav = this.page.querySelector("#navigation");
      nav.classList.toggle("expanded");
      event.target
        .closest("button")
        ?.setAttribute("aria-expanded", String(nav.classList.contains("expanded")));
    }
  }
  /** Release owned resources and reject late updates.
   * @returns {void}
   */
  destroy() {
    this.lifetime.abort();
  }
}
