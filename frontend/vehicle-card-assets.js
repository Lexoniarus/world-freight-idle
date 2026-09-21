const VEHICLE_CARD_ASSETS = Object.freeze({
  daf_xg_plus_480: Object.freeze({
    front: "/assets/daf_xg_plus_480_front.svg",
    side: "/assets/daf_xg_plus_480_side_left.svg",
  }),
  iveco_sway_500: Object.freeze({
    front: "/assets/iveco_sway_500_front.svg",
    side: "/assets/iveco_sway_500_side_left.svg",
  }),
  man_tgx_520: Object.freeze({
    front: "/assets/man_tgx_520_front.svg",
    side: "/assets/man_tgx_520_side_left.svg",
  }),
  mercedes_actros_l_380: Object.freeze({
    front: "/assets/mercedes_actros_l_380_front.svg",
    side: "/assets/mercedes_actros_l_380_side_left.svg",
  }),
  mercedes_eactros_600: Object.freeze({
    front: "/assets/mercedes_eactros_600_front.svg",
    side: "/assets/mercedes_eactros_600_side_left.svg",
  }),
  renault_t_high_520: Object.freeze({
    front: "/assets/renault_t_high_520_front.svg",
    side: "/assets/renault_t_high_520_side_left.svg",
  }),
  scania_r460_gas: Object.freeze({
    front: "/assets/scania_r460_gas_front.svg",
    side: "/assets/scania_r460_gas_side_left.svg",
  }),
  volvo_fh_aero_500_isave: Object.freeze({
    front: "/assets/volvo_fh_aero_500_isave_front.svg",
    side: "/assets/volvo_fh_aero_500_isave_side_left.svg",
  }),
  mercedes_sprinter_317_cdi: Object.freeze({
    front: "/assets/mercedes_sprinter_317_cdi_front.svg",
    side: "/assets/mercedes_sprinter_317_cdi_side_left.svg",
  }),
  vw_crafter_35_130kw: Object.freeze({
    front: "/assets/vw_crafter_35_130kw_front.svg",
    side: "/assets/vw_crafter_35_130kw_side_left.svg",
  }),
  iveco_daily_35s18: Object.freeze({
    front: "/assets/iveco_daily_35s18_front.svg",
    side: "/assets/iveco_daily_35s18_side_left.svg",
  }),
  mercedes_atego_818_l: Object.freeze({
    front: "/assets/mercedes_atego_818_l_front.svg",
    side: "/assets/mercedes_atego_818_l_side_left.svg",
  }),
  mercedes_atego_1224_l: Object.freeze({
    front: "/assets/mercedes_atego_1224_l_front.svg",
    side: "/assets/mercedes_atego_1224_l_side_left.svg",
  }),
  man_tgl_12_250: Object.freeze({
    front: "/assets/man_tgl_12_250_front.svg",
    side: "/assets/man_tgl_12_250_side_left.svg",
  }),
});

/** Resolve normalized local UI assets for one vehicle model.
 * @param {string | undefined} modelId
 * @returns {{front: string, side: string} | null}
 */
export function vehicleCardAssetPaths(modelId) {
  return modelId ? (VEHICLE_CARD_ASSETS[modelId] ?? null) : null;
}
