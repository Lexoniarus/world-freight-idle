/** Format integer game euros for display.
 * @param {number} value
 * @returns {string}
 */
export const money = (value) =>
  new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value || 0);
/** Format a measurement for display.
 * @param {number} [maximumFractionDigits]
 * @param {number} value
 * @returns {string}
 */
export const number = (value, maximumFractionDigits = 1) =>
  new Intl.NumberFormat("de-DE", { maximumFractionDigits }).format(value || 0);
