import { html } from "../ui/dom.js";
import { icon } from "../ui/illustrations.js";
import { actionButton, emptyState, hubFilter, metric, routeLink } from "../ui/components.js";
import { money, number } from "../format.js";
import { formatDuration } from "../time.js";
import { eligibleVehicles } from "../geometry.js";

/** Render the contract market or the selected contract.
 * @param {import('../types.js').PanelView} view
 * @returns {DocumentFragment}
 */
export function renderContracts(view) {
  const id = view.url.pathname.split("/")[2];
  if (id) {
    const contract = view.state.contracts.find((item) => item.id === id);
    return contract
      ? renderContractDetails(contract, view)
      : html`${emptyState("Auftrag nicht mehr verfügbar", "Er wurde angenommen oder ist abgelaufen.")}${routeLink("/contracts", "Zur Auftragsbörse", "button primary")}`;
  }
  const hubId = view.url.searchParams.get("hub");
  const contracts = view.state.contracts
    .filter((item) => !hubId || item.origin_hub_id === hubId)
    .sort(
      (a, b) =>
        Number(eligibleVehicles(view.state.vehicles, b).length > 0) -
        Number(eligibleVehicles(view.state.vehicles, a).length > 0),
    );
  return html`<p class="panel-intro">
      Die nächste Lieferung wartet.<br />Finde einen Auftrag für deine Flotte.
    </p>
    <div class="section-toolbar">
      <span>${contracts.length} verfügbare Aufträge</span
      >${actionButton("refresh-market", [icon("refresh", 17), " Erneuern"], view.busy, "quiet")}
    </div>
    ${hubFilter(view.url)}
    <div class="card-list">
      ${contracts.length ? contracts.map((contract) => renderContractCard(contract, view.state.vehicles)) : emptyState("Keine Aufträge", "Erneuere die Börse oder wähle einen anderen Standort.")}
    </div>`;
}

/** Render one market listing and vehicle eligibility. */
function renderContractCard(contract, vehicles) {
  const ready = eligibleVehicles(vehicles, contract).length > 0;
  return routeLink(
    "/contracts/" + contract.id,
    html`<div class="card-kicker">
        <span>${contract.cargo} · ${number(contract.tons)} t</span
        ><span class="badge ${ready ? "green" : ""}"
          >${ready ? "Lkw bereit" : "Kein passender Lkw"}</span
        >
      </div>
      <h3>${contract.origin.city} ${icon("arrow", 17)} ${contract.destination.city}</h3>
      <div class="card-bottom"><span>${contract.origin.label}</span>${icon("arrow", 19)}</div>`,
    "job-card",
  );
}

/** Compose itinerary, quote and dispatch controls for one contract.
 * @param {import('../types.js').Contract} contract
 * @param {import('../types.js').PanelView} view
 * @returns {DocumentFragment}
 */
export function renderContractDetails(contract, view) {
  return html`${routeLink("/contracts", [icon("back", 16), " Alle Aufträge"], "back-link")}
    <div class="cargo-heading">
      ${icon("contracts", 28)}<span
        >${contract.cargo}<small>${number(contract.tons)} Tonnen · Straßentransport</small></span
      >
    </div>
    <div class="itinerary">
      ${renderStop("ABHOLUNG", contract.origin, contract.shipper_name)}${renderStop("ZUSTELLUNG", contract.destination, contract.consignee_name)}
    </div>
    <p class="footnote">Reale Frachtstandorte · simulierte Auftraggeber</p>
    ${renderQuote(view)}${renderDispatchForm(contract, view)}`;
}

/** Render one real freight stop and its simulated customer. */
function renderStop(label, hub, customer) {
  return html`<div>
    <i></i><span>${label}</span>
    <h2>${hub.city}</h2>
    <p>${hub.address}</p>
    <small>${customer}</small>
  </div>`;
}

/** Render server-calculated economics or the quote action. */
function renderQuote({ quote, state, busy }) {
  if (!quote)
    return html`<div class="quote-placeholder">
      <p>Wie viel steckt in diesem Auftrag?</p>
      ${actionButton("quote", busy ? "Route wird berechnet …" : "Route & Ertrag berechnen", busy)}
    </div>`;
  return html`<div class="metrics">
      ${metric("Strecke", number(quote.distance_km) + " km")}${metric("Fahrzeit im Spiel", formatDuration(quote.duration_seconds / state.time_scale))}${metric("Erlös", money(quote.payout_eur))}${metric("Betriebskosten", money(quote.operating_cost_eur))}${metric("Dein Gewinn", money(quote.profit_eur), "profit wide")}
    </div>
    ${actionButton("focus-quote", [icon("target", 17), " Route anzeigen"], false, "quiet")}`;
}

/** Render eligible vehicles without making authoritative dispatch decisions. */
function renderDispatchForm(contract, view) {
  const vehicles = eligibleVehicles(view.state.vehicles, contract);
  const insufficientFunds = view.quote && view.state.player.cash < view.quote.operating_cost_eur;
  return html`<div class="dispatch-form">
    <label for="vehicle-choice">Fahrzeug disponieren</label> ${
      vehicles.length
        ? html`<select id="vehicle-choice" disabled="${view.mutating}">
            ${vehicles.map((vehicle) => html`<option value="${vehicle.id}" selected="${view.selectedVehicle === vehicle.id}">${vehicle.name} · ${number(vehicle.capacity_tons)} t</option>`)}
          </select>`
        : html`<p class="inline-notice">
            Kein passender Lkw am Abholort. Standort, Nutzlast und Verfügbarkeit müssen passen.
          </p>`
    }
    ${actionButton("dispatch", view.busy ? "Bitte warten …" : ["Transport starten ", icon("arrow", 18)], view.busy || !view.quote || view.quote.vehicle_id !== view.selectedVehicle || !vehicles.length || insufficientFunds)}
    ${insufficientFunds ? html`<p class="inline-notice">Dein Guthaben reicht nicht für die Betriebskosten.</p>` : null}
  </div>`;
}
