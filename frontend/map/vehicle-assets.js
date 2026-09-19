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

/** Resolve a database vehicle model to its shipped map asset.
 * @param {string | undefined} modelId
 * @returns {string | null} */
export function vehicleAssetPath(modelId) {
  return modelId ? (VEHICLE_MAP_ASSETS[modelId] ?? null) : null;
}

/** Return the MapLibre image identifier for one supported vehicle model.
 * @param {string | undefined} modelId
 * @returns {string} */
export function vehicleIconId(modelId) {
  return vehicleAssetPath(modelId) ? `vehicle-${modelId}` : "";
}

/** Replace the generated SVG paint variable with a validated player color.
 * @param {string} svgText
 * @param {string} color
 * @returns {string} */
export function colorizeVehicleSvg(svgText, color) {
  const safeColor = SAFE_COLOR.test(color) ? color : DEFAULT_VEHICLE_COLOR;
  return svgText.replace(/--vehicle-color\s*:\s*#[0-9a-f]{6}/i, `--vehicle-color:${safeColor}`);
}

/** Rasterize one self-contained SVG into the small image MapLibre keeps in its atlas.
 * Dependencies are injectable so the rendering boundary remains unit-testable.
 * @param {string} svgText
 * @param {{height?: number, imageFactory?: () => HTMLImageElement, canvasFactory?: () => HTMLCanvasElement, createObjectURL?: (blob: Blob) => string, revokeObjectURL?: (url: string) => void}} [options]
 * @returns {Promise<ImageData>} */
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

/** Register all shipped map sprites once and return the models that loaded successfully.
 * @param {import("maplibre-gl").Map} map
 * @param {(path: string) => Promise<string>} loadAsset
 * @param {{color?: string, rasterize?: typeof rasterizeVehicleSvg}} [options]
 * @returns {Promise<Set<string>>} */
export async function registerVehicleIcons(map, loadAsset, options = {}) {
  const color = options.color ?? DEFAULT_VEHICLE_COLOR;
  const rasterize = options.rasterize ?? rasterizeVehicleSvg;
  const registered = new Set();
  for (const [modelId, path] of Object.entries(VEHICLE_MAP_ASSETS)) {
    const imageId = vehicleIconId(modelId);
    if (map.hasImage(imageId)) {
      registered.add(modelId);
      continue;
    }
    try {
      const source = await loadAsset(path);
      const image = await rasterize(colorizeVehicleSvg(source, color));
      map.addImage(imageId, image, { pixelRatio: 2 });
      registered.add(modelId);
    } catch (error) {
      console.warn(`Vehicle map asset unavailable: ${modelId}`, error);
    }
  }
  return registered;
}
