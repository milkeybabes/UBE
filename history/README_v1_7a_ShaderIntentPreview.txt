UBE v1.7a - Shader Intent Preview
=================================

Build 194.

This is the first v1.7 shader exploration pass.

Added:
- Shader preview panel for Shader assets.
- Symbolic shader intent visual rather than a Unity/Amplify renderer clone.
- Detects broad shader/material intent from shader name and exposed properties:
  glass, water/caustics, foliage/organic, emissive/glow, UI/unlit, PBR/surface.
- Draws a small educational preview object:
  glass pane, water plane, glow ball, foliage symbol, or generic surface block.
- Shows simple bars for roughness/matte, reflection/specular, edge/fresnel,
  and noise/smudge/wear.
- Material preview now uses the same symbolic preview for shader-heavy materials
  such as glass/water/foliage/emissive materials, instead of only showing a raw
  texture ingredient.
- Material insight now also checks Shader SubShader tags, so transparent/glass
  shaders are not incorrectly described as opaque just because the material
  properties alone are ambiguous.

Important:
This is intentionally educational. It does not decompile Shader Graph, Amplify,
or HLSL, and it does not attempt to reproduce Unity's exact renderer.
It shows the shape/form/intent of the visual recipe.

Kept from v1.6j:
- Recent Open menu.
- Helper flat preview.
- RectTransform visual.
- Canvas inspectors.
- Camera frustum and BoxCollider visuals.
- AnimationClip and AnimatorController inspectors.
- Sprite/SpriteRenderer resolver and previews.
- GLB golf-ball base/normal fixes.
- OpenGL bump/normal preview.
- Filtered export.
- UV infinity crash guard.
