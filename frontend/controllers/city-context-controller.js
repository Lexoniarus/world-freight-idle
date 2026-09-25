import { LatestRequest } from "../state.js";
import { cityLocations, activeCityIds, resolveLegacyCity } from "../city-context.js";
import { marketVehicle, vehicleCity } from "../market-context.js";

/** Resolve route-local city context without scoping the world overview. */
export class CityContextController {
  constructor({ state, view, request, notify }) {
    this.state = state;
    this.view = view;
    this.request = request;
    this.notify = notify;
    this.known = new Map();
    this.route = null;
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
    if (this.route?.pathname === "/contracts") {
      const vehicle = marketVehicle(this.state.data, this.route);
      this.selected = vehicle ? vehicleCity(vehicle) : "";
      if (!vehicle) this.route.searchParams.delete("vehicle");
      this.writeCity(this.route);
    }
    this.view.cityUid = this.selected;
    this.view.cities = [...this.known.values()].sort((a, b) => a.city.localeCompare(b.city));
    this.view.activeCities = active;
    this.view.marketCities = this.view.cities.filter((city) => active.includes(city.city_uid));
  }
  /** Normalize only this route's city parameter. */
  writeCity(url) {
    if (this.selected) url.searchParams.set("city", this.selected);
    else url.searchParams.delete("city");
    window.history.replaceState({}, "", url.pathname + url.search);
  }
  async selectRoute(url) {
    const pending = this.pending.start();
    this.route = null;
    if (url.pathname === "/") url.searchParams.delete("vehicle");
    let identifier = url.pathname === "/" ? null : url.searchParams.get("city");
    const vehicle = this.state.data?.vehicles.find(
      (item) =>
        item.id ===
        (url.searchParams.get("vehicle") ??
          (url.pathname.startsWith("/fleet/") ? url.pathname.split("/")[2] : null)),
    );
    if (url.pathname !== "/" && identifier === null && vehicle?.status === "idle")
      identifier = (vehicle.location_snapshot ?? vehicle.hub)?.city_uid ?? null;
    try {
      if (url.pathname !== "/" && identifier === null && url.searchParams.has("hub")) {
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
      this.selected = identifier ?? "";
    } catch (error) {
      if (!pending.isCurrent() || error.name === "AbortError") return;
      this.notify("Stadt oder Standort nicht verfügbar. Bitte wähle ein Fahrzeug.");
      this.selected = "";
    }
    if (url.pathname === "/contracts") {
      if (identifier) url.searchParams.set("city", identifier);
      const vehicle = marketVehicle(this.state.data, url, true);
      if (vehicle) url.searchParams.set("vehicle", vehicle.id);
    }
    this.route = url;
    this.update();
    url.searchParams.delete("hub");
    this.writeCity(url);
  }
  destroy() {
    this.pending.cancel();
    this.state.removeEventListener("change", this.changed);
  }
}
