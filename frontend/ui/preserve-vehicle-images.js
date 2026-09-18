/** Match unchanged media independently of the panel's transient render state.
 * @param {HTMLElement} currentContent
 * @param {DocumentFragment} nextContent
 * @returns {Array<{current: HTMLElement, next: HTMLElement}>}
 */
export function matchVehicleImages(currentContent, nextContent) {
  const available = [...currentContent.querySelectorAll(".vehicle-photo")];
  const matches = [];
  for (const next of nextContent.querySelectorAll(".vehicle-photo")) {
    if (!(next instanceof HTMLElement)) continue;
    const initialState = next.dataset.imageState;
    const index = available.findIndex((current) => {
      if (!(current instanceof HTMLElement)) return false;
      next.dataset.imageState = current.dataset.imageState;
      return current.isEqualNode(next);
    });
    if (index < 0) {
      next.dataset.imageState = initialState;
      continue;
    }
    const [current] = available.splice(index, 1);
    matches.push({ current: /** @type {HTMLElement} */ (current), next });
  }
  return matches;
}
