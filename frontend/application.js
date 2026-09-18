/** High-level lifecycle orchestration; components own individual workflows. */
export class GameApplication {
  /** @param {{api: import('./api.js').GameApiClient, state: import('./state.js').GameState,
   * panel: import('./controllers/panel-controller.js').PanelController, map: import('./map/world-map.js').WorldMap | null,
   * actions: import('./controllers/game-actions.js').GameActions, sync: import('./controllers/game-sync.js').GameSync,
   * router: import('./navigation.js').BrowserRouter, scheduler: import('./controllers/refresh-scheduler.js').RefreshScheduler,
   * input: import('./controllers/input-controller.js').InputController, sheet: import('./controllers/mobile-sheet.js').MobileSheet,
   * notifications: import('./controllers/notifications.js').Notifications, redirect: (path: string) => void}} dependencies */
  constructor({
    api,
    state,
    panel,
    map,
    actions,
    sync,
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
    this.router = router;
    this.scheduler = scheduler;
    this.input = input;
    this.sheet = sheet;
    this.notifications = notifications;
    this.redirect = redirect;
    this.disposed = false;
  }
  /** Start UI listeners before loading the initial authoritative snapshot. */
  async start() {
    for (const component of [this.router, this.sync, this.input, this.sheet, this.scheduler])
      component.start();
    this.panel.render();
    await Promise.all([
      this.panel.loadDetails(),
      this.sync.loadHubs(),
      this.sync.refreshGameState(),
    ]);
    if (!this.disposed) this.selectTransport();
  }
  /** Coordinate a route change across selection-dependent components. @param {URL} url */
  navigateTo(url) {
    this.actions.cancelQuote();
    this.panel.selectRoute(url);
    this.map?.setPreview(null);
    this.selectTransport();
  }
  /** Apply transport selection without moving or rebuilding the camera. */
  selectTransport() {
    const path = this.panel.view.url.pathname;
    this.map?.select(path.startsWith("/transports/") ? path.split("/").at(-1) : "");
  }
  /** Revoke the session before closing the current application. */
  async logout() {
    await this.api.request("/auth/logout", { method: "POST" });
    this.destroy();
    this.redirect("/login");
  }
  /** Dispose components before aborting outstanding transport requests. */
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
      this.sync,
      this.map,
      this.notifications,
      this.state,
      this.api,
    ])
      component?.destroy();
  }
}
