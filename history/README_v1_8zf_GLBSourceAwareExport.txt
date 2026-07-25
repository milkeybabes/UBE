UBE v1.8zf build 252 - Source-Aware GLB Export Fix

Fixes GLB export after v1.8zd/v1.8ze source-aware PPtr work.

Problem:
  The Mesh inspector could correctly identify:
    sharedassets0.assets / ABVRIOPLogoMat / PathID 2
    sharedassets0.assets / ABVRIOPLogo_fillpixelsGeo / PathID 8

  But GLB export still gathered material/texture records using some plain PathID
  lookups. In a UnityFS file with internal SerializedFiles, PathID 2 can exist
  in level0, resources.assets and sharedassets0.assets, so the GLB material bundle
  could resolve the wrong object.

Fix:
  - Object-material export relationships now carry source_name on both ends.
  - GLB/OBJ material bundle gathering resolves relationship targets by:
      source_name + PathID
  - Texture dedup/cache is also source-aware.
  - GLB metadata now records material/texture source_name.

Verified on the provided data.unity3d:
  Mesh: ABVRIOPLogoGeo / sharedassets0.assets / PathID 17
  Material: ABVRIOPLogoMat / sharedassets0.assets / PathID 2
  Texture: ABVRIOPLogo_fillpixelsGeo / sharedassets0.assets / PathID 8
  GLB export result:
    Images embedded: 1
    Texture export failures: 0
