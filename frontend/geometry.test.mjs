import test from "node:test";
import assert from "node:assert/strict";
import { eligibleVehicles, matchesFacility } from "./geometry.js";
import { contract, hub, vehicle } from "./test-support/controller-fixtures.mjs";

test("facility matching accepts stable IDs and explicit legacy aliases", () => {
  const facility = {
    ...hub,
    id: "facility-uuid",
    facility_uid: "facility-uuid",
    aliases: ["berlin"],
  };
  assert.equal(matchesFacility(facility, "berlin"), true);
  assert.equal(matchesFacility(facility, facility.facility_uid), true);
  assert.equal(matchesFacility(facility, "unknown"), false);
  const owned = {
    ...vehicle,
    facility_uid: facility.facility_uid,
    hub_id: facility.id,
    hub: facility,
    location_snapshot: facility,
  };
  const job = {
    ...contract,
    origin_facility_uid: facility.facility_uid,
    origin_hub_id: facility.id,
    origin: facility,
  };
  assert.deepEqual(eligibleVehicles([owned], job), [owned]);
});
