/** Collect known cities from saved locations without loading the world. */
export function cityLocations(state) {
  if (!state) return [];
  return [
    ...state.vehicles.map((item) => item.location_snapshot ?? item.hub),
    ...state.contracts.flatMap((item) => [item.origin, item.destination]),
    ...state.transports.flatMap((item) => [item.origin, item.destination]),
  ].filter((item) => item?.city_uid);
}

/** Stable default order is independent of display names and array order. */
export function activeCityIds(state) {
  return [
    ...new Set(
      (state?.vehicles ?? [])
        .filter((item) => item.status === "idle")
        .map((item) => (item.location_snapshot ?? item.hub)?.city_uid)
        .filter(Boolean),
    ),
  ].sort();
}

/** Match legacy facility IDs or their explicitly stored aliases. */
export function resolveLegacyCity(state, identifier) {
  return cityLocations(state).find(
    (item) => (item.facility_uid ?? item.id) === identifier || item.aliases?.includes(identifier),
  );
}
