# License and usage notes

This package contains **map-ready, brand-neutral top-down vehicle sprites** for the World Freight Idle project.

## Contents
- 10 individual SVG files
- 1 `LICENSE.md`
- 1 `MANIFEST.md`
This package contains **multi-view vehicle SVG assets** prepared for the World Freight Idle project.

## Contents
- full vehicle sheet SVGs
- extracted single-view SVGs with clear perspective names
- `LICENSE.md`
- `MANIFEST.md`

## Naming scheme
Examples:
- `daf_xg_plus_480_sheet.svg`
- `daf_xg_plus_480_top_complete.svg`
- `daf_xg_plus_480_front.svg`
- `mercedes_benz_sprinter_317_cdi_35t_l3h2_9g_tronic_side_right.svg`

## Technical format
Each SVG is a self-contained hybrid asset:
- embedded PNG base image
- embedded recolor mask
- CSS-style recolor variable on the root SVG

Change the vehicle paint color like this:
- optional recolor via the root SVG variable, for example:

```svg
style="--vehicle-color:#2979ff"
```

## Intended use
These files are normalized for map rendering:
- top-down
- transparent background
- front facing **north/up** at 0° rotation
- suitable for runtime rotation in MapLibre or similar map engines

## Origin and rights
These assets were prepared from AI-generated images created for the user in this ChatGPT conversation, then cropped, normalized and wrapped into recolorable SVG files.
## Origin and rights
These assets were prepared from AI-generated images created for the user in this ChatGPT conversation, then cropped and wrapped into SVG files.

As between the user and OpenAI, rights in the generated output are generally assigned to the user, subject to applicable law and any third-party rights that may exist.

## Important IP note
These sprites are intended to be **brand-neutral game assets** and should not be presented as official manufacturer artwork, official technical drawings or endorsed brand assets.
These files are intended as **game production assets** and should not be presented as official manufacturer artwork, official technical drawings or endorsed brand material.
The user remains responsible for checking downstream legal/IP questions for any public or commercial release.

## No warranty
Provided as-is, without warranty of any kind.
