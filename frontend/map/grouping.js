import { vehicleFootprint, footprintsOverlap } from "./vehicle-footprint.js";
export const ZOOM_TIERS = { regional: 7, assets: 12, expandLimit: 17 };
const SCREEN_CELL_SIZE = 128;
export const GROUP_INTERVAL = 250;

/** Partition projected points without changing any geographic coordinate. */
export function groupVehicles(
  features,
  project,
  selected = "",
  enabled = true,
  zoom = 13,
  mapBearing = 0,
) {
  const groups = [];
  const cells = new Map();
  for (const feature of [...features].sort((a, b) =>
    String(a.properties.key).localeCompare(String(b.properties.key)),
  )) {
    const point = project(feature.geometry.coordinates);
    const x = Math.floor(point.x / SCREEN_CELL_SIZE);
    const y = Math.floor(point.y / SCREEN_CELL_SIZE);
    const footprint = vehicleFootprint(feature, point, zoom, mapBearing);
    const own = Boolean(feature.properties.isOwn);
    const owner = own ? "own" : feature.properties.username;
    const movement =
      feature.properties.movementState ?? (feature.properties.idle ? "idle" : "enroute");
    const partition = `${owner}:${movement}`;
    const chosen =
      own && (feature.properties.id === selected || feature.properties.vehicleId === selected);
    let target;
    if (enabled && !chosen) {
      for (let dx = -1; dx <= 1; dx++)
        for (let dy = -1; dy <= 1; dy++) {
          const candidates = cells.get(`${partition}:${x + dx}:${y + dy}`) ?? [];
          target ??= candidates.find((group) => footprintsOverlap(group.footprint, footprint));
        }
    }
    if (target) target.members.push(feature);
    else {
      const group = { point, footprint, members: [feature], own };
      groups.push(group);
      if (!chosen) {
        const key = `${partition}:${x}:${y}`;
        if (!cells.has(key)) cells.set(key, []);
        cells.get(key).push(group);
      }
    }
  }
  return groups;
}
