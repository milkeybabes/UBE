UBE v1.7m - Light Probe / Lightmap Inspectors

Adds lightweight inspectors for the remaining common Unity lighting records:

- LightProbeGroup
  - GameObject link, enabled state, probe count
  - probe bounds and sample positions
  - dering and other exposed fields
  - explanation of how probes help dynamic objects receive baked indirect light

- LightingSettings
  - GI workflow/modes where exposed
  - baked/realtime lightmap toggles
  - lightmapper / mixed bake mode
  - bake resolution, atlas size, AO, lighting data asset references
  - explanation of baked-lighting provenance in shipped VR/mobile content

- LightmapSettings
  - lightmap entry count and mode
  - baked colour space
  - light probe / lighting data asset references
  - colour/directional/shadow-mask texture references for first entries
  - explanation of how renderer lightmap index/scale-offset points into scene lightmaps

This completes the current lighting component family alongside the v1.7l Light inspector.
