UBE v1.8z build 246 - Semantic Material Context for Raw Meshes

Refines the v1.8y raw Mesh renderer-context feature.

Problem found:
  ABVRIOPLogoGeo matched GameObject/Renderer contexts by object name, but those
  renderers still used generic Default-Particle material.  Object-name match alone
  is not enough for automatic preview/export confidence.

Fix:
  - Generic/default renderer materials no longer create auto-confidence by name alone.
  - Raw Mesh context scoring now requires a real material/texture signal.
  - UBE also scans Material and Texture names directly for semantic matches.
  - A case like:
        ABVRIOPLogoGeo -> ABVRIOPLogoMat -> ABVRIOPLogo_fillpixelsGeo
    can now win over:
        ABVRIOPLogoGeo -> Default-Particle

Inspector:
  The raw Mesh inspector now labels:
    - renderer contexts with material signal vs object-name only
    - material/texture name matches
    - whether auto preview/export will use the semantic material context

Preview/export:
  OBJ/GLB raw Mesh export can force the matched material/texture context without
  pretending it came from a renderer.
