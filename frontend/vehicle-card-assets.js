const VEHICLE_CARD_ASSETS = Object.freeze({
  daf_xg_plus_480: Object.freeze({
    front: "/assets/daf_xg_plus_480_front.svg",
    side: "/assets/daf_xg_plus_480_side_left.svg",
  }),
  iveco_sway_500: Object.freeze({
    front: "/assets/iveco_s_way_500_xc13_front.svg",
    side: "/assets/iveco_s_way_500_xc13_side_left.svg",
  }),
  man_tgx_520: Object.freeze({
    front: "/assets/man_tgx_520_d3066_front.svg",
    side: "/assets/man_tgx_520_d3066_side_left.svg",
  }),
  mercedes_actros_l_380: Object.freeze({
    front: "/assets/mercedes_benz_actros_l_om473_380kw_front.svg",
    side: "/assets/mercedes_benz_actros_l_om473_380kw_side_left.svg",
  }),
  mercedes_eactros_600: Object.freeze({
    front: "/assets/mercedes_benz_eactros_600_3pack_lfp_front.svg",
    side: "/assets/mercedes_benz_eactros_600_3pack_lfp_side_left.svg",
  }),
  renault_t_high_520: Object.freeze({
    front: "/assets/renault_trucks_t_high_520_de13_front.svg",
    side: "/assets/renault_trucks_t_high_520_de13_side_left.svg",
  }),
  scania_r460_gas: Object.freeze({
    front: "/assets/scania_r_460_gas_cbg_lbg_front.svg",
    side: "/assets/scania_r_460_gas_cbg_lbg_side_left.svg",
  }),
  volvo_fh_aero_500_isave: Object.freeze({
    front: "/assets/volvo_trucks_fh_aero_500_i_save_front.svg",
    side: "/assets/volvo_trucks_fh_aero_500_i_save_side_left.svg",
  }),
  mercedes_sprinter_317_cdi: Object.freeze({
    front: "/assets/mercedes_benz_sprinter_317_cdi_35t_l3h2_9g_tronic_front.svg",
    side: "/assets/mercedes_benz_sprinter_317_cdi_35t_l3h2_9g_tronic_side_left.svg",
  }),
  vw_crafter_35_130kw: Object.freeze({
    front: "/assets/volkswagen_crafter_35_2_0_tdi_130kw_l3h3_front.svg",
    side: "/assets/volkswagen_crafter_35_2_0_tdi_130kw_l3h3_side_left.svg",
  }),
});

/** Resolve local card assets for one vehicle model.
 * @param {string | undefined} modelId
 * @returns {{front: string, side: string} | null}
 */
export function vehicleCardAssetPaths(modelId) {
  return modelId ? (VEHICLE_CARD_ASSETS[modelId] ?? null) : null;
}
