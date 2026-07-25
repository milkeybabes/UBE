UBE v1.8zb build 248 - Context Shader Details

Adds shader/material-property details to raw Mesh renderer/material context rows.

The raw Mesh inspector now shows, where available:
  - Material asset name
  - Texture2D asset name and PathID
  - Shader name / shader PathID
  - Key colour properties such as _Color, _TintColor, _EmissionColor, _RimColor
  - Key float properties such as _SrcBlend, _DstBlend, _ZWrite, _Cutoff, _Glossiness

This is useful for cases such as ABVRIOPLogoGeo where the mesh/UV is correct but
Default-Particle may be acting as a ramp/mask/highlight texture while shader
colours create the final logo colour.
