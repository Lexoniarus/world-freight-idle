import { GameApiClient, ApiError } from "./api.js";
import { GameState } from "./state.js";
import { BrowserRouter } from "./navigation.js";
import { GameApplication } from "./application.js";
import { AuthController } from "./controllers/auth-controller.js";
import { GameActions } from "./controllers/game-actions.js";
import { GameSync } from "./controllers/game-sync.js";
import { PanelController } from "./controllers/panel-controller.js";
import { InputController } from "./controllers/input-controller.js";
import { MobileSheet } from "./controllers/mobile-sheet.js";
import { Notifications } from "./controllers/notifications.js";
import { RefreshScheduler } from "./controllers/refresh-scheduler.js";
import { WorldMap } from "./map/world-map.js";
import { createBasemap } from "./map/provider.js";
import { renderShell } from "./views/shell.js";
import { html, requiredElement } from "./ui/dom.js";

/** Assemble the browser application; this is the frontend composition root. */
export async function bootstrap() {
  const root = requiredElement("#app");
  const redirect = (path) => window.location.replace(path);
  const api = new GameApiClient(globalThis.fetch.bind(globalThis), redirect);
  let application;
  const pagehide = () => {
    application?.destroy();
    api.destroy();
  };
  window.addEventListener("pagehide", pagehide, { once: true });
  // A disposed application restored from the back-forward cache needs a fresh lifecycle.
  window.addEventListener("pageshow", (event) => {
    if (event.persisted) location.reload();
  });
  try {
    if (location.pathname === "/login") {
      application = new AuthController(root, api, redirect);
    } else {
      const user = await api.request("/auth/me");
      if (api.lifetime.signal.aborted) return;
      root.replaceChildren(renderShell(user));
      application = createGameApplication(api, user, redirect);
    }
    await application.start();
  } catch (error) {
    application?.destroy();
    api.destroy();
    if (error instanceof ApiError && error.status === 401) {
      redirect("/login");
      return;
    }
    if (error.name !== "AbortError")
      root.replaceChildren(
        html`<main class="startup-error">
          <h1>Deine Welt ist kurz außer Reichweite.</h1>
          <p>${error.message}</p>
          <a class="button primary" href="/">Erneut verbinden</a>
        </main>`,
      );
  }
}

/** Wire stateful game components around a single persistent shell.
 * @param {GameApiClient} api
 * @param {{username: string}} user
 * @param {(path: string) => void} redirect
 * @returns {GameApplication}
 */
function createGameApplication(api, user, redirect) {
  const state = new GameState(api.request);
  /** @type {import("./types.js").PanelView} */
  const view = {
    url: new URL(location.href),
    state: null,
    user,
    quote: null,
    selectedVehicle: "",
    mutating: false,
    quoting: false,
    catalogue: null,
    rankings: null,
    panelError: false,
    get busy() {
      return this.mutating || this.quoting;
    },
  };
  const notifications = new Notifications(
    requiredElement("#toasts"),
    requiredElement("#map-notice"),
  );
  const notify = notifications.show;
  const panel = new PanelController({ view, request: api.request, notify, now: () => state.now() });
  let application;
  const router = new BrowserRouter(window, (url) => application.navigateTo(url));
  const navigate = (path) => router.navigate(path);
  const map = createWorldMap(navigate, notify, () => state.now());
  const sync = new GameSync({ state, request: api.request, panel, map, notify });
  const actions = new GameActions({
    request: api.request,
    state,
    panel,
    map,
    notify,
    navigate,
    refresh: () => sync.refreshGameState(),
    logout: () => application.logout(),
  });
  const scheduler = new RefreshScheduler({
    refresh: async () => {
      await sync.refreshGameState();
      if (view.url.pathname === "/leaderboard") await panel.loadDetails();
    },
    updateProgress: () => sync.updateProgress(),
    canRefresh: () => !view.busy,
  });
  const input = new InputController({ page: document, navigate, actions, panel, map });
  const sheet = new MobileSheet(requiredElement("#sheet-handle"), requiredElement("#panel"));
  application = new GameApplication({
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
  });
  return application;
}

/** Keep game controls usable when the browser cannot initialize WebGL. */
function createWorldMap(navigate, notify, now) {
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  try {
    return new WorldMap("world-map", {
      navigate,
      notify,
      now,
      provider: createBasemap(),
      reducedMotion: () => reducedMotion.matches,
      isHidden: () => document.hidden,
      viewport: () => ({
        width: innerWidth,
        height: innerHeight,
        panelOpen: !requiredElement("#panel").hidden,
      }),
    });
  } catch {
    notify(
      "Die Karte benötigt WebGL. Du kannst Aufträge und Flotte weiterhin über die Navigation verwalten.",
      "map",
    );
    return null;
  }
}
