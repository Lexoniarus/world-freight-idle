import { html } from "../ui/dom.js";
import { renderVehicleImage } from "../ui/vehicle-image.js";
import { icon } from "../ui/illustrations.js";
import { actionButton, fleetTabs } from "../ui/components.js";
import { money, number } from "../format.js";

/** Render the vehicle catalogue using server prices and delivery hub.
 * @param {import('../types.js').PanelView} view
 * @returns {DocumentFragment}
 */
export function renderShop({ catalogue, state, busy }) {
  return html`${fleetTabs(true)}${
    catalogue
      ? html`<p class="panel-intro">
            Mehr Kapazität. Mehr Möglichkeiten.<br />Vergrößere deine Flotte.
          </p>
          <div class="card-list">
            ${catalogue.models.map((model) => renderOffer(model, catalogue.delivery_hub, state.player.cash, state.player.reputation, busy))}
          </div>
          <p class="footnote">
            Dein Fahrzeug ist nach dem Kauf sofort am Lieferstandort einsatzbereit. Technische
            Modelle stammen aus dem Fahrzeugkatalog; Preise, Nutzlast und Betriebskosten sind
            Spielwerte.
          </p>`
      : html`<p class="loading">Fahrzeuge werden geladen …</p>`
  }`;
}

/** Render one purchase offer. */
function renderOffer(model, deliveryHub, cash, reputation, busy) {
  const affordable = cash >= model.price_eur;
  const unlocked = reputation >= model.unlock_reputation;
  return html`<article class="vehicle-card shop-card">
    <div class="card-kicker">
      <span class="badge">Neufahrzeug</span><span>Straßentransport</span>
    </div>
    ${renderVehicleImage(model)}
    <h3>${model.name}</h3>
    <p>${number(model.capacity_tons, 2)} t Nutzlast · Lieferung nach ${deliveryHub}</p>
    <p>
      ${number(model.operating_cost_eur_per_km, 2)} € / km ·
      ${model.powertrain === "battery_electric" ? "Elektro" : model.powertrain === "gas" ? "Gas" : "Diesel"}
    </p>
    <p class="footnote">Freigabe ab Reputation ${model.unlock_reputation}</p>
    <div class="purchase-row"><strong>${money(model.price_eur)}</strong><span>einmalig</span></div>
    ${actionButton("buy", !unlocked ? "Reputation reicht nicht" : affordable ? ["Fahrzeug kaufen ", icon("arrow", 18)] : "Guthaben reicht nicht", busy || !affordable || !unlocked, "primary", model.id)}
  </article>`;
}
