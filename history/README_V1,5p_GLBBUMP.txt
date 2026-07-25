UBE v1.5p GLB Normal V Match
============================

This build keeps the v1.5o colour atlas fix, but changes the golf-ball normal map handling.

The colour/base texture still needs Unity -> glTF V flipping so the selected atlas tile lands at the same Photoshop/inspector row.

For BallNormalMap_Temp / GolfBallShader-style materials, the normal map now preserves the original Unity/extracted PNG V direction. This matches the earlier GLB behaviour where the dimple bump looked right, while still using the corrected base colour atlas V direction.

Expected golf-ball layout:
- TEXCOORD_0 = Unity UV0 for normal/bump map, keeping Unity V for BallNormalMap_Temp
- TEXCOORD_1 = U-key selected UV channel for the colour atlas, V-flipped for glTF

Check the export log for:
- Base texture V flip applied: yes
- Normal texture V flip applied: no - preserving Unity normal-map V
- Dual texcoord export: yes

v1.5s build 176
----------------
- Adds 3D preview texture-source debug controls.
- B cycles the displayed texture: base / normal-bump / emission / metal-mask.
- N jumps directly to normal/bump texture on UV0.
- Existing U key still cycles UV sets, and M still cycles raw/flip/domain modes.
- This is for diagnosing normal-map alignment visually inside UBE; it does not change the GLB colour fix from v1.5r.
