UBE v1.8j - LOD Step Preserve View
===================================

Small quality-of-life fix for LODGroup previews.

When a parent LODGroup object is previewing material-aware LOD children, pressing I
now swaps LOD0 / LOD1 / LOD2 while preserving the current 3D viewer camera state:

  - zoom / distance
  - orbit rotation
  - pan position
  - FOV
  - close-clip setting

This makes it much easier to zoom into a detail, then press I repeatedly and compare
how the lower-resolution LOD versions differ without the view snapping back to the
default framing each time.

Initial LODGroup selection still frames the model normally; only later LOD stepping
preserves the view.
