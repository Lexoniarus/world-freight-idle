import { focusCoordinates } from "../map/focus-targets.js";

/** Consume each navigation focus intent once, after its data and map are ready. */
export class MapFocusController {
  /** @param {{state: import('../state.js').GameState, view: import('../types.js').PanelView, map: import('../map/world-map.js').WorldMap | null}} dependencies */
  constructor({ state, view, map }) {
    this.state = state;
    this.view = view;
    this.map = map;
    this.pending = null;
    this.generation = 0;
    this.key = "";
    this.appliedKey = "";
    this.changed = () => this.flush();
  }
  start() {
    this.state.addEventListener("change", this.changed);
    this.map?.map.on("load", this.changed);
  }
  /** Invalidate delayed work before asynchronous navigation resolution. */
  cancel() {
    this.generation++;
    this.pending = null;
  }
  /** Record only a genuine route or visible-filter change. @param {URL} url */
  select(url) {
    const key =
      url.pathname +
      "?" +
      ["city", "status", "model", "search"]
        .map((name) => `${name}=${url.searchParams.get(name) ?? ""}`)
        .join("&");
    if (key === this.appliedKey) return;
    this.key = key;
    this.pending = { url: new URL(url), generation: this.generation };
    this.flush();
  }
  /** Fulfil a pending intent without establishing a polling camera follower. */
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
    if (points === null) return;
    this.appliedKey = this.key;
    this.pending = null;
    if (points.length) this.map.camera.fitCoordinates(points);
  }
  /** A current user-requested quote supersedes the endpoint framing. */
  quote(quote) {
    this.pending = null;
    this.map?.focusRoute(quote.route_geojson);
  }
  destroy() {
    this.cancel();
    this.state.removeEventListener("change", this.changed);
    this.map?.map.off("load", this.changed);
  }
}
