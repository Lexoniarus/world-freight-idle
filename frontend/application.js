/** High-level lifecycle orchestration; components own individual workflows. */
export class GameApplication {
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
  }) {
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

  async start() {
    for (const component of [
      this.router,
      this.city,
      this.managementInput,
      this.sync,
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

  async navigateTo(url) {
    const version = ++this.navigationVersion;
    this.actions.cancelQuote();
    await this.city?.selectRoute(url);
    if (version !== this.navigationVersion || this.disposed) return;
    this.layers?.select(url);
    this.panel.selectRoute(url);
    this.map?.setPreview(null);
    this.selectTransport();
    void this.contractMarket.refresh();
    void this.analytics?.refresh();
  }

  selectTransport() {
    const path = this.panel.view.url.pathname;
    this.map?.select(
      path.startsWith("/transports/") ||
        path.startsWith("/fleet/") ||
        path.startsWith("/contracts/")
        ? path.split("/").at(-1)
        : "",
    );
  }

  async logout() {
    await this.api.request("/auth/logout", { method: "POST" });
    this.destroy();
    this.redirect("/login");
  }

  destroy() {
    if (this.disposed) return;
    this.disposed = true;
    for (const component of [
      this.scheduler,
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
      this.api,
    ])
      component?.destroy();
  }
}
