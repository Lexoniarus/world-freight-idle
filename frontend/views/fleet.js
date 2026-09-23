import { renderEnergyMeter, renderEnergySpecification } from "../ui/vehicle-energy.js";
import { phaseLabel, transportProgress } from "../journey.js";
import { matchesFacility } from "../geometry.js";
import { html } from "../ui/dom.js";
import { renderVehicleImage } from "../ui/vehicle-image.js";
import { icon } from "../ui/illustrations.js";
import { emptyState, fleetTabs, hubFilter, routeLink } from "../ui/components.js";
import { number } from "../format.js";

/** Render the player's fleet filtered by public freight hub.
 * @param {import('../types.js').PanelView} view
 * @returns {DocumentFragment}
 */
export function renderFleet({ state, url, now }) {
  const hubId = url.searchParams.get("hub");
  const vehicles = state.vehicles.filter((vehicle) => matchesFacility(vehicle.hub, hubId));
  return html`${fleetTabs()}
    <div class="section-toolbar">
      <span>${state.idle_vehicles} einsatzbereit · ${state.active_transports} unterwegs</span>
    </div>
    ${hubFilter(url)}
    <div class="card-list">
      ${
        vehicles.length
          ? vehicles.map((vehicle) =>
              renderVehicle(
                vehicle,
                state.transports.find((trip) => trip.vehicle_id === vehicle.id),
                now,
              ),
            )
          : emptyState(
              "Hier steht kein Fahrzeug",
              "Deine übrige Flotte findest du unter „Alle anzeigen“.",
            )
      }
    </div>`;
}

/** Render one vehicle and its current location or transport. */
function renderVehicle(vehicle, trip, now) {
  return html`<article class="vehicle-card">
    <div class="card-kicker">
      <span class="badge ${trip ? "gold" : "green"}" data-phase-trip="${trip?.id ?? ""}"
        >${trip ? phaseLabel(transportProgress(trip, now).phase) : "Einsatzbereit"}</span
      ><span>${number(vehicle.capacity_tons, 2)} t</span>
    </div>
    ${renderVehicleImage(vehicle)}
    <h3>${vehicle.name}</h3>
    ${renderEnergyMeter(vehicle, trip, now)} ${renderEnergySpecification(vehicle)}
    <p>
      ${icon("pin", 15)}
      ${trip ? trip.origin.city + " → " + trip.destination.city : vehicle.hub.label}
    </p>
    ${routeLink(trip ? "/transports/" + trip.id : "/contracts?hub=" + (vehicle.facility_uid ?? vehicle.hub_id), trip ? "Transport verfolgen" : "Passende Aufträge finden", "button secondary")}
  </article>`;
}
