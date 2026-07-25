# UBE v2.3x — Overlapping Runtime Render Variants

Some imported animation owners contain several numbered complete skinned models
at exactly the same transform. Runtime code chooses one model, but the isolated
common bundle can serialize every child and renderer as active. Drawing them all
at once creates z-fighting, mixed atlas colours and a misleading composite shape.

UBE now recognises only a strict alternative-renderer pattern:

- two to thirty-two SkinnedMeshRenderer instances;
- matching numbered namespace families;
- one identical rendered-name suffix;
- matching transform matrices;
- matching vertex count, submesh topology, bounds and bind-pose structure; and
- distinct Mesh assets.

The first alternative is shown initially. Press **I** to cycle every alternative
or reach the all-visible diagnostic state. The current visible alternative is
also honoured by animated GLB export. Normal assemblies are unchanged.
