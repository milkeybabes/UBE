UBE v1.5w build 180 - UV infinity atlas crash fix

Fixes inspector crash:
  OverflowError: cannot convert float infinity to integer

Cause:
  Some streamed/packed Unity meshes can expose/guess a malformed UV channel with NaN/Inf bounds.
  The atlas insight tried to convert those bounds into pixel coordinates.

Changes:
  - UV extraction now filters NaN/Inf coordinates.
  - uv_bounds() ignores non-finite UVs.
  - atlas_region_from_uv_bounds() safely returns None for non-finite bounds.
  - _atlas_region_text() has an extra guard so a bad UV region never crashes the inspector.

Kept from previous builds:
  - v1.5v filtered export options.
  - v1.5u OpenGL normal/bump preview hotkeys.
  - v1.5t/v1.5r GLB golf-ball texture/normal fixes.
