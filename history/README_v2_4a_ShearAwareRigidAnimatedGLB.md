# UBE v2.4a Build 341 — Shear-Aware Rigid Animated GLB Export

Amusement Park's Sheep Carousel exposed an over-conservative Animated GLB
eligibility rule. The legacy `Scene` clip previews correctly as rigid Transform
animation, but several carousel meshes have authored non-uniform local scale.
Earlier builds treated any unequal X/Y/Z scale anywhere in a rigid renderer's
ancestor chain as proof of glTF-inexpressible shear and hid the export action.

Non-uniform scale is valid glTF TRS. It becomes shear only when hierarchy
composition makes the final 3x3 matrix basis non-orthogonal, typically when a
rotation occurs below a non-uniformly scaled ancestor. In the Sheep Carousel,
the animated rotations occur on shear-free branches; rotations above scaled
leaf meshes remain exactly representable.

UBE now:

- samples up to 96 evenly distributed preview-proven poses for eligibility;
- measures the normalized dot products between each rigid matrix's three basis
  columns;
- accepts non-uniform or mirrored scale when those columns remain orthogonal;
- rejects genuine affine shear with the renderer name, time and basis error;
- validates every baked export frame before glTF TRS decomposition;
- keeps the existing rigid-transform, skinned-animation, visibility, duration
  limit and In-place export paths unchanged.

The Sheep Carousel's static matrices show only floating-point orthogonality
error (approximately 1.2e-7), far below the 2e-4 safety threshold. Its 19.920 s
clip can therefore be baked at the authored 25 fps rather than being rejected
solely because of harmless non-uniform scale.
