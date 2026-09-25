import { renderCostBreakdown } from "../ui/cost-breakdown.js";
import { cityFilter, selectFilter, searchFilter } from "../ui/filters.js";
import { renderVehicleImage } from "../ui/vehicle-image.js";
import { renderEnergyMeter } from "../ui/vehicle-energy.js";
import { distanceLabels, classLabels, humanLabel } from "../labels.js";
import { html } from "../ui/dom.js";
import { icon } from "../ui/illustrations.js";
import { actionButton, emptyState, metric, routeLink } from "../ui/components.js";
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
    const contract =
      view.detailId === id
        ? view.detailContract
        : view.state.contracts.find((item) => item.id === id);
    return contract
      ? renderContractDetails(contract, view)
      : view.detailId !== id
        ? html`<p role="status">Auftrag wird geladen …</p>`
        : html`${emptyState("Auftrag nicht mehr verfügbar", "Er wurde angenommen oder ist abgelaufen.")}${routeLink("/contracts", "Zur Auftragsbörse", "button primary")}`;
  }
  const params = view.url.searchParams;
  const contracts = filterContracts(view.state.contracts, view.cityUid, params);
  const city = view.cities?.find((item) => item.city_uid === view.cityUid);
  const active = !view.cityUid || view.activeCities?.includes(view.cityUid);
  return html`<div class="market-heading">
      <span class="eyebrow">STADTMARKT</span>
      <h2>${city?.city ?? "Alle Marktstädte"}</h2>
      <p>
        ${view.marketLoaded === false ? "Auftragszahl noch unbekannt" : contracts.length + (view.marketStale ? " Aufträge · wird aktualisiert" : " verfügbare Aufträge")}
      </p>
    </div>
    ${active ? null : html`<p class="inline-notice">In dieser Stadt steht kein eigenes einsatzbereites Fahrzeug. Hier ist aktuell kein Stadtmarkt aktiv.</p>`}
    <div class="distance-summary">
      ${Object.entries(distanceLabels).map(([code, label]) => html`<span>${label}<strong>${view.marketLoaded === false || view.marketStale ? "–" : contracts.filter((item) => item.distance_band === code).length}</strong></span>`)}
    </div>
    <div class="filter-grid">
      ${cityFilter(view, true)}
      ${view.marketCities?.length === 0 ? html`<p role="status">Keine aktive Marktstadt: Deine Fahrzeuge sind unterwegs.</p>` : null}
      ${selectFilter(
        "vehicle",
        "Geeignetes Fahrzeug",
        view.state.vehicles
          .filter((item) => item.status === "idle")
          .map((item) => [item.id, item.name]),
        params.get("vehicle"),
      )}
    </div>
    <details
      class="filter-details"
      data-disclosure="market-filters"
      open="${["band", "class", "destination", "cargo"].some((key) => params.get(key))}"
    >
      <summary>Weitere Filter · Entfernung, Fracht und Ziel</summary>
      <div class="filter-grid">
        ${selectFilter("band", "Entfernungsklasse", Object.entries(distanceLabels), params.get("band"))}
        ${selectFilter("class", "Transportklasse", Object.entries(classLabels), params.get("class"))}
        ${searchFilter("destination", "Zielstadt", view.url)}${searchFilter("cargo", "Ware", view.url)}
      </div>
    </details>
    <div class="section-toolbar">
      <span>Reale Standorte · simulierte Aufträge</span
      >${actionButton("refresh-market", [icon("refresh", 17), " Erneuern"], view.busy, "quiet")}
    </div>
    <div class="card-list">
      ${view.marketLoaded === false ? html`<p role="status">Stadtmarkt wird geladen …</p>` : contracts.length ? contracts.map((contract) => renderContractCard(contract, view.state.vehicles, params)) : emptyState("Keine passenden Aufträge", "Passe die Filter an oder erneuere den Stadtmarkt.")}
    </div>`;
}

