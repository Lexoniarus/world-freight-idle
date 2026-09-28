import { selectFleetGroups } from "../fleet-selection.js";
export { fleetGroups } from "../fleet-selection.js";
import { renderEnergyMeter, renderEnergySpecification } from "../ui/vehicle-energy.js";
import { phaseLabel, transportProgress } from "../journey.js";
import { html } from "../ui/dom.js";
import { renderVehicleImage } from "../ui/vehicle-image.js";
import { emptyState, fleetTabs, routeLink } from "../ui/components.js";
import { cityFilter, selectFilter, searchFilter } from "../ui/filters.js";
import { number } from "../format.js";

/** City-first fleet management and individual vehicle inspection. */
export function renderFleet(view) {
  const { state, url, now } = view;
  const id = url.pathname.split("/")[2];
  if (id) {
    const vehicle = state.vehicles.find((item) => item.id === id);
    return vehicle
      ? html`${routeLink("/fleet", "Zur Flotte", "back-link")}${renderVehicle(
          vehicle,
          state.transports.find((trip) => trip.vehicle_id === id),
          now,
          true,
        )}`
      : emptyState("Fahrzeug nicht gefunden", "Öffne deine Flotte erneut.");
  }
  const model = url.searchParams.get("model");
  const status = url.searchParams.get("status");
  const groups = selectFleetGroups(state, url, view.cityUid);
  return html`${fleetTabs()}
    <div class="filter-grid">
      ${cityFilter(view)}
      ${selectFilter(
        "status",
        "Status",
        [
          ["idle", "Einsatzbereit"],
          ["enroute", "Unterwegs"],
        ],
        status,
      )}
      ${selectFilter("model", "Modell", [...new Map(state.vehicles.map((vehicle) => [vehicle.model_id, vehicle.name])).entries()], model)}
      ${searchFilter("search", "Fahrzeugname", url)}
    </div>
    ${
      groups.length
        ? groups.map(
            (group) =>
              html`<section class="fleet-city">
                <h2>${group.city.city}</h2>
                ${[
                  ["stationed", "Hier stationiert"],
                  ["outbound", "Von hier unterwegs"],
                  ["inbound", "Hierhin unterwegs"],
                ].map(([role, label]) =>
                  group[role].length
                    ? html`<h3 class="group-heading">
                          ${label}<span>${group[role].length} Fahrzeuge</span>
                        </h3>
                        <div class="card-list">
                          ${group[role].map(({ vehicle, trip }) => renderVehicle(vehicle, trip, now))}
                        </div>`
                    : null,
                )}
              </section>`,
          )
        : emptyState("Keine Fahrzeuge in dieser Auswahl", "Passe Stadt oder Filter an.")
    }`;
}

function renderVehicle(vehicle, trip, now, detail = false) {
  const place = vehicle.location_snapshot ?? vehicle.hub;
  const city = place?.city_uid ?? "";
  const orders =
    "/contracts?city=" + encodeURIComponent(city) + "&vehicle=" + encodeURIComponent(vehicle.id);
  return html`<article class="vehicle-card ${detail ? "vehicle-detail" : "vehicle-row"}">
    ${renderVehicleImage(vehicle, detail ? "detail" : trip ? "side" : "front")}
    <div class="vehicle-info">
      <div class="card-kicker">
        <span class="badge ${trip ? "gold" : "green"}" data-phase-trip="${trip?.id ?? ""}"
          >${trip ? phaseLabel(transportProgress(trip, now).phase, transportProgress(trip, now).stage) : "Einsatzbereit"}</span
        ><span>${number(vehicle.capacity_tons, 2)} t</span>
      </div>
      <h3>
        ${routeLink("/fleet/" + vehicle.id + "?city=" + encodeURIComponent(city), vehicle.name)}
      </h3>
      <p>${trip ? trip.origin.city + " → " + trip.destination.city : place?.city}</p>
      <p class="footnote">${trip ? "Unterwegs · kein stationiertes Fahrzeug" : place?.label}</p>
      ${renderEnergyMeter(vehicle, trip, now)}${detail ? renderEnergySpecification(vehicle) : null}
      ${routeLink(trip ? "/transports/" + trip.id : orders, trip ? "Transport verfolgen" : "Stadtmarkt öffnen", "button secondary")}
    </div>
  </article>`;
}
