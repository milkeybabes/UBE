# UBE v1.8l - Multi-Select Fit Preview

Adds a small multi-selection 3D preview for checking whether separate Unity objects/meshes share the same authored origin and line up together.

## Usage

1. Select a renderable object/mesh in the tree.
2. Ctrl-click or Shift-click a second renderable object/mesh.
3. The 3D preview combines the selected parts without re-centering each part separately.

This is useful for cases such as:

```text
Tricera.001_LOD0
Tricera.saddle.001_LOD0
```

where the dinosaur body and saddle are separate GameObjects but probably authored to fit together.

## Notes

- Supports GameObject, Transform, MeshFilter, MeshRenderer, SkinnedMeshRenderer, and Mesh records.
- The preview is capped to the first four selected renderable records to avoid accidental huge scene loads.
- Each selected object can keep its own base texture where the exporter exposes one.
- If a selected object has no texture, UBE falls back to its material colour or a readable preview colour.
- Press `I` to solo selected parts one at a time.
- Press `Shift+I` to show all selected parts again.
- Press `V` to hide selected parts one at a time.

This is a visual fit/origin check, not a final Unity scene renderer/exporter.
