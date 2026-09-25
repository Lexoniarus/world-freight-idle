/** Resolve the saved city of an idle vehicle. @param {any} vehicle */
export function vehicleCity(vehicle) {
  return (vehicle.location_snapshot ?? vehicle.hub)?.city_uid ?? "";
}

/** Select a market reference vehicle; polling never chooses a replacement.
 * @param {any} state @param {URL} url @param {boolean} initial
 * @returns {any | null}
 */
export function marketVehicle(state, url, initial = false) {
  const vehicles = (state?.vehicles ?? []).filter((vehicle) => vehicle.status === "idle");
  const id = url.searchParams.get("vehicle");
  if (id) return vehicles.find((vehicle) => vehicle.id === id) ?? null;
  if (!initial) return null;
  const city = url.searchParams.get("city");
  return (
    vehicles
      .filter((vehicle) => !city || vehicleCity(vehicle) === city)
      .sort((a, b) => a.id.localeCompare(b.id))[0] ?? null
  );
}
