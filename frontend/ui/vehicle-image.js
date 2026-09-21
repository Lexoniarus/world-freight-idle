import { vehicleCardAssetPaths } from "../vehicle-card-assets.js";
import { html } from "./dom.js";
import { truckIllustration } from "./illustrations.js";

/** Render normalized local game views first, then verified catalogue photography.
 * @param {{id?: string, model_id?: string, name: string, capacity_tons: number, image?: import('../types.js').VehicleImage | null}} vehicle
 * @returns {DocumentFragment}
 */
export function renderVehicleImage(vehicle) {
  const modelId = vehicle.model_id ?? vehicle.id;
  const localAssets = vehicleCardAssetPaths(modelId);

  if (localAssets) {
    return html`<figure class="vehicle-photo vehicle-game-asset">
      <div class="vehicle-photo-grid">
        <div class="vehicle-asset-view">
          <div class="vehicle-photo-frame">
            <img
              data-local-vehicle-asset
              src="${localAssets.front}"
              alt="${vehicle.name} – Frontansicht"
              width="512"
              height="512"
              loading="lazy"
              decoding="async"
            />
          </div>
          <span class="vehicle-view-label">Frontansicht</span>
        </div>
        <div class="vehicle-asset-view">
          <div class="vehicle-photo-frame">
            <img
              data-local-vehicle-asset
              src="${localAssets.side}"
              alt="${vehicle.name} – Seitenansicht"
              width="896"
              height="512"
              loading="lazy"
              decoding="async"
            />
          </div>
          <span class="vehicle-view-label">Seitenansicht</span>
        </div>
      </div>
      <figcaption><span>Spielgrafik</span></figcaption>
    </figure>`;
  }

  const photo = vehicle.image;
  if (!photo) return truckIllustration(vehicle.capacity_tons <= 12);
  const scope =
    {
      exact_variant: "Foto der Modellvariante",
      exact_model: "Foto des Modells",
      model_family: "Beispielfoto der Modellfamilie",
      generic: "Symbolfoto",
    }[photo.scope] || "Fahrzeugfoto";
  return html`<figure class="vehicle-photo" data-image-state="loading">
    <div class="vehicle-photo-frame">
      <div class="vehicle-photo-fallback">${truckIllustration(vehicle.capacity_tons <= 12)}</div>
      <img
        data-vehicle-photo
        src="${photo.url}"
        alt="${vehicle.name} – ${scope}"
        width="640"
        height="480"
        loading="lazy"
        decoding="async"
        crossorigin="anonymous"
        referrerpolicy="no-referrer"
      />
    </div>
    <figcaption>
      <span>${photo.attribution}</span>
      <a href="${photo.source_url}" target="_blank" rel="noopener noreferrer">Quelle</a> ·
      <a href="${photo.license_url}" target="_blank" rel="noopener noreferrer"
        >${photo.license_name}</a
      >
      <span class="vehicle-image-scope">${scope}</span>
      <span class="vehicle-image-error">Foto nicht erreichbar – Ersatzillustration</span>
    </figcaption>
  </figure>`;
}
