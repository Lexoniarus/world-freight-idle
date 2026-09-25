export const ZOOM_TIERS = { regional: 7, assets: 12, expandLimit: 17 };
export const GROUP_RADIUS = 48;
export const GROUP_INTERVAL = 250;

/** Partition projected points without changing any geographic coordinate. */
export function groupVehicles(features, project, selected = "", enabled = true) {
  const groups = [];
  const cells = new Map();
  for (const feature of [...features].sort((a, b) =>
    String(a.properties.key).localeCompare(String(b.properties.key)),
  )) {
    const point = project(feature.geometry.coordinates);
    const x = Math.floor(point.x / GROUP_RADIUS);
    const y = Math.floor(point.y / GROUP_RADIUS);
    const own = Boolean(feature.properties.isOwn);
    const chosen =
      own && (feature.properties.id === selected || feature.properties.vehicleId === selected);
    let target;
    if (enabled && !chosen) {
      for (let dx = -1; dx <= 1; dx++)
        for (let dy = -1; dy <= 1; dy++) {
          const candidates = cells.get(`${own}:${x + dx}:${y + dy}`) ?? [];
          target ??= candidates.find(
            (group) => Math.hypot(group.point.x - point.x, group.point.y - point.y) < GROUP_RADIUS,
          );
        }
    }
    if (target) target.members.push(feature);
    else {
      const group = { point, members: [feature], own };
      groups.push(group);
      if (!chosen) {
        const key = `${own}:${x}:${y}`;
        if (!cells.has(key)) cells.set(key, []);
        cells.get(key).push(group);
      }
    }
  }
  return groups;
}
