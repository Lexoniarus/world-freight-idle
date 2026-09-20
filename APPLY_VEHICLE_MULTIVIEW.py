from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    if new in content:
        print(f"Already patched: {path.relative_to(ROOT)}")
        return
    if old not in content:
        raise RuntimeError(
            f"Expected block not found in {path.relative_to(ROOT)}. "
            "The branch may have changed; refusing to patch blindly."
        )
    path.write_text(content.replace(old, new, 1), encoding="utf-8")
    print(f"Updated: {path.relative_to(ROOT)}")


def append_once(path: Path, marker: str, block: str) -> None:
    content = path.read_text(encoding="utf-8")
    if marker in content:
        print(f"Already patched: {path.relative_to(ROOT)}")
        return
    separator = "" if content.endswith("\n") else "\n"
    path.write_text(content + separator + "\n" + block.strip() + "\n", encoding="utf-8")
    print(f"Updated: {path.relative_to(ROOT)}")


def write_once(path: Path, content: str) -> None:
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == content:
            print(f"Already present: {path.relative_to(ROOT)}")
            return
    path.write_text(content, encoding="utf-8")
    print(f"Created/updated: {path.relative_to(ROOT)}")


catalogue = """const VEHICLE_CARD_ASSETS = Object.freeze({
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
"""
write_once(ROOT / "frontend" / "vehicle-card-assets.js", catalogue)

vehicle_image = """import { vehicleCardAssetPaths } from "../vehicle-card-assets.js";
import { html } from "./dom.js";
import { truckIllustration } from "./illustrations.js";

/** Render local game assets first, then verified catalogue photography as fallback.
 * @param {{id?: string, model_id?: string, name: string, capacity_tons: number, image?: import('../types.js').VehicleImage | null}} vehicle
 * @returns {DocumentFragment}
 */
export function renderVehicleImage(vehicle) {
  const modelId = vehicle.model_id ?? vehicle.id;
  const localAssets = vehicleCardAssetPaths(modelId);

  if (localAssets) {
    return html`<figure class="vehicle-photo vehicle-game-asset vehicle-photo-multiview">
      <div class="vehicle-photo-grid">
        <div class="vehicle-photo-frame vehicle-photo-frame-front">
          <div class="vehicle-photo-fallback">${truckIllustration(vehicle.capacity_tons <= 12)}</div>
          <img
            data-vehicle-photo
            data-local-vehicle-asset
            src="${localAssets.front}"
            alt="${vehicle.name} – Frontansicht"
            width="640"
            height="480"
            loading="lazy"
            decoding="async"
          />
        </div>
        <div class="vehicle-photo-frame vehicle-photo-frame-side">
          <div class="vehicle-photo-fallback">${truckIllustration(vehicle.capacity_tons <= 12)}</div>
          <img
            data-vehicle-photo
            data-local-vehicle-asset
            src="${localAssets.side}"
            alt="${vehicle.name} – Seitenansicht"
            width="640"
            height="480"
            loading="lazy"
            decoding="async"
          />
        </div>
      </div>
      <figcaption>
        <span>Spielgrafik</span>
        <span class="vehicle-image-scope">Frontansicht · Seitenansicht</span>
      </figcaption>
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
      <div class="vehicle-photo-fallback">
        ${truckIllustration(vehicle.capacity_tons <= 12)}
      </div>
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
"""
write_once(ROOT / "frontend" / "ui" / "vehicle-image.js", vehicle_image)

append_once(
    ROOT / "frontend" / "style.css",
    "/* Local multiview vehicle assets for fleet and shop cards. */",
    """
/* Local multiview vehicle assets for fleet and shop cards. */
.vehicle-photo-multiview .vehicle-photo-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.85rem;
}

.vehicle-photo-multiview .vehicle-photo-frame {
  min-height: 12rem;
  padding: 0.5rem;
  background:
    radial-gradient(circle at 50% 38%, #27465a 0, #173142 42%, #102333 72%);
}

.vehicle-photo-multiview .vehicle-photo-frame img {
  object-fit: contain;
  padding: 0.3rem;
}

.vehicle-photo-multiview figcaption {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem 0.7rem;
  align-items: center;
}

@media (max-width: 720px) {
  .vehicle-photo-multiview .vehicle-photo-grid {
    grid-template-columns: 1fr;
  }
}
""",
)

replace_once(
    ROOT / "frontend" / "vehicle-image.test.mjs",
    'import { renderVehicleImage } from "./ui/vehicle-image.js";',
    'import { vehicleCardAssetPaths } from "./vehicle-card-assets.js";\nimport { renderVehicleImage } from "./ui/vehicle-image.js";',
)

append_once(
    ROOT / "frontend" / "vehicle-image.test.mjs",
    'test("local multiview assets take precedence in fleet and shop cards", () => {',
    """
test("local multiview assets take precedence in fleet and shop cards", () => {
  assert.deepEqual(vehicleCardAssetPaths("iveco_sway_500"), {
    front: "/assets/iveco_s_way_500_xc13_front.svg",
    side: "/assets/iveco_s_way_500_xc13_side_left.svg",
  });
  assert.deepEqual(vehicleCardAssetPaths("daf_xg_plus_480"), {
    front: "/assets/daf_xg_plus_480_front.svg",
    side: "/assets/daf_xg_plus_480_side_left.svg",
  });
  assert.equal(vehicleCardAssetPaths("mercedes_atego_818_l"), null);

  document.body.replaceChildren(
    renderVehicleImage({
      ...vehicle,
      model_id: "iveco_sway_500",
    }),
  );

  const images = [...document.querySelectorAll("img[data-local-vehicle-asset]")];
  assert.equal(images.length, 2);
  assert.equal(images[0].getAttribute("src"), "/assets/iveco_s_way_500_xc13_front.svg");
  assert.equal(images[1].getAttribute("src"), "/assets/iveco_s_way_500_xc13_side_left.svg");
  assert.match(document.body.textContent, /Frontansicht/);
  assert.match(document.body.textContent, /Seitenansicht/);
});
""",
)

append_once(
    ROOT / "docs" / "TARGET.md",
    "## Abnahme – lokale Mehransichten in Flotte und Shop",
    """
## Abnahme – lokale Mehransichten in Flotte und Shop

- [x] Verfügbare lokale Spielassets werden in Flotte und Shop bevorzugt vor Katalogfotos gezeigt.
- [x] Fahrzeugkarten zeigen sowohl Front- als auch Seitenansicht derselben Spielassetserie.
- [x] Die Mehransicht bleibt responsive und bricht auf kleinen Displays sauber auf eine Spalte um.
- [x] Modelle ohne lokale Spielassets behalten das verifizierte Katalogfoto beziehungsweise die bestehende Illustration.
""",
)

append_once(
    ROOT / "docs" / "ARCHITECTURE.md",
    "## Lokale Mehransichten für Flotte und Shop",
    """
## Lokale Mehransichten für Flotte und Shop

`frontend/vehicle-card-assets.js` kapselt die Zuordnung von Modell-ID zu den
lokalen UI-Ansichten. `renderVehicleImage` bevorzugt diese same-origin Assets
und rendert bei unterstützten Modellen eine kleine Mehransicht aus Front- und
Seitenansicht. Die Flotten- und Shop-Views bleiben dadurch unverändert an eine
einzige Darstellungsfunktion gebunden. Modelle ohne lokale Mehransicht fallen
weiterhin auf das verifizierte Katalogfoto oder die bestehende Illustration
zurück.
""",
)

print("Vehicle multiview patch complete.")
