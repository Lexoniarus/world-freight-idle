import { Marker, Popup } from "maplibre-gl";
import { nearestLongitude } from "../geometry.js";
import { groupVehicles, GROUP_INTERVAL, ZOOM_TIERS } from "./grouping.js";

/** Render accessible count markers independently of the movement frame loop. */
export class VehicleGroups {
  /** @param {import("maplibre-gl").Map} map
   * @param {import("../types.js").Navigate} navigate
   * @param {() => boolean} reducedMotion
   */
  constructor(map, navigate, reducedMotion) {
    this.signature = "";
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
    const signature =
      features
        .map(
          (feature) =>
            `${feature.properties.key}:${feature.properties.movementState ?? feature.properties.idle}:${feature.properties.iconImage}:${feature.properties.hasIcon}`,
        )
        .sort()
        .join("|") +
      ":" +
      selected +
      ":" +
      this.enabled;
    if (
      !force &&
      signature === this.signature &&
      time - this.last < (this.reducedMotion() ? 1000 : GROUP_INTERVAL)
    ) {
      this.updatePoses(features);
      return features.filter((feature) => !this.hidden.has(feature.properties.key));
    }
    this.signature = signature;
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
      this.map.getZoom(),
      this.map.getBearing(),
    );
    const active = new Set();
    this.hidden.clear();
    for (const group of groups.filter((item) => item.members.length > 1)) {
      const key = group.members[0].properties.key;
      active.add(key);
      for (const item of group.members.slice(1)) this.hidden.add(item.properties.key);
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
      this.renderVisual(entry.button, group.members);
      entry.button.setAttribute(
        "aria-label",
        `${group.members.length} ${group.own ? "eigene" : "fremde"} ${group.members[0].properties.idle ? "einsatzbereite" : "fahrende"} Fahrzeuge – Gruppe öffnen`,
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
  /** Update current representative coordinates independently of regrouping. */
  updatePoses(features) {
    const current = new Map(features.map((feature) => [feature.properties.key, feature]));
    for (const [key, entry] of this.markers) {
      entry.members = entry.members.map((member) => current.get(member.properties.key) ?? member);
      const coordinate = current.get(key)?.geometry.coordinates;
      if (coordinate)
        entry.marker.setLngLat([
          nearestLongitude(coordinate[0], this.map.getCenter().lng),
          coordinate[1],
        ]);
    }
  }
  /** Render only the badge; the representative uses the normal symbol layer. */
  renderVisual(button, members) {
    const props = members[0].properties;
    button.style.setProperty("--company-color", props.playerColor);
    button.dataset.representative = props.key;
    button.dataset.movement = props.movementState ?? (props.idle ? "idle" : "enroute");
    const count = String(members.length);
    if (button.textContent === count) return;
    const badge = document.createElement("span");
    badge.className = "vehicle-group-count";
    badge.textContent = count;
    button.replaceChildren(badge);
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
