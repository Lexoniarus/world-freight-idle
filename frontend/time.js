/** @param {number} seconds
 * @returns {string} */
export function formatDuration(seconds) {
  const totalMinutes = Math.max(0, Math.round(seconds / 60));
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  return [days ? `${days} T` : "", hours ? `${hours} h` : "", `${minutes} min`]
    .filter(Boolean)
    .join(" ");
}

/** @param {number} nowSeconds
 * @param {number} departedAt
 * @param {number} arrivesAt
 * @returns {number} */
export function routeProgress(nowSeconds, departedAt, arrivesAt) {
  if (arrivesAt <= departedAt) return 1;
  return Math.max(0, Math.min(1, (nowSeconds - departedAt) / (arrivesAt - departedAt)));
}
