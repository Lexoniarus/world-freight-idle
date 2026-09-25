import { Marker, Popup } from "maplibre-gl";
import { nearestLongitude } from "../geometry.js";
import { groupVehicles, GROUP_INTERVAL, ZOOM_TIERS } from "./grouping.js";

/** Render accessible count markers independently of the movement frame loop. */
export class VehicleGroups {
  constructor(map, navigate, reducedMotion) {
    this.map = map;
    this.navigate = navigate;
    this.reducedMotion = reducedMotion;
    this.markers = new Map();
    this.hidden = new Set();
    this.last = -Infinity;
    this.enabled = true;
    this.popup = null;
  }
  update(features, selected, force = false) {
    const time = performance.now();
    if (!force && time - this.last < (this.reducedMotion() ? 1000 : GROUP_INTERVAL))
      return features.filter((feature) => !this.hidden.has(feature.properties.key));
    this.last = time;
    const groups = groupVehicles(
      features,
      (coordinate) =>
        this.map.project([
          nearestLongitude(coordinate[0], this.map.getCenter().lng),
          coordinate[1],
        ]),
      selected,
      this.enabled,
    );
    const active = new Set();
    this.hidden.clear();
    for (const group of groups.filter(
      (item) =>
        item.members.length > 1 ||
        (this.enabled &&
          this.map.getZoom() < ZOOM_TIERS.regional &&
          !item.members.some(
            (member) =>
              member.properties.isOwn &&
              (member.properties.id === selected || member.properties.vehicleId === selected),
          )),
    )) {
      const key = group.members[0].properties.key;
      active.add(key);
      for (const item of group.members) this.hidden.add(item.properties.key);
      let entry = this.markers.get(key);
      if (!entry) {
        const button = document.createElement("button");
        button.className = "vehicle-group " + (group.own ? "own" : "foreign");
        const marker = new Marker({ element: button });
        entry = { button, marker, members: group.members };
        button.addEventListener("click", (event) => {
          event.stopPropagation();
          const current = this.markers.get(key);
          if (this.map.getZoom() < ZOOM_TIERS.expandLimit)
            this.map.easeTo({
              center: current.marker.getLngLat(),
              zoom: Math.min(ZOOM_TIERS.expandLimit, this.map.getZoom() + 2),
              duration: this.reducedMotion() ? 0 : 350,
            });
          else this.showList(current.members, current.marker.getLngLat());
        });
        this.markers.set(key, entry);
      }
      entry.members = group.members;
      entry.button.textContent = String(group.members.length);
      entry.button.setAttribute(
        "aria-label",
        `${group.members.length} ${group.own ? "eigene" : "fremde"} Fahrzeuge – Gruppe öffnen`,
      );
      const coordinate = group.members[0].geometry.coordinates;
      entry.marker
        .setLngLat([nearestLongitude(coordinate[0], this.map.getCenter().lng), coordinate[1]])
        .addTo(this.map);
    }
    for (const [key, entry] of this.markers)
      if (!active.has(key)) {
        entry.marker.remove();
        this.markers.delete(key);
      }
    return features.filter((feature) => !this.hidden.has(feature.properties.key));
  }
  showList(features, coordinate) {
    this.popup?.remove();
    const list = document.createElement("div");
    list.className = "map-object-list";
    const title = document.createElement("strong");
    title.textContent = "Fahrzeug auswählen";
    list.append(title);
    for (const item of features) {
      const props = item.properties;
      const control = document.createElement(props.isOwn ? "button" : "p");
      control.textContent = `${props.modelName || "Fahrzeug"} · ${props.isOwn ? props.vehicleId : props.username}`;
      if (props.isOwn)
        control.addEventListener("click", () => {
          this.navigate(props.idle ? "/fleet/" + props.vehicleId : "/transports/" + props.id);
          this.popup?.remove();
        });
      list.append(control);
    }
    this.popup = new Popup({ maxWidth: "320px" })
      .setLngLat(coordinate)
      .setDOMContent(list)
      .addTo(this.map);
    list.querySelector("button")?.focus();
  }
  destroy() {
    for (const entry of this.markers.values()) entry.marker.remove();
    this.markers.clear();
    this.popup?.remove();
  }
}
