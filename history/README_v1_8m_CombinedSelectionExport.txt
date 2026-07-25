UBE v1.8m - Combined Selection Export
=====================================

Build 233

Adds combined export for multi-selected renderable objects.

Workflow:
  1. Ctrl-click or Shift-click two compatible objects/meshes in the tree.
  2. Confirm they line up in the multi-select 3D preview.
  3. Click "Export N Selected as One...".
  4. Choose GLB or OBJ.

GLB mode:
  - Exports one binary .glb file.
  - Selected parts are separate nodes/meshes inside one glTF scene.
  - Embedded textures from the existing GLB export path are preserved where available.
  - Shared Unity/authored coordinates are preserved; parts are not individually re-centred.

OBJ mode:
  - Exports one combined OBJ assembly plus one combined MTL and texture files.
  - Each selected object is written as a separate OBJ object section.
  - Materials are prefixed per source part to avoid name collisions.
  - Shared Unity/authored coordinates are preserved; parts are not individually re-centred.

Also updates the export format wording:
  - GLB is no longer labelled experimental.
  - Multi-selection defaults to GLB because it gives the cleanest one-file assembly.

This is intended for cases such as:
  Tricera.001_LOD0 + Tricera.saddle.001_LOD0
where separately stored Unity objects were authored to the same origin and fit together perfectly.
