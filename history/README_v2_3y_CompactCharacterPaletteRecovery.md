# UBE v2.3y Build 338 — Compact Character Palette Recovery

Labyrinth chicken skins resolve their renderer material to the shared external
URP `Lit` material. That material is a valid reference but contains no base
texture, so UBE must recover appearance from the complete local
`Labyrinth_Characters` material.

Earlier external-shell recovery required a broad UV0 atlas rectangle. The
chicken meshes instead contain 511 vertices and only four distinct UV0 lookup
points, selecting several solid regions from the shared character texture.
Their UV bounds are compact, so the broad-atlas test rejected them and the
preview remained grey.

Build 338 recognises two valid texture-evidence layouts:

1. a conventional broad atlas unwrap;
2. a compact, strongly repeated multi-swatch UV0 lookup.

The compact path requires at least two distinct UV points, a non-zero 2D area,
strong repetition, coordinates close to the normal 0–1 texture domain, a
SkinnedMeshRenderer, a textureless external material shell, and one decisive
local character-material donor. A single constant UV coordinate is never
accepted.

The recovered texture setup is attached to the original renderer material slot,
so direct Mesh, GameObject, AnimationClip, OBJ and GLB paths use the same result.
