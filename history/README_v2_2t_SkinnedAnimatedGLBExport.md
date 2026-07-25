# UBE v2.2t Build 309 — Skinned Animated GLB Export

Animated GLB export now supports fully resolved SkinnedMeshRenderer previews in
addition to the rigid Transform export introduced in v2.2s.

For each accepted skin UBE exports:

- the original mesh, materials and embedded textures
- JOINTS_0 and WEIGHTS_0 vertex attributes
- glTF skin.joints and inverseBindMatrices
- the complete local Transform chains from the animation root to each deforming bone
- intermediary rig/control nodes needed to preserve authored local TRS
- sampled translation, rotation and scale channels at the source clip rate

The local hierarchy is deliberate: it preserves non-uniform bone/control scale and
avoids decomposing a sheared global matrix. The exporter may duplicate a shared rig
when a character uses multiple skinned renderers; this is a correctness-first proof
path and can be optimised later.

The export option remains hidden when bones, weights, bind poses, target paths,
constraints, runtime linkage, or the renderer hierarchy are incomplete. Geometry
vertex count must also match the decoded Unity weight table exactly.
