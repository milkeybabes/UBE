# UBE v2.4c Build 343 — Mixed Point-Sampled Metal UV Recovery

Amusement Park's `FerrisWheel_Base_metalPS.003` and `.005` exposed an older
custom-shader UV convention that is neither an ordinary atlas unwrap nor a
simple palette mesh.

Each mesh contains 113 vertices and 56 triangles. UV0 combines two unrelated
roles:

- 66 vertices / 34 small-detail triangles repeat one authored swatch point at
  approximately `(0.416992, 0.861816)`;
- 47 vertices / 22 large-panel triangles use an out-of-range auxiliary mapping;
- UV1 is a conventional almost-unique full unwrap.

Applying `APark_Easy_Color._BaseMap` directly to every raw UV0 coordinate paints
large sections of the complete course atlas over the ferris-wheel panels. The
large auxiliary faces occupy over sixty times the surface area of the small
swatch details, making the error especially conspicuous.

UBE now recognises this mixed point-sampled PS layout conservatively. Recovery
requires all of the following evidence:

- a genuine resolved base texture;
- a `metalPS`, `woodPS`, `glassPS` or equivalent material-family mesh name;
- one dominant in-range UV0 swatch used by at least 45% of the vertices;
- a broad, almost-unique alternate UV channel;
- completely separate swatch and auxiliary triangles;
- mostly out-of-range auxiliary faces whose surface area dominates the swatch
  details by at least four times.

Only the proven auxiliary-face vertices are redirected to the dominant authored
swatch for base-colour preview/export. Geometry and the real material remain
unchanged. Explicitly selecting another UV channel with `U` bypasses the
automatic recovery for diagnostics.

A scan of more than 1,000 PS-style meshes in the supplied Amusement Park bundle
triggered the rule only for the two matching ferris-wheel meshes. The normal
LOD0/LOD1 ferris-wheel bases and all other tested PS meshes remained unchanged.
