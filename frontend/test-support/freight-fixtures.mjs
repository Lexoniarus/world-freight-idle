export function freightApi(request) {
  return {
    loadFreightOffers: (vehicleId, signal) =>
      request(`/contracts?vehicle_id=${vehicleId}`, { signal }),
    requestFreightRefill: (vehicleId, signal) =>
      request(`/contracts/refresh?vehicle_id=${vehicleId}`, {
        method: "POST",
        signal,
      }),
    loadFreightOffer: (id, signal) => request(`/contracts/${id}`, { signal }),
  };
}

export const berlin = {
  city_uid: "a",
  city: "Same Name",
  id: "facility-a",
  aliases: ["legacy"],
  lat: 52,
  lon: 13,
};

export const other = {
  city_uid: "b",
  city: "Same Name",
  id: "facility-b",
  lat: 50,
  lon: 12,
};

export const vehicle = {
  id: "v1",
  status: "idle",
  hub: berlin,
  model_id: "iveco_sway_500",
  name: "IVECO",
  capacity_tons: 24,
};

export const offer = {
  id: "offer",
  origin: berlin,
  destination: other,
  cargo: "Fahrzeugteile",
  transport_class: "general",
  distance_band: "short",
  eligible_vehicle_ids: ["v1"],
};
