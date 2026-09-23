import { html } from "./dom.js";
import { number } from "../format.js";
import { transportProgress } from "../journey.js";

/** Render purchased measurements and explicitly simulated stop duration.
 * @param {{energy: import('../types.js').EnergyProfile, top_speed_kmh: number}} vehicle
 * @returns {DocumentFragment}
 */
export function renderEnergySpecification(vehicle) {
  const energy = vehicle.energy;
  return html`<p class="footnote">
    ${number(energy.capacity)} ${energy.unit} Kapazität · ${number(energy.consumption_per_100km, 2)}
    ${energy.unit}/100 km · max. ${number(vehicle.top_speed_kmh)} km/h<br />
    ${energy.kind === "electric" ? "Ladepause" : "Tankpause"}: ${number(energy.stop_minutes)} min
    vor Spielzeitbeschleunigung · 10 % Reserve
  </p>`;
}

/** Calculate an owned display level from its saved journey, without mutation.
 * @param {import('../types.js').Vehicle} vehicle
 * @param {import('../types.js').Transport | undefined} trip
 * @param {number} now
 * @returns {{level: number, text: string}}
 */
export function energyDisplay(vehicle, trip, now) {
  const level = (trip ? transportProgress(trip, now).energyLevel : null) ?? vehicle.energy_level;
  return {
    level,
    text: `${number(level, 1)} / ${number(vehicle.energy.capacity)} ${vehicle.energy.unit}`,
  };
}

/** Render a compact accessible meter; animation only updates text and value.
 * @param {import('../types.js').Vehicle} vehicle
 * @param {import('../types.js').Transport | undefined} trip
 * @param {number} now
 * @returns {DocumentFragment}
 */
export function renderEnergyMeter(vehicle, trip, now) {
  const display = energyDisplay(vehicle, trip, now);
  const label = vehicle.energy.kind === "electric" ? "Batterie" : "Tank";
  return html`<div class="energy-meter" data-energy-vehicle="${vehicle.id}">
    <div><span>${label}</span><span class="energy-value">${display.text}</span></div>
    <meter
      aria-label="${label}"
      min="0"
      max="${vehicle.energy.capacity}"
      value="${display.level}"
    ></meter>
  </div>`;
}
