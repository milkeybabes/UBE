UBE v1.8zd build 250 - Source-aware PPtr Resolution

Fixes a deep UnityFS/SerializedFile resolution issue.

UnityFS bundles can contain multiple internal SerializedFiles, such as:
  level0
  resources.assets
  sharedassets0.assets

PathIDs are only unique inside each internal file.  This means PathID 2 in
sharedassets0.assets can be ABVRIOPLogoMat while PathID 2 in resources.assets
can be Default-Particle.

Before:
  UBE mostly resolved PPtrs by PathID only, so external references from level0
  could accidentally land on the wrong object in resources.assets.  This is why
  ABVRIOPLogoMat could appear to point at ChuckUnlitMat / Default-Particle.

Now:
  - AssetRecord stores internal source_name.
  - BundleIndex stores (source_name, PathID) -> AssetRecord.
  - PPtr resolution uses UnityPy PPtr.deref() to find the real target
    SerializedFile + PathID before falling back to legacy PathID lookup.
  - Mesh/material/texture context diagnostics use the exact target when possible.

Expected for the Angry Birds logo case:
  level0 MeshRenderer material PPtr FileID 2 / PathID 2 resolves to:
    sharedassets0.assets / ABVRIOPLogoMat
  ABVRIOPLogoMat _MainTex PathID 8 resolves to:
    sharedassets0.assets / ABVRIOPLogo_fillpixelsGeo
  ABVRIOPLogoMat shader PathID 18 resolves to:
    sharedassets0.assets / Shader PathID 18
