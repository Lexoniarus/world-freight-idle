import { html } from "./dom.js";
import { money, number } from "../format.js";

/** Display stored server economics; never calculate a client-side price.
 * @param {import("../types.js").CostBreakdown | null | undefined} costs
 */
export function renderCostBreakdown(costs) {
  if (!costs)
    return html`<p class="footnote">Historische Kostenaufschlüsselung nicht verfügbar.</p>`;
  return html`<details data-disclosure="costs">
    <summary>Kostenaufschlüsselung</summary>
    <dl class="cost-breakdown">
      <dt>Grundkosten</dt>
      <dd>${money(costs.base_cost_eur)}</dd>
      <dt>Wartung · ${number(costs.maintenance_eur_per_km, 3)} €/km</dt>
      <dd>${money(costs.maintenance_cost_eur)}</dd>
      <dt>Energieeinkäufe · ${costs.purchases.length} Halte</dt>
      <dd>${money(costs.energy_cost_eur)}</dd>
      ${costs.purchases.map(
        (stop, index) =>
          html`<dt>
              Halt ${index + 1} · ${number(stop.quantity, 2)} ${costs.energy_unit} ×
              ${number(costs.energy_price_eur_per_unit, 2)} €/${costs.energy_unit}
            </dt>
            <dd>${money(stop.cost_eur)}</dd>`,
      )}
      <dt>Gesamtkosten</dt>
      <dd>${money(costs.total_cost_eur)}</dd>
    </dl>
    <p class="footnote">Gameplaypreise. Alle geplanten Kosten werden beim Start abgebucht.</p>
  </details>`;
}
