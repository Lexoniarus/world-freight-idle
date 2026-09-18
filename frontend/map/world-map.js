import * as maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { nearestLongitude, unwrapRoute } from "../geometry.js";
import { OverlayData, previewFeatures, routeGeometry } from "./overlay-data.js";
import { addOverlayLayers, updateHubLabel } from "./layers.js";
import { MapCamera } from "./camera.js";
import { VehicleAnimator } from "./vehicle-animator.js";

const HIT_LAYERS = ["vehicles", "orders", "parked", "hub-points", "hub-clusters"];

/** Own the MapLibre lifecycle and translate map interactions into navigation. */
export class WorldMap {
  /** @param {string} container
   * @param {{navigate: import('../types.js').Navigate, notify: import('../types.js').Notify, now: import('../types.js').Clock, provider: import("./provider.js").BasemapProvider, viewport: () => {width: number, height: number, panelOpen: boolean}, reducedMotion: () => boolean, isHidden: () => boolean}} dependencies */
  constructor(container, { navigate, notify, now, provider, viewport, reducedMotion, isHidden }) {
    this.navigate = navigate;
    this.notify = notify;
    this.now = now;
    this.reducedMotion = reducedMotion;
    this.overlays = new OverlayData();
    this.selected = "";
    this.visible = { hubs: true, orders: true, vehicles: true, routes: true };
    this.ready = false;
    this.disposed = false;
    this.preview = null;
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
    this.camera = new MapCamera(this.map, reducedMotion, viewport);
    this.animator = new VehicleAnimator({
      draw: () => this.setSourceData("vehicles", this.overlays.vehicleFeatures(this.now())),
      isActive: () => this.overlays.state.transports.length > 0,
      isHidden,
      reducedMotion,
    });
    this.map.touchZoomRotate.disableRotation();
    this.map.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-left");
    this.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
    this.bindMapEvents();
  }
  /** Attach map-owned listeners, released together by MapLibre.remove(). */
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
    this.map.on("click", (event) => {
      void this.selectFeature(event).catch(() => {
        if (!this.disposed) this.notify("Kartenobjekt konnte nicht ausgewählt werden.", "map");
      });
    });
    this.map.on("mousemove", (event) => {
      if (this.ready)
        this.map.getCanvas().style.cursor = this.map.queryRenderedFeatures(event.point, {
          layers: HIT_LAYERS,
        }).length
          ? "pointer"
          : "";
    });
  }
  /** Initialize sources after the basemap is ready and replay pending state. */
  initializeOverlays() {
    if (this.disposed) return;
    addOverlayLayers(this.map);
    this.ready = true;
    this.map.getContainer().setAttribute("aria-busy", "false");
    this.update(this.overlays.state);
    for (const [name, visible] of Object.entries(this.visible)) this.toggle(name, visible);
    this.setPreview(this.preview);
    this.select(this.selected);
    this.animator.start();
  }
  /** Supply resolved public freight locations.
   * @param {import('../types.js').Hub[]} hubs
   */
  setHubs(hubs) {
    this.overlays.setHubs(hubs);
    this.update(this.overlays.state);
  }
  /** Publish one server snapshot to the independent overlay sources.
   * @param {import('../types.js').MapState} state
   */
  update(state) {
    this.overlays.update(state);
    if (!this.ready || this.disposed) return;
    for (const hub of this.overlays.hubs) updateHubLabel(this.map, hub, state);
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
    this.setSourceData("vehicles", this.overlays.vehicleFeatures(this.now()));
  }
  /** Update one registered GeoJSON source.
   * @param {string} name
   * @param {import("geojson").FeatureCollection} data
   */
  setSourceData(name, data) {
    /** @type {import("maplibre-gl").GeoJSONSource} */ (this.map.getSource(name))?.setData(data);
  }
  /** Expand a cluster or navigate to the selected game resource.
   * @param {import("maplibre-gl").MapMouseEvent} event
   */
  async selectFeature(event) {
    if (!this.ready || this.disposed) return;
    const feature = this.map.queryRenderedFeatures(event.point, { layers: HIT_LAYERS })[0];
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
    } else if (feature.layer.id === "vehicles")
      this.navigate("/transports/" + encodeURIComponent(feature.properties.id));
    else
      this.navigate(
        (feature.layer.id === "parked" ? "/fleet" : "/contracts") +
          "?hub=" +
          encodeURIComponent(feature.properties.id),
      );
  }
  /** Display or clear a non-authoritative quote preview.
   * @param {import("../types.js").Quote | null} quote
   */
  setPreview(quote) {
    this.preview = quote;
    if (this.ready && !this.disposed) this.setSourceData("preview", previewFeatures(quote));
  }
  /** Highlight the selected transport route.
   * @param {string} id
   */
  select(id) {
    this.selected = id;
    if (!this.ready || this.disposed) return;
    this.map.setPaintProperty("routes", "line-color", [
      "case",
      ["==", ["get", "id"], id],
      "#f6bc43",
      "#267e9a",
    ]);
    this.map.setPaintProperty("routes", "line-width", ["case", ["==", ["get", "id"], id], 6, 3]);
  }
  /** Frame a selected route in the nearest world copy.
   * @param {import("../types.js").RouteGeometry} route
   */
  focusRoute(route) {
    this.camera.fitRoute(unwrapRoute(routeGeometry(route).coordinates));
  }
  /** Frame all known parked and moving vehicles. */
  focusFleet() {
    const points = this.overlays.fleetCoordinates(this.now());
    if (points.length) this.camera.fitCoordinates(points);
    else this.notify("Die Standorte deiner Flotte werden noch geladen.");
  }
  /** Toggle the display layers belonging to one logical overlay.
   * @param {string} name
   * @param {boolean} visible
   */
  toggle(name, visible) {
    this.visible[name] = visible;
    const layers =
      name === "hubs"
        ? ["hub-clusters", "hub-points", "hub-labels"]
        : name === "vehicles"
          ? ["vehicles", "parked"]
          : [name];
    for (const layer of layers)
      if (this.map.getLayer(layer))
        this.map.setLayoutProperty(layer, "visibility", visible ? "visible" : "none");
  }
  /** Release the renderer, its listeners and the shared animation loop. */
  destroy() {
    if (this.disposed) return;
    this.disposed = true;
    this.animator.destroy();
    this.map.remove();
  }
}
