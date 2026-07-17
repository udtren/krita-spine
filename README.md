# Krita Spine Export

Krita Spine Export is a Krita Python plugin that exports document layers as PNG attachments plus Spine JSON, modeled after Esoteric Software's `PhotoshopToSpine.jsx` workflow.

## Usage

Select a **group layer** as the active node, then run **Tools > Scripts > Export to Spine...**. Choose an **export folder**, scale, padding, and export options, then press **Export**.

The active group layer determines the export location:

- A `parentGroupName` folder is created inside the export folder, and an `activeGroupName` folder is created inside it (layer tags are stripped). If the active group has no group parent, only the `activeGroupName` folder is created inside the export folder.
- The Spine JSON is written into the `activeGroupName` folder as `activeGroupName.json`.
- Images are written into an `images` folder inside the `activeGroupName` folder.

If the active node is not a group layer, the export is cancelled and you are asked to change the active node.

Only **visible** layers are exported. Hidden layers, and layers inside hidden groups, are always ignored.

The exporter writes:

- PNG files for exportable layers and `[merge]` groups.
- Spine JSON with `bones`, `slots`, `skins`, and an empty animation.
- Optional `template.png` from the current document projection.

## Supported Tags

Tags can be placed in layer or group names using the same square-bracket style as PhotoshopToSpine.

- `[bone]` or `[bone:name]`
- `[slot]` or `[slot:name]`
- `[skin]` or `[skin:name]`
- `[folder]` or `[folder:name]`
- `[scale:number]`
- `[trim]` or `[trim:false]`
- `[mesh]` or `[mesh:name]`
- `[ignore]`
- `[merge]` on groups
- `[name:pattern]` on groups, where `pattern` contains `*`
- `[path:name]` on layers or merged groups

## Notes

Krita's Python API is not Photoshop's layer compositor, so this version intentionally focuses on reliable layer projection export. It does not reproduce Photoshop-specific adjustment-layer, clipping-mask, mask-bound, selection-only, ruler-origin, or overlay behavior exactly. Krita group projections and layer bounds are used where available.

For non-RGBA/U8 layers, the exporter falls back to Krita's native node PNG save. For RGBA/U8 layers, it writes PNGs via `projectionPixelData` so padding and scale are applied consistently.
