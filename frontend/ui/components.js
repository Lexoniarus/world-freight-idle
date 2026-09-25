import { html } from "./dom.js";
import { icon } from "./illustrations.js";

/** Create an internal navigation link.
 * @param {string} path
 * @param {import("../types.js").DomValue} label
 * @param {string} [className]
 * @returns {DocumentFragment | null}
 */
export function routeLink(path, label, className = "") {
  return html`<a href="${path}" data-nav class="${className}">${label}</a>`;
}

/** Render an explanatory empty state.
 * @param {string} title
 * @param {string} text
 * @returns {DocumentFragment | null}
 */
export function emptyState(title, text) {
  return html`<div class="empty-state">
    ${icon("world", 40)}
    <h3>${title}</h3>
    <p>${text}</p>
  </div>`;
}

/** Render one labeled economic value.
 * @param {string} label
 * @param {import("../types.js").DomValue} value
 * @param {string} [className]
 * @returns {DocumentFragment | null}
 */
export function metric(label, value, className = "") {
  return html`<div class="metric ${className}">
    <span>${label}</span><strong>${value}</strong>
  </div>`;
}

/** Create an action button; the controller owns its behavior.
 * @param {string} action
 * @param {import("../types.js").DomValue} label
 * @param {boolean} [disabled]
 * @param {string} [className]
 * @param {string} [id]
 * @returns {DocumentFragment | null}
 */
export function actionButton(action, label, disabled = false, className = "primary", id = "") {
  return html`<button
    class="button ${className}"
    data-action="${action}"
    disabled="${disabled}"
    data-id="${id}"
  >
    ${label}
  </button>`;
}

/** Render fleet navigation shared by fleet and shop views.
 * @param {boolean} [shop]
 * @returns {DocumentFragment | null}
 */
export function fleetTabs(shop = false) {
  return html`<div class="tabs">
    ${routeLink("/fleet", "Meine Fahrzeuge", !shop ? "active" : "")}${routeLink("/fleet?tab=shop", "Fahrzeugshop", shop ? "active" : "")}
  </div>`;
}
