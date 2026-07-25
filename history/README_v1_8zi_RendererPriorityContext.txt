UBE v1.8zi build 255 - Renderer Context Priority

Refines raw Mesh auto context selection after the source-aware and multi-stream fixes.

Problem seen on HatchlingGeo:
  The loose material-name candidate scored higher because HatchlingTex appeared
  twice in the Material texture list.  It then beat the actual SkinnedMeshRenderer
  context by a few points.

Fix:
  - Duplicate Texture2D names no longer double-score material-name candidates.
  - Real MeshRenderer/SkinnedMeshRenderer contexts get priority over loose
    material-only candidates when they use the same material/texture.
  - Exact Mesh→Renderer→Material→Texture rows now show the material texture
    property/relation and UV scale/offset when available.

Expected result:
  HatchlingGeo should prefer an actual SkinnedMeshRenderer context rather than
  the material-only semantic candidate.
