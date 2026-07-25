UBE v1.8zc build 249 - Raw Mesh Context Confidence Fix

Fixes two issues seen in ABVRIOPLogoGeo diagnostics:

1. Material-name-only semantic matches no longer trigger automatic raw Mesh
   preview/export if the material does not resolve any Texture2D slots.
   Example:
     ABVRIOPLogoGeo -> ABVRIOPLogoMat
   is useful as a lead, but if Texture2D assets is '-', UBE now keeps the raw
   Mesh preview/export conservative.

2. Shader/ref display now validates whether the resolved object is actually a
   Shader. If a material shader pointer resolves as another object type, UBE
   reports that instead of presenting it as a shader name.

Also removed duplicate Shader/ref lines in the context display.
