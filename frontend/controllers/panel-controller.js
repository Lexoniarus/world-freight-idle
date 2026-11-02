import { matchVehicleImages } from "../ui/preserve-vehicle-images.js";
import { LatestRequest } from "../latest-request.js";
import { eligibleVehicles } from "../geometry.js";
import { renderPanel } from "../views/panel.js";
import { panelTitle } from "../navigation.js";
import { requiredElement } from "../ui/dom.js";

/** Own panel selection, auxiliary reads and focus-preserving presentation. */
export class PanelController {
  /** @param {{view: import('../types.js').PanelView, request: import('../types.js').RequestJson, notify: import('../types.js').Notify, now: import('../types.js').Clock, images?: import('../vehicle-image-bindings.js').VehicleImageController | null}} options */
  constructor({ view, request, notify, now, images = null }) {
    this.view = view;
    this.request = request;
    this.notify = notify;
    this.now = now;
    this.pending = new LatestRequest();
    this.panel = requiredElement("#panel");
    this.content = requiredElement("#panel-content");
    this.title = requiredElement("#panel-title");
    this.contentFocus = null;
    this.returnFocus = null;
    this.disposed = false;
    this.images = images;
  }
  /** Report whether a mutation or quote currently owns the panel.
   * @returns {boolean}
   */
  isBusy() {
    return this.view.busy;
  }
  /** Report whether the panel surface is currently visible.
   * @returns {boolean}
   */
  isOpen() {
    return !this.panel.hidden;
  }
  /** Return the currently published quote for map focus and dispatch.
   * @returns {import('../types.js').Quote | null}
   */
  currentQuote() {
    return this.view.quote;
  }
  /** Publish quote progress without exposing writable view state.
   * @param {boolean} active
   * @returns {void}
   */
  setQuotePending(active) {
    this.view.quoting = active;
  }
  /** Select a vehicle and discard economics from the prior selection.
   * @param {string} vehicleId
   * @returns {void}
   */
  selectVehicle(vehicleId) {
    this.view.selectedVehicle = vehicleId;
    this.view.url.searchParams.set("vehicle", vehicleId);
    window.history.replaceState({}, "", this.view.url.pathname + this.view.url.search);
    this.view.quote = null;
  }
  /** Publish a quote belonging to the current vehicle selection.
   * @param {import('../types.js').Quote | null} quote
   * @returns {void}
   */
  publishQuote(quote) {
    this.view.quote = quote;
  }
  /** Publish mutation progress owned by action orchestration.
   * @param {boolean} active
   * @returns {void}
   */
  setMutationPending(active) {
    this.view.mutating = active;
  }
  /** Publish one synchronized game and market-detail snapshot.
   * @param {import('../types.js').GameSnapshot} state
   * @param {import('../types.js').Contract | null} detailContract
   * @param {string | null} detailId
   * @param {boolean} marketLoaded
   * @param {boolean} marketStale
   * @returns {void}
   */
  publishGameState(state, detailContract, detailId, marketLoaded, marketStale) {
    Object.assign(this.view, {
      state,
      detailContract,
      detailId,
      marketLoaded,
      marketStale,
    });
  }
  /** Publish route-local city labels resolved by the city controller.
   * @param {string} cityUid
   * @param {Array<import('../types.js').FacilityLocation>} cities
   * @param {Array<string>} activeCities
   * @returns {void}
   */
  publishCityContext(cityUid, cities, activeCities) {
    Object.assign(this.view, {
      cityUid,
      cities,
      activeCities,
      marketCities: cities.filter((city) => activeCities.includes(city.city_uid)),
    });
  }
  /** Mark a preference read as pending.
   * @returns {void}
   */
  beginPreferenceLoad() {
    this.view.preferenceStatus = "loading";
  }
  /** Publish the curated preference palette and confirmed color.
   * @param {Array<string>} palette
   * @param {string} color
   * @returns {void}
   */
  publishPreferences(palette, color) {
    this.view.preferenceStatus = "ready";
    this.view.companyPalette = palette;
    this.view.user.company_color = color;
  }
  /** Mark a preference read as unavailable.
   * @returns {void}
   */
  failPreferenceLoad() {
    this.view.preferenceStatus = "error";
  }
  /** Publish whether the latest preference write failed.
   * @param {boolean} failed
   * @returns {void}
   */
  setPreferenceSaveError(failed) {
    this.view.preferenceSaveError = failed;
  }
  /** Publish one optimistic or confirmed company color.
   * @param {string} color
   * @returns {void}
   */
  publishCompanyColor(color) {
    this.view.user.company_color = color;
  }
  /** Report whether a color belongs to the server-provided palette.
   * @param {string} color
   * @returns {boolean}
   */
  acceptsCompanyColor(color) {
    return Boolean(this.view.companyPalette?.includes(color));
  }
  /** Mark analytics loading and clear an obsolete error.
   * @returns {void}
   */
  beginAnalyticsLoad() {
    this.view.analyticsLoading = true;
    this.view.analyticsError = false;
  }
  /** Publish one analytics response and its company breakdowns.
   * @param {import('../types.js').AnalyticsReport & {scope: {type: string}}} result
   * @returns {void}
   */
  publishAnalytics(result) {
    this.view.analytics = result;
    if (result.scope.type === "company") this.view.analyticsChoices = result.breakdowns;
  }
  /** Mark the latest analytics read as failed.
   * @returns {void}
   */
  failAnalyticsLoad() {
    this.view.analyticsError = true;
  }
  /** Finish the current analytics request.
   * @returns {void}
   */
  finishAnalyticsLoad() {
    this.view.analyticsLoading = false;
  }
  /** Toggle between contextual and management panel presentation.
   * @returns {void}
   */
  toggleMode() {
    this.panel.dataset.mode = this.panel.dataset.mode === "management" ? "context" : "management";
    document
      .querySelector("#game")
      ?.classList.toggle("management-open", this.panel.dataset.mode === "management");
  }
  /** Reset only panel-specific selection when the route changes.
   * @param {URL} url
   *
   * @returns {void}
   */
  selectRoute(url) {
    const sameView = this.view.url.pathname === url.pathname;
    const scroll = this.content.scrollTop;
    this.returnFocus = document.activeElement?.closest(".nav-item") || this.returnFocus;
    this.pending.cancel();
    Object.assign(this.view, {
      url,
      quote: null,
      selectedVehicle: url.searchParams.get("vehicle") ?? "",
      rankings: null,
      panelError: false,
    });
    if (!sameView) this.contentFocus = null;
    if (!sameView || !this.panel.dataset.mode)
      this.panel.dataset.mode = url.pathname === "/company" ? "management" : "context";
    document
      .querySelector("#game")
      ?.classList.toggle("management-open", this.panel.dataset.mode === "management");
    this.render();
    this.content.scrollTop = sameView ? scroll : 0;
    if (url.pathname === "/")
      (this.returnFocus?.isConnected ? this.returnFocus : requiredElement(".nav-item")).focus();
    else if (!sameView) this.title.focus({ preventScroll: true });
    void this.loadDetails();
  }
  /** Fetch selection-specific data; an obsolete response cannot publish.
   * @returns {Promise<void>}
   */
  async loadDetails() {
    if (this.disposed) return;
    const path = this.view.url.pathname;
    const endpoint =
      path === "/leaderboard"
        ? "/leaderboard"
        : path === "/fleet" &&
            this.view.url.searchParams.get("tab") === "shop" &&
            !this.view.catalogue
          ? "/fleet/catalogue"
          : null;
    if (!endpoint) return;
    const request = this.pending.start();
    try {
      const result = await this.request(endpoint, { signal: request.signal });
      if (!request.isCurrent()) return;
      if (endpoint === "/leaderboard") this.view.rankings = result.players;
      else this.view.catalogue = result;
      this.view.panelError = false;
    } catch (error) {
      if (!request.isCurrent() || error.name === "AbortError") return;
      this.notify(error.message);
      this.view.panelError = true;
    }
    this.render();
  }
  /** Synchronize the selected panel and its navigation state.
   * @returns {void}
   */
  render() {
    if (this.disposed) return;
    this.reconcileVehicleSelection();
    const open = this.view.url.pathname !== "/";
    this.panel.hidden = !open;
    const mapElement = document.querySelector("#world-map");
    if (mapElement instanceof HTMLElement)
      mapElement.inert = open && this.panel.dataset.sheet === "full" && window.innerWidth <= 759;
    requiredElement("#game").classList.toggle("panel-open", open);
    this.title.textContent = panelTitle(this.view.url);
    document.title = this.title.textContent + " · World Freight";
    this.updateNavigation(open);
    if (open) this.replaceContent();
    requiredElement("#welcome").hidden =
      open ||
      !this.view.state ||
      this.view.state.player.completed > 0 ||
      this.view.state.active_transports > 0;
  }
  /** Keep the selection explicit and invalidate quotes for removed vehicles.
   * @returns {void}
   */
  reconcileVehicleSelection() {
    const contractId = this.view.url.pathname.startsWith("/contracts/")
      ? this.view.url.pathname.split("/")[2]
      : null;
    const contract =
      this.view.detailId === contractId
        ? this.view.detailContract
        : this.view.state?.contracts.find((item) => item.id === contractId);
    const vehicles = contract ? eligibleVehicles(this.view.state.vehicles, contract) : [];
    if (contractId && !vehicles.some((vehicle) => vehicle.id === this.view.selectedVehicle)) {
      this.view.selectedVehicle = this.view.url.searchParams.get("vehicle")
        ? ""
        : vehicles[0]?.id || "";
      this.view.quote = null;
    }
  }
  /** Mark exactly the active navigation destination.
   * @param {boolean} open
   *
   * @returns {void}
   */
  updateNavigation(open) {
    document.querySelectorAll(".nav-rail a").forEach((link) => {
      const target = new URL(link.getAttribute("href"), location.origin);
      const active =
        target.pathname === "/"
          ? !open
          : this.view.url.pathname.startsWith(target.pathname) &&
            target.searchParams.get("tab") === this.view.url.searchParams.get("tab");
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }
  /** Replace changed DOM while preserving a selected control's keyboard focus.
   * @returns {void}
   */
  replaceContent() {
    const focused = document.activeElement;
    if (focused instanceof HTMLElement && this.content.contains(focused))
      this.contentFocus = {
        id: focused.id,
        action: focused.dataset.action,
        item: focused.dataset.id,
        href: focused.getAttribute("href"),
        filter: focused.getAttribute("data-filter"),
      };
    // A player who moved to navigation or the map must keep that focus.
    if (focused !== document.body && !this.content.contains(focused)) this.contentFocus = null;
    const fragment = renderPanel({ ...this.view, now: this.now() });
    for (const detail of fragment.querySelectorAll("details[data-disclosure]")) {
      const current = [...this.content.querySelectorAll("details[data-disclosure]")].find(
        (item) => item.getAttribute("data-disclosure") === detail.getAttribute("data-disclosure"),
      );
      if (current)
        /** @type {HTMLDetailsElement} */ (detail).open = /** @type {HTMLDetailsElement} */ (
          current
        ).open;
    }
    this.images?.prepare(fragment, this.view.user.company_color);
    const media = matchVehicleImages(this.content, fragment);
    const same =
      this.content.childNodes.length === fragment.childNodes.length &&
      [...this.content.childNodes].every((node, index) =>
        node.isEqualNode(fragment.childNodes[index]),
      );
    if (same) return;
    for (const { current, next } of media) next.replaceWith(current);
    this.content.replaceChildren(fragment);
    this.images?.update(this.content.querySelectorAll("img[data-vehicle-model]"));
    this.restoreFocus();
  }
  /** Restore a surviving control only when a replacement was necessary.
   * @returns {void}
   */
  restoreFocus() {
    const focus = this.contentFocus;
    if (!focus) return;
    const replacement = [...this.content.querySelectorAll("button, a, select, input")].find(
      (element) =>
        focus.filter
          ? element.getAttribute("data-filter") === focus.filter
          : focus.id
            ? element.id === focus.id
            : focus.action
              ? element.getAttribute("data-action") === focus.action &&
                element.getAttribute("data-id") === focus.item
              : focus.href && element.getAttribute("href") === focus.href,
    );
    if (replacement instanceof HTMLElement && !replacement.hasAttribute("disabled"))
      replacement.focus({ preventScroll: true });
  }
  /** Stop selection-specific reads and future rendering.
   * @returns {void}
   */
  destroy() {
    this.disposed = true;
    this.pending.cancel();
    this.images?.destroy();
  }
}
