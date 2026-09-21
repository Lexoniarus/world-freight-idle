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
  }) {
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
      this.sync,
      this.contractMarket,
      this.input,
      this.sheet,
      this.scheduler,
    ])
      component.start();
    this.panel.render();
    await Promise.all([this.panel.loadDetails(), this.sync.refreshGameState()]);
    if (this.disposed) return;
    await this.contractMarket.refresh();
    if (!this.disposed) this.selectTransport();
  }

  navigateTo(url) {
    this.actions.cancelQuote();
    this.panel.selectRoute(url);
    this.map?.setPreview(null);
    this.selectTransport();
    void this.contractMarket.refresh();
  }

  selectTransport() {
    const path = this.panel.view.url.pathname;
    this.map?.select(path.startsWith("/transports/") ? path.split("/").at(-1) : "");
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
