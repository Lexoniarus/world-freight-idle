import test from "node:test";
import assert from "node:assert/strict";
import { opportunityGroups } from "./map/opportunities.js";
import { selectedLocations } from "./map/selection.js";
import { berlin, offer, other } from "./test-support/freight-fixtures.mjs";

test("opportunities group by UID while selection keeps exact endpoints", () => {
  const contracts = [offer, { ...offer, id: "two" }, { ...offer, id: "other", origin: other }];
  assert.equal(opportunityGroups(contracts, true).size, 2);
  assert.equal(opportunityGroups(contracts, false).get(berlin.id).count, 2);
  const selected = selectedLocations({ transports: [], contracts }, offer.id);
  assert.deepEqual(selected.features[0].geometry.coordinates, [berlin.lon, berlin.lat]);
  assert.equal(selected.features.length, 2);
});
