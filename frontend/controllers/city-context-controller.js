import { LatestRequest } from "../state.js";
import { cityLocations, activeCityIds, resolveLegacyCity } from "../city-context.js";

/** Own session city selection; market availability is a separate fact. */
export class CityContextController {
  constructor({ state, view, request, notify, map }) {
    this.state = state;
    this.view = view;
    this.request = request;
    this.notify = notify;
    this.map = map;
    this.known = new Map();
    this.explicit = false;
    this.marketRoute = false;
    this.selected = "";
    this.pending = new LatestRequest();
    this.changed = () => this.update();
  }
  start() {
    this.state.addEventListener("change", this.changed);
  }
  update() {
    for (const location of cityLocations(this.state.data))
      this.known.set(location.city_uid, location);
    const active = activeCityIds(this.state.data);
    if (this.marketRoute && this.selected && !active.includes(this.selected)) {
      this.selected = "";
      this.explicit = true;
      this.view.url.searchParams.set("city", "");
      window.history.replaceState({}, "", this.view.url.pathname + this.view.url.search);
    }
    if (!this.explicit && !active.includes(this.selected)) this.selected = active[0] ?? "";
    this.view.cityUid = this.selected;
    this.view.cities = [...this.known.values()].sort((a, b) => a.city.localeCompare(b.city));
    this.view.activeCities = active;
    this.view.marketCities = this.view.cities.filter((city) => active.includes(city.city_uid));
    const label = document.querySelector("#current-city-label");
    if (label) label.textContent = this.known.get(this.selected)?.city ?? "Alle Städte";
  }
  async selectRoute(url) {
    const pending = this.pending.start();
    const old = this.selected;
    let identifier = url.searchParams.get("city");
    const vehicle = this.state.data?.vehicles.find(
      (item) =>
        item.id ===
        (url.searchParams.get("vehicle") ??
          (url.pathname.startsWith("/fleet/") ? url.pathname.split("/")[2] : null)),
    );
    if (identifier === null && vehicle?.status === "idle")
      identifier = (vehicle.location_snapshot ?? vehicle.hub)?.city_uid ?? null;
    try {
      if (identifier === null && url.searchParams.has("hub")) {
        const hub = url.searchParams.get("hub");
        const location =
          resolveLegacyCity(this.state.data, hub) ??
          (await this.request("/map/facilities/" + encodeURIComponent(hub), {
            signal: pending.signal,
          }));
        this.known.set(location.city_uid, location);
        identifier = location.city_uid;
      }
      if (identifier && !this.known.has(identifier)) {
        const city = await this.request("/map/cities/" + encodeURIComponent(identifier), {
          signal: pending.signal,
        });
        if (pending.isCurrent()) this.known.set(identifier, city);
      }
      if (!pending.isCurrent()) return;
      if (identifier !== null) {
        this.selected = identifier;
        this.explicit = true;
      }
    } catch (error) {
      if (!pending.isCurrent() || error.name === "AbortError") return;
      this.notify("Stadt oder Standort nicht verfügbar. Alle Städte werden angezeigt.");
      this.selected = "";
      this.explicit = true;
    }
    this.marketRoute = url.pathname.startsWith("/contracts");
    if (
      this.state.data &&
      this.marketRoute &&
      !activeCityIds(this.state.data).includes(this.selected)
    ) {
      this.selected = "";
      this.explicit = true;
    }
    this.update();
    url.searchParams.delete("hub");
    if (this.selected || this.explicit) url.searchParams.set("city", this.selected);
    else url.searchParams.delete("city");
    window.history.replaceState({}, "", url.pathname + url.search);
    if (this.selected && old !== this.selected && this.explicit) this.focus();
  }
  focus() {
    const points = [...cityLocations(this.state.data), this.known.get(this.selected)]
      .filter(Boolean)
      .filter(
        (item) =>
          item.city_uid === this.selected && Number.isFinite(item.lon) && Number.isFinite(item.lat),
      )
      .map((item) => [item.lon, item.lat]);
    if (points.length) this.map?.camera.fitCoordinates(points);
    else this.notify("Für diese Stadt sind noch keine Kartenpositionen geladen.");
  }
  destroy() {
    this.pending.cancel();
    this.state.removeEventListener("change", this.changed);
  }
}
