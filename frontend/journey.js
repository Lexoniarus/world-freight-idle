/** Evaluate the server itinerary using the same half-open intervals as Python.
 * @param {import('./types.js').JourneyPlan} journey
 * @param {number} elapsedSeconds
 * @returns {{phase: string, fraction: number, distanceKm: number, energyLevel: number | null, remainingSeconds: number}}
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
        distanceKm: distance,
        energyLevel,
        remainingSeconds: part.ends_at - elapsed,
      };
    }
  }
  return {
    phase: "arrived",
    fraction: 1,
    distanceKm: journey.distance_km,
    energyLevel: journey.segments.at(-1).end_energy ?? null,
    remainingSeconds: 0,
  };
}

/** Evaluate an owned or public transport at synchronized server time.
 * @param {{journey: import('./types.js').JourneyPlan, departed_at: number, route_legs?: import('./types.js').RouteLeg[]}} trip
 * @param {number} now
 */
export function transportProgress(trip, now) {
  const progress = journeyProgress(trip.journey, now - trip.departed_at);
  const leg = trip.route_legs?.find((part) => progress.distanceKm < part.end_km);
  return { ...progress, stage: leg?.purpose ?? null };
}

/** Translate calculated phases without introducing new vehicle statuses.
 * @param {string} phase
 * @param {string | null} [stage]
 * @returns {string}
 */
export function phaseLabel(phase, stage = null) {
  if (phase === "driving" && stage)
    return stage === "approach" ? "Zur Abholung" : "Fracht unterwegs";
  return { driving: "Unterwegs", refuelling: "Tankt", charging: "Lädt", arrived: "Ankunft" }[phase];
}
