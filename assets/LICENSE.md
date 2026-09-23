# License and usage notes

This package contains 134 multi-view vehicle SVG assets for 14 catalogue
models. See [MANIFEST.md](MANIFEST.md) and [inventory.json](inventory.json)
for original filenames, roles, current paths and preserved checksums.

## Organization

Each `vehicles/<model_id>/` directory contains the currently used `map.svg`,
`front.svg` and `side-left.svg`. Additional views, parts, variants and sheets
retain their original filenames in `source/`; this name does not imply that
all of them are unprocessed originals.

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
The selected `map.svg` files are normalized for map rendering:
- top-down
- transparent background
- front facing **north/up** at 0° rotation
- suitable for runtime rotation in MapLibre or similar map engines

## Origin and rights
These assets were prepared from AI-generated images created for the user in this ChatGPT conversation, then cropped, normalized and wrapped into recolorable SVG files.

As between the user and OpenAI, rights in the generated output are generally assigned to the user, subject to applicable law and any third-party rights that may exist.

## Important IP note
These sprites are intended to be **brand-neutral game assets** and should not be presented as official manufacturer artwork, official technical drawings or endorsed brand assets.
The user remains responsible for checking downstream legal/IP questions for any public or commercial release.

## No warranty
Provided as-is, without warranty of any kind.

External catalogue photos keep their separate source and license metadata.
The folder reorganization introduces no new license claims or artwork.
