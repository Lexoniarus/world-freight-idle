/** Join each owned vehicle to at most one active transport. */
export function fleetEntries(state) {
  const trips = new Map(state.transports.map((trip) => [trip.vehicle_id, trip]));
  return state.vehicles.map((vehicle) => ({
    vehicle,
    trip: trips.get(vehicle.id) ?? null,
  }));
}

/** Decide whether one distinct fleet entry belongs to a city filter. */
export function matchesFleetCity(entry, cityUid) {
  if (!cityUid) return true;
  if (entry.trip)
    return entry.trip.origin?.city_uid === cityUid || entry.trip.destination?.city_uid === cityUid;
  const location = entry.vehicle.location_snapshot ?? entry.vehicle.hub;
  return location?.city_uid === cityUid;
}

/** Group distinct entries by physical station or one shared journey section. */
export function groupFleetEntries(entries) {
  const sections = new Map();
  const section = (key, label, kind) => {
    if (!sections.has(key)) sections.set(key, { key, label, kind, entries: [] });
    return sections.get(key);
  };
  for (const entry of entries) {
    if (entry.trip) {
      section("enroute", "Unterwegs", "enroute").entries.push(entry);
      continue;
    }
    const location = entry.vehicle.location_snapshot ?? entry.vehicle.hub ?? null;
    const key = "city:" + (location?.city_uid ?? "unknown");
    section(key, location?.city ?? "Standort unbekannt", "stationed").entries.push(entry);
  }
  return [...sections.values()].sort((left, right) => {
    if (left.kind !== right.kind) return left.kind === "stationed" ? -1 : 1;
    return left.label.localeCompare(right.label, "de");
  });
}

/** Select unique fleet entries displayed by the current fleet route. */
export function selectFleetEntries(state, url, cityUid = "") {
  const model = url.searchParams.get("model");
  const status = url.searchParams.get("status");
  const search = (url.searchParams.get("search") ?? "").toLocaleLowerCase("de");
  return fleetEntries(state).filter(
    (entry) =>
      matchesFleetCity(entry, cityUid) &&
      (!model || entry.vehicle.model_id === model) &&
      (!status || entry.vehicle.status === status) &&
      entry.vehicle.name.toLocaleLowerCase("de").includes(search),
  );
}

/** Select and group the distinct entries displayed by the fleet view. */
export function selectFleetSections(state, url, cityUid = "") {
  return groupFleetEntries(selectFleetEntries(state, url, cityUid));
}
