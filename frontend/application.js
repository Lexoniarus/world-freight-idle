import { releaseAll, reportCleanup } from "./lifecycle.js";
/** High-level lifecycle orchestration; components own individual workflows. */
export class GameApplication {
  /** @param {import("./types.js").ApplicationDependencies} dependencies */
  constructor({
    api,
    state,
    panel,
    map,
    actions,
    sync,
    contractMarket,
    router,
    scheduler,
    input,
    sheet,
    notifications,
    redirect,
    city,
    layers,
    analytics,
    managementInput,
    preferences,
    focus,
    assets,
    supabaseAuth,
  }) {
    this.focus = focus;
    this.preferences = preferences;
    this.assets = assets;
    this.supabaseAuth = supabaseAuth;
    this.city = city;
    this.layers = layers;
    this.analytics = analytics;
    this.managementInput = managementInput;
    this.navigationVersion = 0;
    this.api = api;
    this.state = state;
    this.panel = panel;
    this.map = map;
    this.actions = actions;
    this.sync = sync;
    this.contractMarket = contractMarket;
    this.router = router;
    this.scheduler = scheduler;
    this.input = input;
    this.sheet = sheet;
    this.notifications = notifications;
    this.redirect = redirect;
    this.disposed = false;
  }

  /** @returns {Promise<void>} */
  async start() {
    for (const component of [
      this.router,
      this.preferences,
      this.city,
      this.managementInput,
      this.sync,
      this.focus,
      this.contractMarket,
      this.input,
      this.sheet,
      this.scheduler,
    ])
      component?.start();
    this.panel.render();
    await Promise.all([this.panel.loadDetails(), this.sync.refreshGameState()]);
    if (this.disposed) return;
    await this.navigateTo(this.panel.view.url);
  }

  /** @param {URL} url @returns {Promise<void>} */
  async navigateTo(url) {
    const version = ++this.navigationVersion;
    this.focus?.cancel();
    this.actions.cancelQuote();
    await this.city?.selectRoute(url);
    if (version !== this.navigationVersion || this.disposed) return;
    this.layers?.select(url);
    this.panel.selectRoute(url);
    this.sync.updateMap();
    this.map?.setPreview(null);
    this.synchronizeMapSelection();
    this.focus?.select(url);
    void this.contractMarket.refresh();
    void this.analytics?.refresh();
  }

  /** Synchronize vehicle, transport or offer selection. @returns {void} */
  synchronizeMapSelection() {
    const path = this.panel.view.url.pathname;
    this.map?.select(
      path.startsWith("/transports/") ||
        path.startsWith("/fleet/") ||
        path.startsWith("/contracts/")
        ? path.split("/").at(-1)
        : "",
    );
  }

  /** @returns {Promise<void>} */
  async logout() {
    await this.api.request("/auth/logout", { method: "POST" });
    await this.supabaseAuth?.logout();
    reportCleanup([() => this.destroy()]);
    this.redirect("/login");
  }

  /** @returns {void} */
  destroy() {
    if (this.disposed) return;
    this.disposed = true;
    releaseAll(
      [
        this.scheduler,
        this.focus,
        this.preferences,
        this.city,
        this.layers,
        this.analytics,
        this.managementInput,
        this.input,
        this.sheet,
        this.router,
        this.actions,
        this.panel,
        this.contractMarket,
        this.sync,
        this.map,
        this.notifications,
        this.state,
        this.assets,
        this.supabaseAuth,
        this.api,
      ].map((component) => () => component?.destroy()),
    );
  }
}
