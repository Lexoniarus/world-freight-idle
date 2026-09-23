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

/** Format remaining pause time, retaining seconds for accelerated games.
 * @param {number} seconds
 * @returns {string}
 */
export function formatCountdown(seconds) {
  return seconds < 60 ? `${Math.max(0, Math.ceil(seconds))} s` : formatDuration(seconds);
}
