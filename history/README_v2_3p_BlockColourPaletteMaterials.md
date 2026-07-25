# UBE v2.3p Build 329 — Block-Colour Palette Materials

This build corrects flat-colour Unity assets that were previously shown with an
entire colour atlas stretched across their geometry.

## Palette UV recognition

Many stylised meshes use:

- UV0: a handful of repeated points selecting colours from a swatch texture;
- UV1: a conventional full unwrap used by other shader features.

UBE now records this layout as palette/swatch intent and reliably exports the
selected Unity UV channel.

## Robust OBJ UV replacement

UnityPy may deduplicate OBJ `vt` rows, so the old one-for-one UV replacement
could silently fail. UBE now rebuilds texture coordinates per vertex and
rewrites face UV indices when necessary. This keeps group preview, OBJ output
and material appearance aligned.

## Runtime-assigned palette materials

When a palette-like material serializes without a texture slot, UBE may recover
a clearly named swatch/palette Texture2D from the loaded bundle, but only when
the mesh itself has the characteristic repeated palette UV0 layout.

Material-only fallbacks are now neutral white instead of dark fallback grey.
