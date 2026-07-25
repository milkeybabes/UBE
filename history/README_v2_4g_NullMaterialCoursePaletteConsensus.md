# UBE v2.4g Build 347 — Null-Material Course Palette Consensus

Alice's Dodo Caucus animation revealed a second explicit-null renderer pattern. All sixteen visible character and stump MeshRenderers serialize `PPtr(0, 0)` material slots, but unlike Tokyo there is no duplicate static/runtime mesh family with a real material assignment. Every affected mesh nevertheless contains a convincing repeated UV0 palette lookup: the eight characters use 6–25 authored swatch points, while each stump uses four.

The bundle retains three complete course colour materials—`Alice_Color_Dynamic`, `Alice_Color_Storybook_Dynamic`, and `Alice_Easy_Color`—and all three independently resolve their base colour slot to the same 4096×4096 `Alice_Texture` (PathID `1269677832550941796`). `Alice_Easy_Checkerboard` points elsewhere and is excluded as a specialised material.

UBE now keeps the Tokyo exact-family recovery as first priority. Only when no textured mesh-family donor exists does it consider this new consensus path. The renderer must have literal null slots, the mesh must carry an authored PS/runtime suffix and repeated palette UV0 evidence, candidate materials must be local same-course colour materials, effect/environment variants are excluded, and the winning base-texture group must beat every alternative decisively. The chosen shader variant may be uncertain, but the visible colour texture is not guessed when all close candidates agree.

The recovered appearance is shared by raw Mesh, GameObject and AnimationClip preview and by OBJ/GLB export. Existing genuine, stripped, external or already textured materials remain authoritative and bypass this fallback.
