export const distanceLabels = {
  short: "Kurzstrecke",
  medium: "Mittelstrecke",
  long: "Fernverkehr",
};
export const classLabels = {
  general: "Stückgut",
  parcel: "Paket / Kleinfracht",
  dry_bulk: "Schüttgut",
  liquid_bulk: "Flüssiggut",
  temperature_controlled: "Kühltransport",
  special: "Spezialtransport",
};
export function humanLabel(value) {
  return distanceLabels[value] ?? classLabels[value] ?? value;
}
