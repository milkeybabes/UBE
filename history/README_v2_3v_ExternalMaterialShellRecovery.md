# UBE v2.3v — External Material Shell Recovery

Build 335 fixes skinned character meshes whose renderer material is technically
resolved from a shared bundle but provides only a generic shader/material shell
and no colour texture.

Labyrinth example:

- `Hoggle_RIG:hoggle` resolves Material `Lit` from `urp_assets_all.bundle`.
- That external Material supplies URP/Lit shader intent but no base texture.
- The mesh has a full atlas-style UV0 unwrap.
- `Labyrinth_Characters` is the one decisive complete local character Material
  and references `Labyrinth_CombinedAssets_Texture 1`.

UBE now treats this as an incomplete appearance resolution, not a successful
textured material.  Recovery remains limited to skinned meshes with atlas UV
evidence and an unambiguous local character/creature material.  Real external
materials with a resolved base texture are never replaced.
