# UBE v2.3q — Context-aware palette selection

Build 330 corrects palette fallback selection for stripped/runtime materials.

Blokhaven contains both a general `Blokhaven_Swatch_Texture` and specialised
textures such as `Blokhaven_GreenSwatch_Texture`. v2.3p assigned equal scores
to both and alphabetical ordering selected the green sheet for
`Blokhaven_Dynamic_Characters`, producing pale/washed animation colours.

The palette fallback now:

- prefers the unqualified course swatch for generic Dynamic/Character/Block materials;
- selects a specialised swatch only when its qualifier also appears in the material name;
- keeps the v2.3p per-vertex UV0 OBJ rebuild and flat palette colour handling;
- applies the same corrected inference to preview, OBJ and GLB paths.
