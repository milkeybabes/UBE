UBE v1.8h - LODGroup Material-Aware Preview

This build improves previews for GameObjects that own an LODGroup.

Previously, transform-only parent/group preview used debug palette colours for child meshes.
That is useful for general assemblies, but confusing for LODGroup parents because Unity normally
shows only one LOD child at a time and each LOD child has its own renderer/material context.

New behaviour:
- Selecting an LODGroup parent previews the first LOD child using its real renderer material/texture.
- Press I to cycle LOD children: LOD0 -> LOD1 -> LOD2 -> ...
- Press Shift+I to return to the first LOD child.
- Generic non-LOD group assemblies still use the palette-coloured group preview.

This is especially useful for SkinnedMeshRenderer LOD sets such as animated creatures,
where clicking the individual LOD child looked correct but the parent preview used debug colours.
