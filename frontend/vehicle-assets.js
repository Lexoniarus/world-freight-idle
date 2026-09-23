/** @typedef {Readonly<{map: string, front: string, side: string}>} VehicleAssets */

/** @type {Readonly<Record<string, VehicleAssets>>} */
const VEHICLE_ASSETS = Object.freeze({
  daf_xg_plus_480: Object.freeze({
    map: "/assets/vehicles/daf_xg_plus_480/map.svg",
    front: "/assets/vehicles/daf_xg_plus_480/front.svg",
    side: "/assets/vehicles/daf_xg_plus_480/side-left.svg",
  }),
  iveco_daily_35s18: Object.freeze({
    map: "/assets/vehicles/iveco_daily_35s18/map.svg",
    front: "/assets/vehicles/iveco_daily_35s18/front.svg",
    side: "/assets/vehicles/iveco_daily_35s18/side-left.svg",
  }),
  iveco_sway_500: Object.freeze({
    map: "/assets/vehicles/iveco_sway_500/map.svg",
    front: "/assets/vehicles/iveco_sway_500/front.svg",
    side: "/assets/vehicles/iveco_sway_500/side-left.svg",
  }),
  man_tgl_12_250: Object.freeze({
    map: "/assets/vehicles/man_tgl_12_250/map.svg",
    front: "/assets/vehicles/man_tgl_12_250/front.svg",
    side: "/assets/vehicles/man_tgl_12_250/side-left.svg",
  }),
  man_tgx_520: Object.freeze({
    map: "/assets/vehicles/man_tgx_520/map.svg",
    front: "/assets/vehicles/man_tgx_520/front.svg",
    side: "/assets/vehicles/man_tgx_520/side-left.svg",
  }),
  mercedes_actros_l_380: Object.freeze({
    map: "/assets/vehicles/mercedes_actros_l_380/map.svg",
    front: "/assets/vehicles/mercedes_actros_l_380/front.svg",
    side: "/assets/vehicles/mercedes_actros_l_380/side-left.svg",
  }),
  mercedes_atego_1224_l: Object.freeze({
    map: "/assets/vehicles/mercedes_atego_1224_l/map.svg",
    front: "/assets/vehicles/mercedes_atego_1224_l/front.svg",
    side: "/assets/vehicles/mercedes_atego_1224_l/side-left.svg",
  }),
  mercedes_atego_818_l: Object.freeze({
    map: "/assets/vehicles/mercedes_atego_818_l/map.svg",
    front: "/assets/vehicles/mercedes_atego_818_l/front.svg",
    side: "/assets/vehicles/mercedes_atego_818_l/side-left.svg",
  }),
  mercedes_eactros_600: Object.freeze({
    map: "/assets/vehicles/mercedes_eactros_600/map.svg",
    front: "/assets/vehicles/mercedes_eactros_600/front.svg",
    side: "/assets/vehicles/mercedes_eactros_600/side-left.svg",
  }),
  mercedes_sprinter_317_cdi: Object.freeze({
    map: "/assets/vehicles/mercedes_sprinter_317_cdi/map.svg",
    front: "/assets/vehicles/mercedes_sprinter_317_cdi/front.svg",
    side: "/assets/vehicles/mercedes_sprinter_317_cdi/side-left.svg",
  }),
  renault_t_high_520: Object.freeze({
    map: "/assets/vehicles/renault_t_high_520/map.svg",
    front: "/assets/vehicles/renault_t_high_520/front.svg",
    side: "/assets/vehicles/renault_t_high_520/side-left.svg",
  }),
  scania_r460_gas: Object.freeze({
    map: "/assets/vehicles/scania_r460_gas/map.svg",
    front: "/assets/vehicles/scania_r460_gas/front.svg",
    side: "/assets/vehicles/scania_r460_gas/side-left.svg",
  }),
  volvo_fh_aero_500_isave: Object.freeze({
    map: "/assets/vehicles/volvo_fh_aero_500_isave/map.svg",
    front: "/assets/vehicles/volvo_fh_aero_500_isave/front.svg",
    side: "/assets/vehicles/volvo_fh_aero_500_isave/side-left.svg",
  }),
  vw_crafter_35_130kw: Object.freeze({
    map: "/assets/vehicles/vw_crafter_35_130kw/map.svg",
    front: "/assets/vehicles/vw_crafter_35_130kw/front.svg",
    side: "/assets/vehicles/vw_crafter_35_130kw/side-left.svg",
  }),
});

/** Resolve the shipped views for a catalogue model without a fallback choice.
 * @param {string | undefined | null} modelId
 * @returns {VehicleAssets | null}
 */
export function getVehicleAssets(modelId) {
  return modelId && Object.hasOwn(VEHICLE_ASSETS, modelId) ? VEHICLE_ASSETS[modelId] : null;
}
