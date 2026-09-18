import { deflateSync } from "node:zlib";

// Deterministic PNG fixture. Tiles are generated locally, never downloaded.
function chunk(type, data) {
  const body = Buffer.concat([Buffer.from(type), data]);
  let crc = 0xffffffff;
  for (const byte of body) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  const length = Buffer.alloc(4); length.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4); checksum.writeUInt32BE((crc ^ 0xffffffff) >>> 0);
  return Buffer.concat([length, body, checksum]);
}
const header = Buffer.alloc(13);
header.writeUInt32BE(256, 0); header.writeUInt32BE(256, 4); header[8] = 8; header[9] = 2;
const pixels = Buffer.alloc(256 * (256 * 3 + 1));
for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) {
  const offset = y * 769 + 1 + x * 3;
  const road = x % 64 < 3 || y % 64 < 3;
  pixels[offset] = road ? 241 : 207;
  pixels[offset + 1] = road ? 241 : 219;
  pixels[offset + 2] = road ? 229 : 207;
}
export const tile = Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk("IHDR", header), chunk("IDAT", deflateSync(pixels)), chunk("IEND", Buffer.alloc(0))]);
