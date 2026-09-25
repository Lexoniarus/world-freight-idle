import { collection, pointFeature } from "../geometry.js";

/** Selected endpoints remain visible independently of normal layer preferences. */
export function selectedLocations(state, id, contract = null) {
  const trip = state.transports.find((item) => item.id === id);
  const offer = contract?.id === id ? contract : state.contracts.find((item) => item.id === id);
  const locations = trip
    ? [trip.origin, trip.destination]
    : offer
      ? [offer.origin, offer.destination]
      : [];
  return collection(
    locations
      .filter((item) => Number.isFinite(item?.lon) && Number.isFinite(item?.lat))
      .map((item) => pointFeature([item.lon, item.lat], { id: item.facility_uid ?? item.id })),
  );
}
