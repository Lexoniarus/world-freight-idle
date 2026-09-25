import { Marker } from "maplibre-gl";
import { nearestLongitude } from "../geometry.js";
import { ZOOM_TIERS } from "./grouping.js";

/** Aggregate offers by city or origin; never draw identical offer pins. */
export function opportunityGroups(contracts, cityLevel) {
  const groups = new Map();
  for (const contract of contracts) {
    const origin = contract.origin;
    if (!Number.isFinite(origin.lon) || !Number.isFinite(origin.lat)) continue;
    const key = cityLevel ? origin.city_uid : (origin.facility_uid ?? origin.id);
    if (!groups.has(key)) groups.set(key, { origin, count: 0 });
    groups.get(key).count++;
  }
  return groups;
}

/** Accessible badges use existing coordinates and preserve keyboard nodes. */
export class Opportunities {
  constructor(map, navigate) {
    this.map = map;
    this.navigate = navigate;
    this.markers = new Map();
  }
  update(contracts, visible, selected = "") {
    const cityLevel = this.map.getZoom() < ZOOM_TIERS.regional;
    const groups = opportunityGroups(
      visible ? contracts.filter((item) => item.id !== selected) : [],
      cityLevel,
    );
    for (const [key, group] of groups) {
      let entry = this.markers.get(key);
      if (!entry) {
        const button = document.createElement("button");
        button.className = "opportunity-marker";
        const marker = new Marker({ element: button, anchor: "bottom", offset: [0, -18] });
        entry = { button, marker, group };
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          this.navigate(
            "/contracts?city=" + encodeURIComponent(this.markers.get(key).group.origin.city_uid),
          );
        });
        this.markers.set(key, entry);
      }
      entry.group = group;
      entry.button.textContent = `${cityLevel ? group.origin.city + " · " : ""}${group.count} Aufträge`;
      entry.button.setAttribute(
        "aria-label",
        `${group.origin.city} · ${group.origin.label} · ${group.count} Aufträge`,
      );
      entry.marker
        .setLngLat([nearestLongitude(group.origin.lon, this.map.getCenter().lng), group.origin.lat])
        .addTo(this.map);
    }
    for (const [key, entry] of this.markers)
      if (!groups.has(key)) {
        entry.marker.remove();
        this.markers.delete(key);
      }
  }
  destroy() {
    for (const entry of this.markers.values()) entry.marker.remove();
    this.markers.clear();
  }
}
