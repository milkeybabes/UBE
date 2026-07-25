# UBE v2.3z Build 339 — Alternate Character Colour UV Recovery

The Labyrinth `MiscGoblin01_Rig_03:h14_metalPS_011` mesh exposed a third
historical character-texture convention.

Its renderer resolves to the same textureless external URP `Lit` material shell
used by other Labyrinth characters, but its UV channels are different:

- 3,383 vertices;
- UV0 repeats one coordinate only: approximately `(0.140991, 0.764160)`;
- UV1 contains 3,242 distinct coordinates and spans almost the complete 0–1
  texture domain.

Build 338 deliberately rejected constant UV0 meshes, which was safe for ordinary
palette recovery but left this goblin grey. The detailed colour unwrap is stored
on UV1 instead.

Build 339 now evaluates alternate character UV channels only when all of the
following are true:

1. the mesh is proven to be skinned;
2. the renderer uses an external material shell with no usable base texture;
3. one complete local character material wins decisively;
4. UV0 is absent or effectively constant;
5. a later UV channel contains a broad, detailed, high-uniqueness 0–1 atlas
   unwrap.

When that evidence is present, UBE hydrates the original renderer material slot
from the recovered character material and automatically uses the proven alternate
UV channel for the base texture. A non-zero UV channel selected with the `U` key
remains authoritative, so manual inspection is still available.

The automatic channel is recorded in OBJ/GLB metadata and displayed in the 3D
preview context. Hoggle-style broad UV0 atlases, chicken-style compact UV0
palettes and ordinary resolved textured materials are unchanged.
