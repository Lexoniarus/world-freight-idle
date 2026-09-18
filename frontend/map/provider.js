/** Provider boundary: overlay code never depends on a tile vendor. */
export class BasemapProvider {
  /** @param {{tiles: string[], attribution: string, minZoom?: number, maxZoom?: number}} options */
  constructor({ tiles, attribution, minZoom = 0, maxZoom = 19 }) {
    this.tiles = tiles;
    this.attribution = attribution;
    this.minZoom = minZoom;
    this.maxZoom = maxZoom;
  }

  /** @returns {import("maplibre-gl").StyleSpecification} */
  style() {
    return {
      version: 8,
      sources: {
        basemap: {
          type: "raster",
          tiles: this.tiles,
          tileSize: 256,
          attribution: this.attribution,
          minzoom: this.minZoom,
          maxzoom: this.maxZoom,
        },
      },
      layers: [
        { id: "basemap", type: "raster", source: "basemap", paint: { "raster-saturation": -0.25 } },
      ],
    };
  }
}

/** @param {Record<string, string>} [env]
 * @returns {BasemapProvider} */
export function createBasemap(env = import.meta.env) {
  return new BasemapProvider({
    tiles: [env.VITE_MAP_TILE_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    attribution:
      env.VITE_MAP_ATTRIBUTION ||
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
    maxZoom: Number(env.VITE_MAP_MAX_ZOOM || 19),
  });
}
