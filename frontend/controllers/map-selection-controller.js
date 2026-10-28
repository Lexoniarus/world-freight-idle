/** Translate typed map selections into existing navigation workflows. */
export class MapSelectionController {
  /** @param {{map: EventTarget, navigate: import('../types.js').Navigate, notify: import('../types.js').Notify}} dependencies */
  constructor({ map, navigate, notify }) {
    this.map = map;
    this.navigate = navigate;
    this.notify = notify;
    this.selected = (event) => this.handle(/** @type {CustomEvent} */ (event).detail);
  }

  /** Subscribe to map-owned selection events. @returns {void} */
  start() {
    this.map.addEventListener("object-selected", this.selected);
  }

  /** Apply one map selection without reading renderer internals.
   * @param {import('../types.js').MapObjectSelection} selection
   * @returns {void}
   */
  handle(selection) {
    if (selection.kind === "own-vehicle") {
      this.navigate(
        selection.idle
          ? "/fleet/" + encodeURIComponent(selection.vehicleId)
          : "/transports/" + encodeURIComponent(selection.transportId),
      );
    } else if (selection.kind === "public-vehicle") {
      this.notify(
        `${selection.username || "Ein anderer Spieler"} · ${selection.modelName || "Fahrzeug"}`,
        "map",
      );
    } else {
      const path = selection.parked ? "/fleet" : "/contracts";
      const vehicle = selection.vehicleId
        ? "&vehicle=" + encodeURIComponent(selection.vehicleId)
        : "";
      this.navigate(`${path}?city=${encodeURIComponent(selection.cityUid)}${vehicle}`);
    }
  }

  /** Release the map subscription. @returns {void} */
  destroy() {
    this.map.removeEventListener("object-selected", this.selected);
  }
}
