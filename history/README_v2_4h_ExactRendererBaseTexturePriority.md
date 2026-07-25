# UBE v2.4h Build 348 — Exact Renderer Base-Texture Priority

Cherry Blossom's `Fern2_sandPS.008` exposed a raw-Mesh context-selection error. The Mesh name contains `sand`, so the semantic name matcher preferred `CherryBlossom_ZenSand` even though the Mesh's only real scene use is an exact `MeshFilter` + sibling `MeshRenderer` assignment to `CherryBlossom_Wind`. That material explicitly stores `_BaseTexture → CherryBlossom_Tex`; its separate `noise_01_3D 1` slot is a wind-deformation input rather than visible colour.

UBE now treats a recognised base-colour texture property on an exact renderer using the selected Mesh as authoritative structural evidence. It always outranks global material/texture-name guesses. Scores are still used to choose among several genuine renderer uses, while auxiliary noise, normal, emission, mask and other shader textures receive no authority boost.

The raw Mesh inspector, automatic 3D preview, OBJ export and GLB export all use the same `best_renderer_context_for_mesh()` decision. The inspector now labels exact base-colour assignments and states the actual Material → Texture pair that preview/export will trust. MeshFilter and owning-GameObject previews therefore remain consistent with the raw Mesh view.

Semantic material matching is retained as a fallback for Mesh assets that have no resolvable exact renderer base-colour assignment. Existing null-material recovery, external-material hydration and course-palette consensus paths are unchanged.
