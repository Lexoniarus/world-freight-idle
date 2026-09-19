const VEHICLE_MAP_ASSETS = Object.freeze({
  daf_xg_plus_480: "/assets/daf_xg_plus_480_map.svg",
  iveco_sway_500: "/assets/iveco_s_way_500_xc13_map.svg",
  man_tgx_520: "/assets/man_tgx_520_d3066_map.svg",
  mercedes_actros_l_380: "/assets/mercedes_benz_actros_l_om473_380kw_map.svg",
  mercedes_eactros_600: "/assets/mercedes_benz_eactros_600_3pack_lfp_map.svg",
  renault_t_high_520: "/assets/renault_trucks_t_high_520_de13_map.svg",
  scania_r460_gas: "/assets/scania_r_460_gas_cbg_lbg_map.svg",
  volvo_fh_aero_500_isave: "/assets/volvo_trucks_fh_aero_500_i_save_map.svg",
  mercedes_sprinter_317_cdi: "/assets/mercedes_benz_sprinter_317_cdi_35t_l3h2_9g_tronic_map.svg",
  vw_crafter_35_130kw: "/assets/volkswagen_crafter_35_2_0_tdi_130kw_l3h3_map.svg",
});

export const DEFAULT_VEHICLE_COLOR = "#f6bc43";
const SAFE_COLOR = /^#[0-9a-f]{6}$/i;

/** Normalize untrusted map color input to one supported hex value.
 * @param {string | undefined} color
 * @returns {string}
 */
export function normalizeVehicleColor(color) {
  return color && SAFE_COLOR.test(color) ? color.toLowerCase() : DEFAULT_VEHICLE_COLOR;
}

/** Resolve a database vehicle model to its shipped map asset.
 * @param {string | undefined} modelId
 * @returns {string | null}
 */
export function vehicleAssetPath(modelId) {
  return modelId ? (VEHICLE_MAP_ASSETS[modelId] ?? null) : null;
}

/** Return the MapLibre image identifier for one model/player color pair.
 * @param {string | undefined} modelId
 * @param {string | undefined} color
 * @returns {string}
 */
export function vehicleIconId(modelId, color = DEFAULT_VEHICLE_COLOR) {
  if (!vehicleAssetPath(modelId)) return "";
  const suffix = normalizeVehicleColor(color).slice(1);
  return `vehicle-${modelId}-${suffix}`;
}

/** Replace the generated SVG paint variable with a validated player color.
 * @param {string} svgText
 * @param {string} color
 * @returns {string}
 */
export function colorizeVehicleSvg(svgText, color) {
  const safeColor = normalizeVehicleColor(color);
  return svgText.replace(/--vehicle-color\s*:\s*#[0-9a-f]{6}/i, `--vehicle-color:${safeColor}`);
}

/** Rasterize one self-contained SVG into the small image MapLibre keeps in its atlas.
 * Dependencies are injectable so the rendering boundary remains unit-testable.
 * @param {string} svgText
 * @param {{height?: number, imageFactory?: () => HTMLImageElement, canvasFactory?: () => HTMLCanvasElement, createObjectURL?: (blob: Blob) => string, revokeObjectURL?: (url: string) => void}} [options]
 * @returns {Promise<ImageData>}
 */
export async function rasterizeVehicleSvg(svgText, options = {}) {
  const targetHeight = options.height ?? 128;
  const imageFactory = options.imageFactory ?? (() => new Image());
  const canvasFactory = options.canvasFactory ?? (() => document.createElement("canvas"));
  const createObjectURL = options.createObjectURL ?? ((blob) => URL.createObjectURL(blob));
  const revokeObjectURL = options.revokeObjectURL ?? ((url) => URL.revokeObjectURL(url));
  const url = createObjectURL(new Blob([svgText], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const image = imageFactory();
    image.src = url;
    await image.decode();
    const ratio = image.naturalHeight ? image.naturalWidth / image.naturalHeight : 1;
    const width = Math.max(1, Math.round(targetHeight * ratio));
    const canvas = canvasFactory();
    canvas.width = width;
    canvas.height = targetHeight;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Vehicle sprite canvas unavailable");
    context.clearRect(0, 0, width, targetHeight);
    context.drawImage(image, 0, 0, width, targetHeight);
    return context.getImageData(0, 0, width, targetHeight);
  } finally {
    revokeObjectURL(url);
  }
}

/** Cache source SVGs and colored MapLibre images across polling updates. */
export class VehicleIconRegistry {
  /** @param {import("maplibre-gl").Map} map
   * @param {(path: string) => Promise<string>} loadAsset
   * @param {{rasterize?: typeof rasterizeVehicleSvg}} [options]
   */
  constructor(map, loadAsset, options = {}) {
    this.map = map;
    this.loadAsset = loadAsset;
    this.rasterize = options.rasterize ?? rasterizeVehicleSvg;
    /** @type {Map<string, Promise<string>>} */
    this.sources = new Map();
    /** @type {Map<string, Promise<void>>} */
    this.pending = new Map();
    this.registered = new Set();
  }

  /** Ensure every visible model/color combination exists in the sprite atlas.
   * @param {import("../types.js").PublicTransport[]} transports
   * @returns {Promise<Set<string>>}
   */
  async ensure(transports) {
    const requests = new Map();
    for (const transport of transports) {
      const path = vehicleAssetPath(transport.model_id);
      if (!path) continue;
      const color = normalizeVehicleColor(transport.player_color);
      requests.set(vehicleIconId(transport.model_id, color), {
        modelId: transport.model_id,
        color,
        path,
      });
    }
    await Promise.all([...requests.values()].map((request) => this.register(request)));
    return new Set(this.registered);
  }

  /** Register one unique vehicle model/color pair exactly once.
   * @param {{modelId: string, color: string, path: string}} request
   * @returns {Promise<void>}
   */
  async register(request) {
    const imageId = vehicleIconId(request.modelId, request.color);
    if (this.map.hasImage(imageId)) {
      this.registered.add(imageId);
      return;
    }
    const existing = this.pending.get(imageId);
    if (existing) return existing;
    const task = this.loadAndRegister(imageId, request).finally(() => {
      this.pending.delete(imageId);
    });
    this.pending.set(imageId, task);
    return task;
  }

  /** Fetch an SVG source once, recolor it, rasterize it and add it to MapLibre.
   * @param {string} imageId
   * @param {{modelId: string, color: string, path: string}} request
   */
  async loadAndRegister(imageId, request) {
    try {
      let sourcePromise = this.sources.get(request.path);
      if (!sourcePromise) {
        sourcePromise = this.loadAsset(request.path);
        this.sources.set(request.path, sourcePromise);
      }
      const source = await sourcePromise;
      const image = await this.rasterize(colorizeVehicleSvg(source, request.color));
      if (!this.map.hasImage(imageId)) this.map.addImage(imageId, image, { pixelRatio: 2 });
      this.registered.add(imageId);
    } catch (error) {
      console.warn(`Vehicle map asset unavailable: ${request.modelId} ${request.color}`, error);
    }
  }
}
