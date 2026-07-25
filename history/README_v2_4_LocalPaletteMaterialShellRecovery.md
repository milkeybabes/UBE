# UBE v2.4 Build 340 — Local Palette Material Shell Recovery

Amusement Park's `H17e_birds` exposed a rigid-renderer variation of the
runtime-material problem. The six moving bird groups contain twelve ordinary
`MeshRenderer` parts. Every renderer resolves successfully to the local
material `B_APark_Swatch_texture`, but that material serializes with no texture
slots and only a neutral grey colour. The game supplies the real course colour
appearance at runtime.

UBE now recognises a resolved local material as a palette shell only when its
name explicitly identifies a swatch/palette, it has no usable base texture, and
one complete same-course colour material wins decisively. Candidate selection
uses shared semantic tokens, explicit Easy/Hard context and actual material
reference frequency; it is never based on alphabetical order. In this bundle,
`APark_Easy_Color` decisively supplies `AmusementPark_Easy_Texture`, while the
original renderer material slot remains intact.

The bird body meshes use six repeated UV0 swatch points. Their shared secondary
mesh uses one authored UV0 point for a single flat colour. A constant UV remains
too ambiguous globally, but it is now accepted when the named palette-shell
recovery has already proven the material intent. Both layouts use nearest
sampling and UV0. Existing textured materials, unnamed neutral materials and
ambiguous Easy/Hard candidates remain unchanged.
