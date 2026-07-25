# UBE v2.3a Build 314 — Animation External Colour Hydration

Animation preview now resolves the same external visual dependencies as direct
Object and Material preview before the 3D viewer builds its material cache.

This fixes the order-dependent case where a Homestar animation initially appeared
grey, but became coloured after selecting one of its Materials. The animation path
now follows each visible render item through Renderer -> Material -> recognised
base-colour texture slots such as `_ColorMap`, `_BaseMap`, and `_MainTex`. When the
referenced bundle is available in the project PathID index, it is loaded once and
cached before the animation is displayed.

The resolver remains bounded to the selected animation's render items. A malformed
or unavailable dependency does not prevent playback; the existing external-colour
diagnostic remains the fallback. Object, Mesh, Material, OBJ/GLB export, animated
GLB export, V/I visibility, and all v2.3 functionality are retained.
