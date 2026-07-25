# UBE v2.0o Build 277 — Texture UV Clarity

Texture2D and Object inspectors now explain the distinction between texture data, mesh UV channels, material texture slots, and shader sampling.

## Texture2D inspector

- Renames the atlas section to **Mesh UV comparison on this texture**.
- States clearly that Texture2D assets do not own UV coordinates; UV0/UV1/UV2 belong to each renderer's attached mesh.
- Explains that UBE projects every available mesh UV channel onto the selected image for comparison, while the Material/Shader decides the actual texture/channel pairing.
- Replaces the old golf-ball-specific general advice with a generic Unity explanation: UV0 is the conventional starting point for `_BaseMap` / `_MainTex`, while UV1+ are commonly secondary/lightmap data, but custom shaders can differ.
- Labels the smallest rectangle as **smallest atlas candidate (not confirmed)** rather than implying confirmed display usage.
- Explains that nearly full-size UV1/UV2 boxes can be secondary unwraps and do not prove the colour texture uses those channels.
- Makes the 48-renderer display cap explicit, so users know an object's exact UV row may only appear in that object's inspector.

## Object/render-chain inspector

- Renames the block to **Mesh UV channels projected onto referenced textures**.
- Shows each texture's material slot name, such as `CherryBlossom_Tex [_BaseMap]` or `Caustics_04 [_CausticsTextureArray]`.
- Adds a reminder that the 3D preview status line shows the currently displayed UV channel and that `U` cycles the available channels.

Clickable texture-atlas overlay links remain intact with the revised headings and candidate wording.
