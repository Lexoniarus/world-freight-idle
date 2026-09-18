import { html } from "./dom.js";

/** Render a named static interface icon.
 * @param {string} name
 * @param {number} [size]
 * @returns {DocumentFragment}
 */
export function icon(name, size = 22) {
  const paths = {
    world:
      '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 6h14M5 18h14"/>',
    contracts:
      '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 3h6v4H9zM9 12h6M9 16h4"/>',
    fleet:
      '<path d="M2 6h12v11H2zM14 10h4l4 4v3h-8"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
    shop: '<path d="M4 8h16l-1 13H5zM8 8V6a4 4 0 0 1 8 0v2M12 12v6M9 15h6"/>',
    transports:
      '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M7 6h8a4 4 0 0 1 0 8H9a4 4 0 0 0 0 8M17 18h-4"/>',
    leaderboard:
      '<path d="M8 3h8v7a4 4 0 0 1-8 0zM8 5H4v3a4 4 0 0 0 4 4M16 5h4v3a4 4 0 0 1-4 4M12 14v6M8 21h8"/>',
    close: '<path d="m6 6 12 12M18 6 6 18"/>',
    arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    back: '<path d="M20 12H4m6-6-6 6 6 6"/>',
    target:
      '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 1v4m0 14v4M1 12h4m14 0h4"/>',
    layers: '<path d="m12 3 10 5-10 5L2 8zM2 12l10 5 10-5M2 16l10 5 10-5"/>',
    logout: '<path d="M9 4H4v16h5M9 12h12m-5-5 5 5-5 5"/>',
    pin: '<path d="M19 10c0 6-7 11-7 11S5 16 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    check: '<path d="m5 12 4 4L19 6"/>',
    refresh: '<path d="M20 7v5h-5M4 17v-5h5M6 6a8 8 0 0 1 14 6M4 12a8 8 0 0 0 14 6"/>',
  };
  return html`<svg
    width="${size}"
    height="${size}"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    ${iconPaths(name, paths)}
  </svg>`;
}

/** @param {boolean} [compact]
 * @returns {DocumentFragment} */
export function truckIllustration(compact = false) {
  return html`<svg
    class="truck-art"
    viewBox="0 0 440 180"
    role="img"
    aria-label="${compact ? "Regional-Lkw" : "Sattelzug"}"
  >
    <ellipse cx="228" cy="153" rx="181" ry="10" fill="#07121d" opacity=".28" />
    <path d="M44 57 69 37h${compact ? 195 : 250}v84H44Z" fill="#dce6ea" />
    <path d="M44 57h${compact ? 195 : 250}v68H44Z" fill="#9eb3c0" />
    <path d="M44 57 69 37h${compact ? 195 : 250}l-25 20Z" fill="#f1f6f8" />
    <path
      d="M58 66v48m12-48v48m12-48v48m12-48v48m12-48v48m12-48v48m12-48v48m12-48v48m12-48v48m12-48v48m12-48v48m12-48v48m12-48v48"
      stroke="#7f99aa"
      opacity=".5"
    />
    <path d="M${compact ? 245 : 300} 71h53l31 38v25h-84Z" fill="#f3bd46" />
    <path d="m${compact ? 254 : 309} 79h37l21 28h-58Z" fill="#19384c" />
    <path d="M${compact ? 304 : 359} 112h18v7h-18" fill="#fff4d0" />
    <path d="M39 126h${compact ? 302 : 357}v12H39Z" fill="#284354" />
    <path d="M${compact ? 252 : 307} 114h14" stroke="#b07b26" stroke-width="3" />
    <g fill="#142839" stroke="#08141f" stroke-width="5">
      <circle cx="89" cy="138" r="17" />
      <circle cx="129" cy="138" r="17" />
      <circle cx="${compact ? 296 : 351}" cy="138" r="17" />
    </g>
    <g fill="#98adba">
      <circle cx="89" cy="138" r="7" />
      <circle cx="129" cy="138" r="7" />
      <circle cx="${compact ? 296 : 351}" cy="138" r="7" />
    </g>
    <text
      x="152"
      y="97"
      fill="#365264"
      font-family="sans-serif"
      font-size="16"
      font-weight="800"
      letter-spacing="3"
    >
      WF /
    </text>
  </svg>`;
}

/** Parse a fixed icon definition selected by name; no user markup is accepted. */
function iconPaths(name, paths) {
  const parsed = new DOMParser().parseFromString(
    `<svg xmlns="http://www.w3.org/2000/svg">${paths[name] || paths.world}</svg>`,
    "image/svg+xml",
  );
  return document.importNode(parsed.documentElement, true);
}
