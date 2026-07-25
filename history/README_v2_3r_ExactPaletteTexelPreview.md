# UBE v2.3r — Exact palette texel preview

Build 331 corrects washed or nearly single-colour previews for block-colour
animated scenes that use a large swatch texture as a colour lookup table.

The ShipCrane animation shares one stripped runtime material across nine rigid
renderers. Its intended red, yellow, blue, white and dark parts are encoded by
repeated UV0 lookup points, not by separate material colours.

Changes:

- palette/swatch textures use nearest-neighbour sampling rather than linear filtering;
- assembled group/animation previews sample the exported palette PNG per face and draw exact flat colours;
- normal textured materials remain on the existing linear-filtered path;
- palette GLB exports request NEAREST + CLAMP_TO_EDGE samplers;
- audio property curves such as pitch/volume remain inspector-only and do not affect visual material resolution.
