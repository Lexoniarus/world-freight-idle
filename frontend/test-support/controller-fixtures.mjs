import { PanelController } from "../controllers/panel-controller.js";
import { renderShell } from "../views/shell.js";

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
    quoteFreightOffer: (id, vehicleId, signal) =>
      request(`/contracts/${id}/quote`, {
        method: "POST",
        signal,
        body: JSON.stringify({ vehicle_id: vehicleId }),
      }),
    dispatchFreightOffer: (id, vehicleId) =>
      request(`/contracts/${id}/accept`, {
        method: "POST",
        body: JSON.stringify({ vehicle_id: vehicleId }),
      }),
    purchaseVehicle: (modelId) =>
      request("/fleet/purchase", {
        method: "POST",
        body: JSON.stringify({ model_id: modelId }),
      }),
  };
}

export const hub = {
  id: "berlin",
  city_uid: "city-berlin",
  label: "Westhafen",
  city: "Berlin",
  address: "Westhafen 1",
  lat: 52,
  lon: 13,
  resolution_status: "resolved",
};

export const contract = {
  id: "job",
  origin_hub_id: hub.id,
  origin: hub,
  destination: { ...hub, city: "Hamburg" },
  mode: "truck",
  tons: 10,
  cargo: "Steel",
  shipper_name: "A",
  consignee_name: "B",
  eligible_vehicle_ids: ["truck"],
};

export const vehicle = {
  id: "truck",
  name: "Lkw",
  mode: "truck",
  status: "idle",
  hub_id: hub.id,
  hub,
  capacity_tons: 24,
  energy: {
    kind: "diesel",
    unit: "l",
    capacity: 100,
    consumption_per_100km: 20,
    stop_minutes: 10,
    reserve_fraction: 0.1,
  },
  energy_level: 100,
  top_speed_kmh: 90,
};

export const quote = {
  vehicle_id: vehicle.id,
  operating_cost_eur_per_km: 0.62,
  route_geojson: {
    type: "LineString",
    coordinates: [
      [179, 0],
      [-179, 0],
    ],
  },
  distance_km: 100,
  duration_seconds: 3600,
  payout_eur: 2000,
  operating_cost_eur: 500,
  profit_eur: 1500,
};

export const trip = {
  ...quote,
  id: "trip",
  vehicle_id: vehicle.id,
  origin: hub,
  destination: contract.destination,
  contract,
  journey: {
    distance_km: 100,
    segments: [
      {
        phase: "driving",
        starts_at: 0,
        ends_at: 100,
        start_km: 0,
        end_km: 100,
      },
    ],
  },
  departed_at: 0,
  arrives_at: 100,
};

export function createView(path = "/contracts/job") {
  return {
    url: new URL(path, "http://test"),
    cityUid: hub.city_uid,
    state: {
      contracts: [contract],
      vehicles: [vehicle],
      transports: [],
      player: { cash: 25000, completed: 0, reputation: 0 },
      time_scale: 1,
      idle_vehicles: 1,
      active_transports: 0,
    },
    user: { username: "driver" },
    quote: null,
    selectedVehicle: "",
    mutating: false,
    quoting: false,
    get busy() {
      return this.mutating || this.quoting;
    },
    rankings: null,
    catalogue: null,
    panelError: false,
  };
}

export function mountPanel(request = async () => ({})) {
  document.body.replaceChildren(renderShell({ username: "driver" }));
  const panel = new PanelController({
    view: createView(),
    request,
    notify() {},
    now: () => 50,
  });
  panel.render();
  return panel;
}
