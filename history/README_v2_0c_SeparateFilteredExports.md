# UBE v2.0c — Separate Filtered/Branch Exports

Build 265

## New export mode

When two or more exportable Mesh/Object results are selected, the Export Options dialog now has a separate **Output** selector:

- **Separate assets** — exports every result independently.
  - GLB: one `.glb` file per asset.
  - OBJ: one OBJ/MTL package per asset, plus referenced textures.
- **Combined assembly** — exports all results into one GLB scene or one combined OBJ/MTL assembly.

Filtered, branch and whole-bundle batch exports default to **Separate assets**. A direct multi-selection export from the 3D preview defaults to **Combined assembly**, preserving the established multi-selection workflow.

## Combined batch correction

Combined filtered/branch exports are no longer restricted to the first four records. The four-object limit belongs only to the interactive multi-selection preview. An explicit combined export of 14 filtered records now attempts to include all 14.

## Notes

- Separate exports retain the existing safe filename behavior; duplicate names gain a Path ID suffix.
- Ground/up-axis conversion and the active UV channel continue to apply to each exported mesh/object.
