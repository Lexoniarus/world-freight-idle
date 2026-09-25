/** Group vehicles by physical idle location and explicit journey direction. */
export function fleetGroups(state, cityUid) {
  const groups = new Map();
  const add = (city, role, vehicle, trip) => {
    if (cityUid && city?.city_uid !== cityUid) return;
    city = city ?? { city: "Standort unbekannt" };
    if (!groups.has(city.city_uid))
      groups.set(city.city_uid, { city, stationed: [], outbound: [], inbound: [] });
    groups.get(city.city_uid)[role].push({ vehicle, trip });
  };
  for (const vehicle of state.vehicles) {
    const trip = state.transports.find((item) => item.vehicle_id === vehicle.id);
    if (!trip) add(vehicle.location_snapshot ?? vehicle.hub, "stationed", vehicle, null);
    else {
      add(trip.origin, "outbound", vehicle, trip);
      if (trip.destination.city_uid !== trip.origin.city_uid)
        add(trip.destination, "inbound", vehicle, trip);
    }
  }
  return [...groups.values()].sort((a, b) => (a.city.city ?? "").localeCompare(b.city.city ?? ""));
}

/** Select exactly the city groups displayed by the fleet view.
 * @param {any} state @param {URL} url @param {string} [cityUid]
 */
export function selectFleetGroups(state, url, cityUid = "") {
  const model = url.searchParams.get("model");
  const status = url.searchParams.get("status");
  const search = (url.searchParams.get("search") ?? "").toLocaleLowerCase("de");
  return fleetGroups(
    {
      ...state,
      vehicles: state.vehicles.filter(
        (vehicle) =>
          (!model || vehicle.model_id === model) &&
          (!status || vehicle.status === status) &&
          vehicle.name.toLocaleLowerCase("de").includes(search),
      ),
    },
    cityUid,
  );
}
