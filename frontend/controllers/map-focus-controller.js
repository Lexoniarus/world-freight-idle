import { focusCoordinates } from "../map/focus-targets.js";

/** Consume each navigation focus intent once, after its data and map are ready. */
export class MapFocusController {
  /** @param {{state: import('../state.js').GameState, view: import('../types.js').PanelView, map: import('../types.js').GameMap | null}} dependencies */
  constructor({ state, view, map }) {
    this.state = state;
    this.view = view;
    this.map = map;
    this.pending = null;
    this.generation = 0;
    this.key = "";
    this.appliedKey = "";
    this.requestedRoute = "";
    this.changed = () => this.flush();
  }
  /** Register owned listeners for this controller.
   * @returns {void}
   */
  start() {
    this.state.addEventListener("change", this.changed);
    this.map?.addEventListener("ready", this.changed);
  }
  /** Invalidate delayed work before asynchronous navigation resolution.
   * @returns {void}
   */
  cancel() {
    this.generation++;
    this.pending = null;
  }
  /** Record only a genuine route or visible-filter change. @param {URL} url
   * @returns {void}
   */
  select(url) {
    const key =
      url.pathname +
      "?" +
      ["city", "status", "model", "search"]
        .map((name) => `${name}=${url.searchParams.get(name) ?? ""}`)
        .join("&");
    if (key === this.appliedKey) return;
    this.key = key;
    this.requestedRoute = "";
    this.pending = { url: new URL(url), generation: this.generation };
    this.flush();
  }
  /** Fulfil a pending intent without establishing a polling camera follower.
   * @returns {void}
   */
  flush() {
    if (!this.pending || !this.state.data || !this.map?.ready) return;
    const points = focusCoordinates(
      this.state.data,
      this.pending.url,
      this.state.now(),
      this.state.contractDetail,
      this.view.cityUid ?? "",
      this.view.cities ?? [],
    );
    if (points === null) {
      const [, section, id] = this.pending.url.pathname.split("/");
      const trip = this.state.data.transports.find((item) =>
        section === "fleet" ? item.vehicle_id === id : section === "transports" && item.id === id,
      );
      if (trip?.route_ref && this.requestedRoute !== trip.route_ref) {
        this.requestedRoute = trip.route_ref;
        void this.state.loadTransportRoute(trip.id).catch((error) => {
          if (error.name !== "AbortError")
            console.warn("Selected route unavailable:", error.message);
        });
      }
      return;
    }
    this.appliedKey = this.key;
    this.pending = null;
    if (points.length) this.map.fitCoordinates(points);
  }
  /** A current user-requested quote supersedes the endpoint framing.
   * @param {import('../types.js').Quote} quote
   * @returns {void}
   */
  quote(quote) {
    this.pending = null;
    this.map?.focusRoute(quote.route_geojson);
  }
  /** Release owned resources and reject late updates.
   * @returns {void}
   */
  destroy() {
    this.cancel();
    this.state.removeEventListener("change", this.changed);
    this.map?.removeEventListener("ready", this.changed);
  }
}
