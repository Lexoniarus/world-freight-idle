/** Resolve the saved city of an idle vehicle. @param {import("./types.js").Vehicle} vehicle */
export function vehicleCity(vehicle) {
  return (vehicle.location_snapshot ?? vehicle.hub)?.city_uid ?? "";
}

/** Select a market reference vehicle; polling never chooses a replacement.
 * @param {import("./types.js").GameSnapshot | null} state @param {URL} url
 * @returns {import("./types.js").Vehicle | null}
 */
export function marketVehicle(state, url) {
  const vehicles = (state?.vehicles ?? []).filter((vehicle) => vehicle.status === "idle");
  const id = url.searchParams.get("vehicle");
  if (id) return vehicles.find((vehicle) => vehicle.id === id) ?? null;
  return null;
}

/** Project map offers from the same server-authorized vehicle context.
 * @param {import("./types.js").GameSnapshot} state
 * @param {URL} url
 * @returns {import("./types.js").MapState}
 */
export function marketMapState(state, url) {
  if (url.pathname !== "/contracts") return state;
  const vehicle = marketVehicle(state, url);
  return {
    ...state,
    marketVehicleId: vehicle?.id ?? "",
    contracts: vehicle
      ? state.contracts.filter((offer) => offer.eligible_vehicle_ids?.includes(vehicle.id))
      : [],
  };
}
