import { html } from "./dom.js";
import { renderVehicleImage } from "./vehicle-image.js";
import { getVehicleAssets } from "../vehicle-assets.js";

/** Render a server-provided palette and current-livery previews.
 * @param {import("../types.js").PanelView} view
 */
export function renderCompanyPreferences(view) {
  const vehicle = view.state?.vehicles[0];
  const assets = getVehicleAssets(vehicle?.model_id);
  return html`<section aria-label="Firmenfarbe">
    <h3>Firmenfarbe</h3>
    ${
      view.preferenceStatus === "error"
        ? html`<p role="alert">Firmenfarben konnten nicht geladen werden.</p>
            <button data-preference-retry>Erneut versuchen</button>`
        : !view.companyPalette
          ? html`<p role="status">Farben werden geladen …</p>`
          : null
    }
    ${view.preferenceSaveError ? html`<p role="alert">Firmenfarbe konnte nicht gespeichert werden. Bitte wähle die Farbe erneut.</p>` : null}
    <div class="company-palette" role="group" aria-label="Firmenfarbe">
      ${(view.companyPalette ?? []).map(
        (color, index) =>
          html`<button
            type="button"
            data-company-color="${color}"
            style="${"--swatch:" + color}"
            aria-label="Firmenfarbe ${index + 1}"
            aria-pressed="${view.user.company_color === color}"
          >
            <span aria-hidden="true">${view.user.company_color === color ? "✓" : ""}</span>
          </button>`,
      )}
    </div>
    ${vehicle ? renderVehicleImage(vehicle) : null}
    ${
      assets
        ? html`<img
            class="company-map-preview"
            data-vehicle-model="${vehicle.model_id}"
            data-vehicle-role="map"
            src="${assets.map}"
            alt="Vorschau des Kartenfahrzeugs"
          />`
        : null
    }
    <p class="footnote">Deine Firmenfarbe ist auch für andere Spieler sichtbar.</p>
  </section>`;
}
