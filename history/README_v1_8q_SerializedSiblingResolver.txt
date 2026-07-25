UBE v1.8q build 237 - SerializedFile Sibling External Resolver

This build improves the v1.8p Unity SerializedFile first pass.

When a .assets/globalgamemanagers/level/resources file is opened from a
Serialized Assets Folder, UBE now scans nearby Unity SerializedFile sources and
loads a capped set as external reference sources.

This helps older Steam/desktop Unity layouts such as:

  level0
  globalgamemanagers
  sharedassets0.assets
  resources.assets
  unity default resources
  sharedassets0.assets.resS

Why:
  A MeshFilter in level0 might point to PathID 10210, FileID 3 external.
  That mesh may actually live in another sibling SerializedFile such as
  "unity default resources".  UBE now tries to attach those sibling records so
  inspector links, preview, and export have a chance to resolve them.

Notes:
  - .resS and .resource files are still sidecar byte stores, not opened directly.
  - This is a practical first pass using UBE's existing PathID external maps.
  - True FileID-to-file table resolution is still future work.
  - PathID collisions between sibling files are detected and reported.
  - The resolver is capped to avoid opening a very large game folder all at once.
