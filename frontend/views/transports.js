import { phaseLabel, transportProgress } from "../journey.js";
import { renderEnergyMeter } from "../ui/vehicle-energy.js";
import { html } from "../ui/dom.js";
import { renderVehicleImage } from "../ui/vehicle-image.js";
import { icon } from "../ui/illustrations.js";
import { actionButton, emptyState, metric, routeLink } from "../ui/components.js";
import { money, number } from "../format.js";
import { formatDuration, formatCountdown } from "../time.js";

/** Render active transports or one selected transport.
 * @param {import('../types.js').PanelView} view
 * @returns {DocumentFragment}
 */
export function renderTransports({ state, url, now }) {
  const id = url.pathname.split("/")[2];
  if (id) {
    const trip = state.transports.find((item) => item.id === id);
    return trip
      ? renderTransportDetails(
          trip,
          now,
          state.vehicles.find((vehicle) => vehicle.id === trip.vehicle_id),
        )
      : html`${emptyState("Transport nicht mehr aktiv", "Bereits abgeschlossene Lieferungen sind im Kontostand und in der Reputation berücksichtigt.")}${routeLink("/fleet", "Zur Flotte", "button primary")}`;
  }
  return html`<p class="panel-intro">Deine Flotte hält die Welt in Bewegung.</p>
    <div class="card-list">
      ${state.transports.length ? state.transports.map((trip) => renderTransportCard(trip, now)) : html`${emptyState("Die Straße wartet", "Nimm einen Auftrag an und schicke deinen ersten Lkw auf die Reise.")}${routeLink("/contracts", "Auftrag auswählen", "button primary")}`}
    </div>`;
}

/** Render the overview link for one active transport. */
function renderTransportCard(trip, now) {
  return routeLink(
    "/transports/" + trip.id,
    html`<div class="card-kicker">
        <span class="badge green" data-phase-trip="${trip.id}"
          >${progressDisplay(trip, now).phase}</span
        ><span>${number(trip.distance_km)} km</span>
      </div>
      <h3>${trip.origin.city} ${icon("arrow", 16)} ${trip.destination.city}</h3>
      ${renderProgress(trip, now)}
      <div class="card-bottom">
        <span>${trip.contract.cargo}</span><strong>${money(trip.payout_eur)}</strong>
      </div>`,
    "job-card",
  );
}

/** Render the economics and tracking controls of one transport. */
function renderTransportDetails(trip, now, vehicle) {
  return html`${routeLink("/transports", [icon("back", 16), " Alle Transporte"], "back-link")}
    <div class="dispatch-banner">
      <span class="badge green" data-phase-trip="${trip.id}"
        >${progressDisplay(trip, now).phase}</span
      >${renderVehicleImage(vehicle || { name: "Lkw", capacity_tons: 24 })}
    </div>
    <h2>${trip.origin.city} ${icon("arrow", 22)} ${trip.destination.city}</h2>
    <p>${trip.contract.cargo} · ${number(trip.contract.tons, 2)} t</p>
    ${renderProgress(trip, now)} ${vehicle ? renderEnergyMeter(vehicle, trip, now) : null}
    <div class="metrics">
      ${metric("Strecke", number(trip.distance_km) + " km")}${metric("Erlös bei Ankunft", money(trip.payout_eur))}${metric("Betriebskosten", money(trip.operating_cost_eur))}${metric("Gewinn", money(trip.profit_eur), "profit")}
    </div>
    ${actionButton("focus-trip", [icon("target", 18), " Route auf der Karte"], false, "secondary", trip.id)}
    <p class="footnote">
      Der Transport läuft auch weiter, wenn du das Spiel schließt. Die Gutschrift erfolgt bei
      bestätigter Ankunft.
    </p>`;
}

/** Describe interpolated progress; only the server can confirm settlement.
 * @param {import('../types.js').Transport} trip
 * @param {number} now
 */
export function progressDisplay(trip, now) {
  const progress = transportProgress(trip, now);
  const paused = ["refuelling", "charging"].includes(progress.phase);
  return {
    phase: phaseLabel(progress.phase),
    percent: Math.round(progress.fraction * 100),
    eta:
      progress.phase === "arrived"
        ? "Ankunft wird bestätigt …"
        : paused
          ? phaseLabel(progress.phase) +
            " · Weiter in " +
            formatCountdown(progress.remainingSeconds)
          : "Ankunft in " + formatDuration(trip.arrives_at - now),
  };
}

/** Render an accessible transport progress indicator. */
function renderProgress(trip, now) {
  const { percent, eta } = progressDisplay(trip, now);
  return html`<div class="trip-progress" data-trip="${trip.id}">
    <div><span class="eta">${eta}</span><b class="percentage">${percent}%</b></div>
    <progress aria-label="Transportfortschritt" max="100" value="${percent}">${percent}%</progress>
  </div>`;
}
