import { VehicleColorAssets } from "../vehicle-color-assets.js";

export const model = "iveco_sway_500";
export const source = "<svg style='--vehicle-color:#ffffff'></svg>";
const compose = async (_original, _mask, color) => `<svg style="--vehicle-color:${color}"></svg>`;

export class TestColorAssets extends VehicleColorAssets {
  constructor(load) {
    super(load, compose);
  }
}

export const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
