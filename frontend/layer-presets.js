export const layerLabels = {
  hubs: "Relevante Standorte",
  orders: "Aufträge",
  vehicles: "Eigene Fahrzeuge",
  multiplayer: "Multiplayer-Verkehr",
  routes: "Transportrouten",
  preview: "Routenvorschau",
};
const base = {
  hubs: true,
  orders: false,
  vehicles: true,
  multiplayer: false,
  routes: true,
  preview: true,
};
export const layerPresets = {
  world: { ...base, multiplayer: true },
  contracts: { ...base, orders: true, routes: false },
  fleet: { ...base },
  transports: { ...base },
  company: { ...base, routes: false },
  leaderboard: { ...base, multiplayer: true, routes: false },
};
export function presetFor(url) {
  const name = url.pathname.split("/")[1];
  return name in layerPresets ? name : "world";
}
