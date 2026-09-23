/** Evaluate the server itinerary using the same half-open intervals as Python.
 * @param {import('./types.js').JourneyPlan} journey
 * @param {number} elapsedSeconds
 * @returns {{phase: string, fraction: number, energyLevel: number | null, remainingSeconds: number}}
 */
export function journeyProgress(journey, elapsedSeconds) {
  if (!Number.isFinite(elapsedSeconds) || !journey?.segments?.length || !(journey.distance_km > 0))
    throw new Error("Ungültiger Fahrtplan");
  const elapsed = Math.max(0, elapsedSeconds);
  for (const part of journey.segments) {
    if (elapsed < part.ends_at) {
      const ratio = (elapsed - part.starts_at) / (part.ends_at - part.starts_at);
      const distance = part.start_km + (part.end_km - part.start_km) * ratio;
      let energyLevel = part.start_energy ?? null;
      if (part.phase === "driving" && energyLevel !== null && part.end_energy != null)
        energyLevel += (part.end_energy - energyLevel) * ratio;
      return {
        phase: part.phase,
        fraction: distance / journey.distance_km,
        energyLevel,
        remainingSeconds: part.ends_at - elapsed,
      };
    }
  }
  return {
    phase: "arrived",
    fraction: 1,
    energyLevel: journey.segments.at(-1).end_energy ?? null,
    remainingSeconds: 0,
  };
}

/** Evaluate an owned or public transport at synchronized server time.
 * @param {{journey: import('./types.js').JourneyPlan, departed_at: number}} trip
 * @param {number} now
 */
export function transportProgress(trip, now) {
  return journeyProgress(trip.journey, now - trip.departed_at);
}

/** Translate calculated phases without introducing new vehicle statuses.
 * @param {string} phase
 * @returns {string}
 */
export function phaseLabel(phase) {
  return { driving: "Unterwegs", refuelling: "Tankt", charging: "Lädt", arrived: "Ankunft" }[phase];
}
