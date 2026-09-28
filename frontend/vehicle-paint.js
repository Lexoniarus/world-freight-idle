import { normalizeVehicleColor } from "./vehicle-color.js";

/** Multiply only explicit mask coverage; preserve every original alpha byte.
 * @param {Uint8ClampedArray} original @param {Uint8ClampedArray} mask
 * @param {string} color @returns {Uint8ClampedArray}
 */
export function paintPixels(original, mask, color) {
  if (original.length !== mask.length) throw new Error("Paint mask dimensions differ");
  const result = new Uint8ClampedArray(original);
  const safe = normalizeVehicleColor(color);
  const channels = [1, 3, 5].map((offset) => parseInt(safe.slice(offset, offset + 2), 16) / 255);
  for (let offset = 0; offset < original.length; offset += 4) {
    const coverage = ((mask[offset] / 255) * mask[offset + 3]) / 255;
    for (let channel = 0; channel < 3; channel++)
      result[offset + channel] =
        original[offset + channel] * (1 - coverage + coverage * channels[channel]);
  }
  return result;
}

/** Extract the direct original raster, excluding historical tint/filter nodes.
 * @param {string} source @returns {{svg: string, width: number, height: number}}
 */
export function originalVehicleSvg(source) {
  const root = source.match(/<svg\b[^>]*>/)?.[0] ?? "";
  const image = source.replace(/<defs\b[\s\S]*?<\/defs>/g, "").match(/<image\b[^>]*>/)?.[0] ?? "";
  const raster = image.match(/(?:href|xlink:href)="(data:image\/png;base64,[A-Za-z0-9+/=]+)"/)?.[1];
  if (!raster) throw new Error("Vehicle original raster missing");
  const width = Number(root.match(/\bwidth="([0-9]+)"/)?.[1]);
  const height = Number(root.match(/\bheight="([0-9]+)"/)?.[1]);
  if (!(width > 0 && height > 0)) throw new Error("Vehicle dimensions invalid");
  return {
    svg: `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><image width="${width}" height="${height}" href="${raster}"/></svg>`,
    width,
    height,
  };
}

/** Decode one owned SVG URL into pixels at the original dimensions.
 * @param {string} svg @param {number} width @param {number} height
 * @returns {Promise<ImageData>}
 */
async function readPixels(svg, width, height) {
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Vehicle paint canvas unavailable");
    context.drawImage(image, 0, 0, width, height);
    return context.getImageData(0, 0, width, height);
  } finally {
    URL.revokeObjectURL(url);
  }
}

/** Compose the original raster and an independently authored paint mask.
 * @param {string} source @param {string} mask @param {string} color
 * @returns {Promise<string>}
 */
export async function composeVehiclePaint(source, mask, color) {
  const { svg, width, height } = originalVehicleSvg(source);
  const [base, coverage] = await Promise.all([
    readPixels(svg, width, height),
    readPixels(mask, width, height),
  ]);
  base.data.set(paintPixels(base.data, coverage.data, color));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Vehicle paint canvas unavailable");
  context.putImageData(base, 0, 0);
  return `<svg xmlns="http://www.w3.org/2000/svg" style="--vehicle-color:${normalizeVehicleColor(color)}" width="${width}" height="${height}"><image width="${width}" height="${height}" href="${canvas.toDataURL("image/png")}"/></svg>`;
}