/** Filter only authoritative offer facts, never rebuild vehicle eligibility. */
export function filterContracts(contracts, cityUid, params) {
  const hasText = (value, key) =>
    String(value)
      .toLocaleLowerCase("de")
      .includes((params.get(key) ?? "").toLocaleLowerCase("de"));
  return contracts.filter(
    (item) =>
      (!cityUid || item.origin.city_uid === cityUid) &&
      (!params.get("vehicle") || item.eligible_vehicle_ids?.includes(params.get("vehicle"))) &&
      (!params.get("band") || item.distance_band === params.get("band")) &&
      (!params.get("class") || item.transport_class === params.get("class")) &&
      hasText(item.destination.city, "destination") &&
      hasText(item.cargo, "cargo"),
  );
}

/** Render one market listing and vehicle eligibility. */
function renderContractCard(contract, vehicles, params = new URLSearchParams()) {
  const ready = eligibleVehicles(vehicles, contract).length > 0;
  return routeLink(
    "/contracts/" + contract.id + "?" + params,
    html`<div class="card-kicker">
        <span title="${contract.cargo}">${contract.cargo}</span
        ><strong class="cargo-amount">${number(contract.tons, 2)} t</strong
        ><span class="badge ${ready ? "green" : ""}"
          >${ready ? "Lkw bereit · " + eligibleVehicles(vehicles, contract).length + " Fahrzeuge verfügbar" : "Kein passender Lkw"}</span
        >
      </div>
      <h3>${contract.origin.city} ${icon("arrow", 17)} ${contract.destination.city}</h3>
      ${contract.distance_band ? html`<p class="footnote">${humanLabel(contract.distance_band)} · ca. ${number(contract.estimated_distance_km)} km Luftlinie</p>` : null}
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
  const vehicle = view.state.vehicles.find((item) => item.id === view.selectedVehicle);
  const start = view.quote?.start ?? vehicle?.location_snapshot ?? vehicle?.hub;
  return html`${routeLink("/contracts", [icon("back", 16), " Alle Aufträge"], "back-link")}
    <div class="cargo-heading">
      ${icon("contracts", 28)}<span
        >${contract.cargo}<small>${number(contract.tons, 2)} Tonnen · Straßentransport</small></span
      >
    </div>
    <div class="itinerary">
      ${start ? renderStop("FAHRZEUGSTANDORT", start, "Fahrtbeginn") : null}
      ${renderStop("ABHOLUNG", contract.origin, contract.shipper_name)}${renderStop("ZUSTELLUNG", contract.destination, contract.consignee_name)}
    </div>
    <p class="footnote">
      Reale Standorte und Referenzunternehmen · Geschäftsbeziehung, Menge und Auftrag simuliert
    </p>
    ${contract.cargo_basis === "derived" ? html`<p class="footnote">NHM-Warenprofil für diesen Standort simuliert; konkrete Geschäftsbeziehung und Auftrag bleiben Spielsimulation.</p>` : null}
    ${contract.market_model === "nhm_v2" ? html`<p class="footnote">${humanLabel(contract.transport_class)} · Warenwert ${money(contract.cargo_value_eur)} (Spielwert, kein Transporterlös)</p>` : null}
    <div class="metrics">
      ${metric("NHM-Code", contract.cargo_code ?? "—")}${metric("Geschätzte Luftlinie", number(contract.estimated_distance_km) + " km")}
    </div>
    ${renderDispatchForm(contract, view)}${renderQuote(view)}`;
}

/** Render a real public facility and its reference company. */
function renderStop(label, hub, customer) {
  return html`<div>
    <i></i><span>${label}</span>
    <h2>${hub.label}</h2>
    <p>${hub.address}</p>
    <small>${customer}</small>
  </div>`;
}

/** Render server-calculated economics or the quote action. */
function renderQuote({ quote, state, busy, selectedVehicle }) {
  if (!quote)
    return html`<div class="quote-placeholder">
      <p>Wie viel steckt in diesem Auftrag?</p>
      ${actionButton("quote", busy ? "Route wird berechnet …" : "Route & Ertrag berechnen", busy || !selectedVehicle)}
    </div>`;
  return html`<div class="metrics">
      ${metric("Anfahrt zur Abholung", number(quote.approach_distance_km ?? 0) + " km")}${metric("Frachtstrecke", number(quote.delivery_distance_km ?? quote.distance_km) + " km")}
      ${metric("Straßenstrecke gesamt", number(quote.distance_km) + " km")}${metric("Gesamtdauer im Spiel", formatDuration(quote.total_duration_seconds ?? quote.duration_seconds / state.time_scale))}${metric("Erlös", money(quote.payout_eur))}${metric("Betriebskosten", money(quote.operating_cost_eur))}${metric("Dein Gewinn", money(quote.profit_eur), "profit wide")}
    </div>
    ${renderCostBreakdown(quote.cost_breakdown)}
    ${quote.profit_eur < 0 ? html`<p class="inline-notice negative">Dieser Auftrag ergibt mit diesem Fahrzeug ein negatives Ergebnis.</p>` : null}
    ${quote.journey ? html`<p class="footnote">${quote.energy_stop_count} Tank-/Ladepausen · ${formatDuration(quote.pause_seconds)} Pause insgesamt · Verbrauch ${number(quote.energy_consumption, 1)} ${quote.journey.energy.unit}. Haltepositionen sind simuliert.</p>` : null}
    ${actionButton("focus-quote", [icon("target", 17), " Route anzeigen"], false, "quiet")}`;
}

/** Render eligible vehicles without making authoritative dispatch decisions. */
function renderDispatchForm(contract, view) {
  const vehicles = eligibleVehicles(view.state.vehicles, contract);
  const insufficientFunds = view.quote && view.state.player.cash < view.quote.operating_cost_eur;
  return html`<div class="dispatch-form">
    <h3>Fahrzeug disponieren</h3>
    <div class="vehicle-choices" role="radiogroup" aria-label="Geeignete Fahrzeuge">
      ${vehicles.map(
        (vehicle) =>
          html`<button
            type="button"
            class="vehicle-choice"
            role="radio"
            aria-checked="${view.selectedVehicle === vehicle.id}"
            data-action="choose-vehicle"
            data-id="${vehicle.id}"
            disabled="${view.mutating}"
          >
            ${renderVehicleImage(vehicle, "front")}<span
              ><strong>${vehicle.name}</strong
              ><span
                >${number(vehicle.capacity_tons, 2)} t Nutzlast · ${number(contract.tons, 2)} t
                Auftrag</span
              ><span>${vehicle.hub?.city} · ${vehicle.hub?.label}</span
              >${renderEnergyMeter(vehicle, null, view.now)}</span
            >
          </button>`,
      )}
    </div>
    <label for="vehicle-choice">Fahrzeug disponieren</label> ${
      vehicles.length
        ? html`<select id="vehicle-choice" disabled="${view.mutating}">
            ${vehicles.map((vehicle) => html`<option value="${vehicle.id}" selected="${view.selectedVehicle === vehicle.id}">${vehicle.name} · ${number(vehicle.capacity_tons, 2)} t</option>`)}
          </select>`
        : html`<p class="inline-notice">
            Kein passender Lkw in der Abholstadt. Nutzlast, Transportklasse und Fahrzeuggröße müssen
            passen.
          </p>`
    }
    ${actionButton("dispatch", view.busy ? "Bitte warten …" : ["Transport starten ", icon("arrow", 18)], view.busy || !view.quote || view.quote.vehicle_id !== view.selectedVehicle || !vehicles.length || insufficientFunds)}
    ${insufficientFunds ? html`<p class="inline-notice">Dein Guthaben reicht nicht für die Betriebskosten.</p>` : null}
  </div>`;
}
