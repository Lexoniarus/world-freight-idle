import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { getVehicleAssets } from "./vehicle-asset-manifest.js";

const modelIds = [
  "daf_xg_plus_480",
  "iveco_sway_500",
  "man_tgx_520",
  "mercedes_actros_l_380",
  "mercedes_eactros_600",
  "renault_t_high_520",
  "scania_r460_gas",
  "volvo_fh_aero_500_isave",
  "mercedes_sprinter_317_cdi",
  "vw_crafter_35_130kw",
  "iveco_daily_35s18",
  "mercedes_atego_818_l",
  "mercedes_atego_1224_l",
  "man_tgl_12_250",
];

test("catalogue models resolve to distinct shipped map assets", () => {
  const paths = modelIds.map((modelId) => {
    const path = getVehicleAssets(modelId)?.map;
    assert.ok(path, modelId);
    assert.equal(existsSync(new URL(`..${path}`, import.meta.url)), true, path);
    return path;
  });
  assert.equal(new Set(paths).size, modelIds.length);
});

test("shipped map assets expose the recolorable paint variable", () => {
  const iveco = readFileSync(
    new URL("../assets/vehicles/iveco_sway_500/map.svg", import.meta.url),
    "utf8",
  );
  const daf = readFileSync(
    new URL("../assets/vehicles/daf_xg_plus_480/map.svg", import.meta.url),
    "utf8",
  );
  assert.match(iveco, /--vehicle-color:#ffffff/i);
  assert.ok(iveco.includes("vehicle-base"));
  assert.notEqual(iveco, daf);
});
