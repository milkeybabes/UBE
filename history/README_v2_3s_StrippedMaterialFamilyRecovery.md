# UBE v2.3s — Stripped Material Family Recovery

Unity runtime materials can serialize with a meaningful name but no shader,
texture slots or colours. UBE now searches for one unambiguous complete sibling
Material in the same naming family before using the broader palette/swatch
fallback.

For Blokhaven, `Blokhaven_Dynamic_Characters` can inherit the real `_ColorMap`
setup from `Blokhaven_Dynamic`. The selected Mesh keeps its own UV0 palette
lookup, so each part still chooses its authored flat colour. This is based on
material-family evidence and mesh UV data, not on the `PS` filename suffix.

The recovery is conservative: the sibling must have a strong family-name match,
a real base texture, and no near-tied alternative. Ordinary materials with saved
texture references are unchanged. OBJ preview/export, animation/group preview
and GLB export use the same recovered material bundle.
