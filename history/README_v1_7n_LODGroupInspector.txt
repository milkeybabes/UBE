UBE v1.7n - LODGroup Inspector / Preview
=======================================

Adds a lightweight Unity LODGroup inspector and symbolic preview.

What it shows:

- LOD count and owning GameObject
- LOD0 / LOD1 / LOD2 screen-relative transition thresholds
- Fade width / cross-fade fields when exposed
- Renderer list for each LOD level
- Resolved MeshRenderer / SkinnedMeshRenderer names
- Matching mesh names where they can be resolved
- Approximate vertex / triangle counts per renderer and per LOD
- Educational note explaining how LODGroup helps VR/mobile performance

The top preview now draws a simple LOD threshold chart so it is easy to see close/high-detail versus far/cheaper LOD levels.

This is diagnostic/educational. It does not simulate Unity camera distance exactly; it explains the LODGroup structure in the bundle.
