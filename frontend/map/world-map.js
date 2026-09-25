import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { nearestLongitude, unwrapRoute } from "../geometry.js";
import { OverlayData, previewFeatures, routeGeometry } from "./overlay-data.js";
import { addOverlayLayers } from "./layers.js";
import { MapCamera } from "./camera.js";
import { VehicleAnimator } from "./vehicle-animator.js";
import { VehicleIconRegistry } from "./vehicle-assets.js";
import { selectedLocations } from "./selection.js";
import { Opportunities } from "./opportunities.js";
import { VehicleGroups } from "./vehicle-groups.js";

const OWN_VEHICLE_LAYERS = ["vehicles", "vehicles-fallback"];
const MULTIPLAYER_VEHICLE_LAYERS = ["multiplayer-vehicles", "multiplayer-vehicles-fallback"];
const HIT_LAYERS = [
  ...OWN_VEHICLE_LAYERS,
  ...MULTIPLAYER_VEHICLE_LAYERS,
  "orders",
  "parked",
  "hub-points",
  "hub-clusters",
];
const FACILITY_HOVER_LAYERS = new Set(["orders", "parked", "hub-points"]);

export class WorldMap {
  constructor(
    container,
    { navigate, notify, now, loadAsset, provider, viewport, reducedMotion, isHidden },
  ) {
    this.navigate = navigate;
    this.notify = notify;
    this.now = now;
    this.reducedMotion = reducedMotion;
    this.isHidden = isHidden;
    this.overlays = new OverlayData();
    this.selected = "";
    this.visible = {
      hubs: true,
      orders: true,
      vehicles: true,
      multiplayer: true,
      routes: true,
    };
    this.ready = false;
    this.disposed = false;
    this.preview = null;
    this.hoverPopup = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 14,
    });
    maplibregl.setWorkerUrl(workerUrl);
    this.map = new maplibregl.Map({
      container,
      style: provider.style(),
      center: [13.34, 52.53],
      zoom: 11,
      renderWorldCopies: true,
      minZoom: Math.max(1, provider.minZoom),
      maxZoom: provider.maxZoom,
      attributionControl: false,
      canvasContextAttributes: { antialias: true },
      dragRotate: false,
      pitchWithRotate: false,
    });
    this.vehicleIcons = new VehicleIconRegistry(this.map, loadAsset);
    this.camera = new MapCamera(this.map, reducedMotion, viewport);
    this.animator = new VehicleAnimator({
      draw: () => this.drawTraffic(),
      isActive: () => (this.overlays.state.traffic ?? []).length > 0,
      isHidden,
      reducedMotion,
    });
    this.map.touchZoomRotate.disableRotation();
    this.groups = new VehicleGroups(this.map, navigate, reducedMotion);
    this.opportunities = new Opportunities(this.map, navigate);
    this.map.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-left");
    this.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    this.bindMapEvents();
  }

  bindMapEvents() {
    this.map.on("error", (event) => {
      console.warn("Map rendering:", event.error?.message);
      if (!this.disposed)
        this.notify(
          "Kartenquelle momentan nicht erreichbar. Deine Spielaktionen bleiben verfügbar.",
          "map",
        );
    });
    this.map.on("load", () => this.initializeOverlays());
    this.map.on("moveend", () => {
      if (this.ready) {
        this.groups.last = -Infinity;
        this.drawTraffic();
        this.opportunities.update(
          this.overlays.state.contracts,
          this.visible.orders,
          this.selected,
        );
      }
    });
    this.map.on("click", (event) => {
      void this.selectFeature(event).catch(() => {
        if (!this.disposed) this.notify("Kartenobjekt konnte nicht ausgewählt werden.", "map");
      });
    });
    this.map.on("mousemove", (event) => {
      if (!this.ready) return;
      const feature = this.map.queryRenderedFeatures(event.point, {
        layers: HIT_LAYERS,
      })[0];
      this.map.getCanvas().style.cursor = feature ? "pointer" : "";
      this.updateFacilityHover(feature, event.lngLat);
    });
  }

  initializeOverlays() {
    if (this.disposed) return;
    addOverlayLayers(this.map);
    this.ready = true;
    this.map.getContainer().setAttribute("aria-busy", "false");
    this.update(this.overlays.state);
    for (const [name, visible] of Object.entries(this.visible)) this.toggle(name, visible);
    this.setPreview(this.preview);
    this.select(this.selected, this.selectedContract);
    this.setPreset(this.preset ?? "world");
    this.animator.start();
  }

  update(state) {
    this.overlays.update(state);
    if (!this.ready || this.disposed) return;
    this.setSourceData("hubs", this.overlays.hubFeatures());
    this.setSourceData("orders", this.overlays.locationFeatures(state.contracts, "origin_hub_id"));
    this.setSourceData(
      "parked",
      this.overlays.locationFeatures(
        state.vehicles.filter((vehicle) => vehicle.status === "idle"),
        "hub_id",
      ),
    );
    this.setSourceData("routes", this.overlays.routeFeatures());
    this.updateSelectedRoute();
    this.setSourceData(
      "selected-locations",
      selectedLocations(this.overlays.state, this.selected, this.selectedContract),
    );
    this.drawTraffic();
    this.opportunities.update(state.contracts, this.visible.orders, this.selected);
    void this.syncVehicleIcons([
      ...(state.traffic ?? []),
      ...state.vehicles.map((vehicle) => ({ model_id: vehicle.model_id, player_color: "#f6bc43" })),
    ]);
  }

  updateFacilityHover(feature, lngLat) {
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
    detail.textContent = `${city} · ${trucks} Lkw · ${orders == null ? "Auftragszahl unbekannt" : orders + " Aufträge"}`;
    content.append(title, detail);
    this.hoverPopup.setLngLat(lngLat).setDOMContent(content).addTo(this.map);
  }

  async syncVehicleIcons(traffic) {
    const imageIds = await this.vehicleIcons.ensure(traffic);
    if (this.disposed) return;
    this.overlays.setVehicleIcons(imageIds);
    this.drawTraffic();
  }

  drawTraffic() {
    if (this.disposed || !this.ready || this.isHidden()) return;
    const now = this.now();
    const own = this.overlays.vehicleFeatures(now).features;
    const other = this.overlays.multiplayerVehicleFeatures(now).features;
    const visible = [
      ...(this.visible.vehicles
        ? own.filter((item) => this.preset !== "contracts" || item.properties.idle)
        : []),
      ...(this.visible.multiplayer ? other : []),
    ];
    const ungrouped = this.groups.update(visible, this.selected);
    this.setSourceData("vehicles", {
      type: "FeatureCollection",
      features: ungrouped.filter((item) => item.properties.isOwn),
    });
    this.setSourceData("multiplayer-vehicles", {
      type: "FeatureCollection",
      features: ungrouped.filter((item) => !item.properties.isOwn),
    });
    this.setSourceData("selection", {
      type: "FeatureCollection",
      features: own.filter(
        (item) =>
          item.properties.id === this.selected || item.properties.vehicleId === this.selected,
      ),
    });
  }

  setGrouping(value) {
    this.groups.enabled = value;
    this.groups.last = -Infinity;
    if (this.ready) this.drawTraffic();
  }

  setPreset(preset) {
    this.preset = preset;
    if (!this.ready) return;
    const opacity = preset === "leaderboard" ? 0.95 : 0.45;
    this.map.setPaintProperty("multiplayer-vehicles-fallback", "circle-opacity", opacity);
    this.map.setPaintProperty("vehicles", "icon-opacity", preset === "company" ? 0.65 : 1);
    this.groups.last = -Infinity;
    this.drawTraffic();
    this.map.setPaintProperty("multiplayer-vehicles", "icon-opacity", opacity);
  }

  setSourceData(name, data) {
    /** @type {import("maplibre-gl").GeoJSONSource} */ (this.map.getSource(name))?.setData(data);
  }

  async selectFeature(event) {
    if (!this.ready || this.disposed) return;
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
      const zoom = await /** @type {import("maplibre-gl").GeoJSONSource} */ (
        this.map.getSource("hubs")
      ).getClusterExpansionZoom(feature.properties.cluster_id);
      if (this.disposed) return;
      const [lon, lat] = /** @type {import("geojson").Point} */ (feature.geometry).coordinates;
      this.map.easeTo({
        center: [nearestLongitude(lon, event.lngLat.lng), lat],
        zoom,
        duration: this.reducedMotion() ? 0 : 500,
      });
    } else if (OWN_VEHICLE_LAYERS.includes(feature.layer.id)) {
      this.navigate(
        feature.properties.idle
          ? "/fleet/" + encodeURIComponent(feature.properties.vehicleId)
          : "/transports/" + encodeURIComponent(feature.properties.id),
      );
    } else if (MULTIPLAYER_VEHICLE_LAYERS.includes(feature.layer.id)) {
      this.notify(
        `${feature.properties.username || "Ein anderer Spieler"} · ${feature.properties.modelName || "Fahrzeug"}`,
        "map",
      );
    } else {
      this.navigate(
        (feature.layer.id === "parked" ? "/fleet" : "/contracts") +
          "?city=" +
          encodeURIComponent(feature.properties.cityUid ?? ""),
      );
    }
  }

  setPreview(quote) {
    this.preview = quote;
    if (this.ready)
      this.map.setLayoutProperty(
        "preview",
        "visibility",
        quote || this.visible.preview ? "visible" : "none",
      );
    if (this.ready && !this.disposed) this.setSourceData("preview", previewFeatures(quote));
  }

  select(id, contract = null) {
    this.selected = id;
    this.selectedContract = contract;
    if (!this.ready || this.disposed) return;
    this.groups.last = -Infinity;
    this.drawTraffic();
    this.updateSelectedRoute();
    this.opportunities.update(this.overlays.state.contracts, this.visible.orders, id);
    this.setSourceData("selected-locations", selectedLocations(this.overlays.state, id, contract));
    this.map.setPaintProperty("routes", "line-color", [
      "case",
      ["==", ["get", "id"], id],
      "#f6bc43",
      "#267e9a",
    ]);
    this.map.setPaintProperty("routes", "line-width", ["case", ["==", ["get", "id"], id], 6, 3]);
  }

  updateSelectedRoute() {
    const trip = this.overlays.state.transports.find(
      (item) => item.id === this.selected || item.vehicle_id === this.selected,
    );
    this.setSourceData("selected-route", {
      type: "FeatureCollection",
      features: this.overlays
        .routeFeatures()
        .features.filter((item) => item.properties.id === trip?.id),
    });
  }

  focusRoute(route) {
    this.camera.fitRoute(unwrapRoute(routeGeometry(route).coordinates));
  }

  focusFleet() {
    const points = this.overlays.fleetCoordinates(this.now());
    if (points.length) this.camera.fitCoordinates(points);
    else this.notify("Die Standorte deiner Flotte werden noch geladen.");
  }

  toggle(name, visible) {
    this.visible[name] = visible;
    const layers =
      name === "hubs"
        ? ["hub-clusters", "hub-points"]
        : name === "vehicles"
          ? [...OWN_VEHICLE_LAYERS, "parked"]
          : name === "multiplayer"
            ? MULTIPLAYER_VEHICLE_LAYERS
            : [name];
    const rendered = visible || (name === "preview" && Boolean(this.preview));
    for (const layer of layers)
      if (this.map.getLayer(layer))
        this.map.setLayoutProperty(layer, "visibility", rendered ? "visible" : "none");
    if (this.ready) {
      this.groups.last = -Infinity;
      this.drawTraffic();
      this.opportunities.update(this.overlays.state.contracts, this.visible.orders, this.selected);
    }
  }

  destroy() {
    if (this.disposed) return;
    this.disposed = true;
    this.animator.destroy();
    this.groups.destroy();
    this.opportunities.destroy();
    this.hoverPopup.remove();
    this.map.remove();
  }
}
