import * as maplibregl from "maplibre-gl";
import { nearestLongitude } from "../geometry.js";

export const OWN_VEHICLE_LAYERS = ["vehicles", "vehicles-idle", "vehicles-fallback"];
export const MULTIPLAYER_VEHICLE_LAYERS = [
  "multiplayer-vehicles",
  "multiplayer-vehicles-idle",
  "multiplayer-vehicles-fallback",
];

const HIT_LAYERS = [
  ...OWN_VEHICLE_LAYERS,
  ...MULTIPLAYER_VEHICLE_LAYERS,
  "orders",
  "parked",
  "hub-points",
  "hub-clusters",
];
const FACILITY_HOVER_LAYERS = new Set(["orders", "parked", "hub-points"]);

export class MapInteractions {
  /** @param {{
   * map: import("maplibre-gl").Map,
   * notify: (message: string, source?: string) => void,
   * reducedMotion: () => boolean,
   * isReady: () => boolean,
   * groups: import("./vehicle-groups.js").VehicleGroups,
   * emitSelection: (selection: import("../types.js").MapObjectSelection) => void,
   * }} dependencies
   */
  constructor({ map, notify, reducedMotion, isReady, groups, emitSelection }) {
    this.map = map;
    this.notify = notify;
    this.reducedMotion = reducedMotion;
    this.isReady = isReady;
    this.groups = groups;
    this.emitSelection = emitSelection;
    this.hoverPopup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 14,
    });
    this.handleClick = (event) => {
      void this.selectFeature(event).catch(() => {
        if (this.isReady()) this.notify("Kartenobjekt konnte nicht ausgewählt werden.", "map");
      });
    };
    this.handleMouseMove = (event) => this.updateHover(event);
    this.map.on("click", this.handleClick);
    this.map.on("mousemove", this.handleMouseMove);
  }

  /** Project the hovered facility into the owned popup.
   * @param {import("maplibre-gl").MapMouseEvent} event
   * @returns {void}
   */
  updateHover(event) {
    if (!this.isReady()) return;
    const feature = this.map.queryRenderedFeatures(event.point, {
      layers: HIT_LAYERS,
    })[0];
    this.map.getCanvas().style.cursor = feature ? "pointer" : "";
    if (!feature || !FACILITY_HOVER_LAYERS.has(feature.layer.id)) {
      this.hoverPopup.remove();
      return;
    }
    const content = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = feature.properties.label || "Frachtstandort";
    const detail = document.createElement("div");
    const city = feature.properties.city || "";
    const trucks = Number(feature.properties.idleTruckCount || 0);
    const orders = feature.properties.orderCount;
    detail.textContent = `${city} · ${trucks} Lkw · ${
      orders == null ? "Auftragszahl unbekannt" : orders + " Aufträge"
    }`;
    content.append(title, detail);
    this.hoverPopup.setLngLat(event.lngLat).setDOMContent(content).addTo(this.map);
  }

  /** Translate a map hit into navigation or group interaction.
   * @param {import("maplibre-gl").MapMouseEvent} event
   * @returns {Promise<void>}
   */
  async selectFeature(event) {
    if (!this.isReady()) return;
    const hits = this.map.queryRenderedFeatures(event.point, { layers: HIT_LAYERS });
    const vehicleHits = [
      ...new Map(
        hits
          .filter((item) =>
            [...OWN_VEHICLE_LAYERS, ...MULTIPLAYER_VEHICLE_LAYERS].includes(item.layer.id),
          )
          .map((item) => [item.properties.key, item]),
      ).values(),
    ];
    if (vehicleHits.length > 1) {
      this.groups.showList(vehicleHits, event.lngLat);
      return;
    }
    const feature = hits[0];
    if (!feature) return;
    if (feature.properties.cluster) {
      const source = /** @type {import("maplibre-gl").GeoJSONSource} */ (
        this.map.getSource("hubs")
      );
      const zoom = await source.getClusterExpansionZoom(feature.properties.cluster_id);
      if (!this.isReady()) return;
      const [lon, lat] = /** @type {import("geojson").Point} */ (feature.geometry).coordinates;
      this.map.easeTo({
        center: [nearestLongitude(lon, event.lngLat.lng), lat],
        zoom,
        duration: this.reducedMotion() ? 0 : 500,
      });
    } else if (OWN_VEHICLE_LAYERS.includes(feature.layer.id)) {
      this.emitSelection({
        kind: "own-vehicle",
        idle: Boolean(feature.properties.idle),
        vehicleId: feature.properties.vehicleId,
        transportId: feature.properties.id,
      });
    } else if (MULTIPLAYER_VEHICLE_LAYERS.includes(feature.layer.id)) {
      this.emitSelection({
        kind: "public-vehicle",
        username: feature.properties.username,
        modelName: feature.properties.modelName,
      });
    } else {
      this.emitSelection({
        kind: "facility",
        cityUid: feature.properties.cityUid ?? "",
        parked: feature.layer.id === "parked",
      });
    }
  }

  /** Release popup and native map listeners.
   * @returns {void}
   */
  destroy() {
    this.map.off("click", this.handleClick);
    this.map.off("mousemove", this.handleMouseMove);
    this.hoverPopup.remove();
  }
}
