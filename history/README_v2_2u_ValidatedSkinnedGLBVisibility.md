# UBE v2.2u Build 310 — Validated Skinned GLB and Preview Visibility

This build corrects the first skinned animated GLB proof path and makes animation
export follow the visible V/I child state shown in UBE.

## Skinned GLB corrections

- Remaps Unity bone-weight rows through the exact source-vertex map used when OBJ
  geometry is reordered or split by position/UV/normal combinations.
- Writes strictly increasing float32 animation input times and removes duplicate
  end samples before creating glTF animation accessors.
- Omits the optional `skin.skeleton` hint unless a common-root guarantee exists;
  the joint hierarchy remains authoritative.
- Keeps nodes carrying both `mesh` and `skin` at scene root, with the joint/rig
  hierarchy in its own root branch, avoiding parent-transform ambiguity.
- Rejects nested or incompatible skinned mesh layouts rather than creating a GLB
  that only partly follows glTF skinning rules.

## V/I-aware export

`Export Animated GLB…` now follows the current assembled-preview visibility:

- a child hidden with **V** is omitted from the GLB
- a child isolated with **I** is the only visual part exported
- **Shift+V** or **Shift+I** restores the full export set

This is useful for helper, collision, detection, and dummy meshes that are valid
Unity objects but are not intended to appear in the viewed animation.
