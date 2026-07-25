# UBE v2.1 Build 285 — True Hierarchy Reconstruction

Version 2.1 begins with hierarchy reconstruction rather than another isolated inspector.

## Multi-select now understands transform-only objects

The earlier multi-select preview required a directly attached MeshFilter or SkinnedMeshRenderer. That disagreed with the normal single-object preview, which could already assemble a transform-only GameObject from visible descendants.

In v2.1, Ctrl/Shift selecting objects such as:

```text
b.axel
├─ lf.axel       (Transform-only wheel container)
└─ rb.axel       (Transform-only wheel container)
```

now follows each selection down to its real renderer/mesh children.

## Common-ancestor coordinate frame

UBE finds the nearest common Transform ancestor of the selected objects and calculates:

```text
selected relative matrix
    × descendant local matrix chain
    × renderer mesh vertices
```

The preview is framed only after all selected render instances have been positioned together. Parts are never individually re-centred.

## Repeated meshes remain separate instances

Two wheels can share one Mesh asset while using different GameObjects, Renderers and Transforms. v2.1 preserves those as separate render instances instead of treating the shared Mesh PathID as the identity of the visible object.

Debug palette colours are assigned by top-level selection, so every visible descendant of the left selection shares one colour and every descendant of the right selection shares another. `O`, `V`, `I`, `Shift+I`, `P` and `Shift+O` remain available for hierarchy diagnosis.

## Source-aware Transform resolution

UnityFS bundles can contain several internal SerializedFiles with overlapping PathIDs. Hierarchy PPtrs are now resolved first by:

```text
(SerializedFile source name, PathID)
```

before falling back to the older bundle-wide PathID lookup. This prevents a Transform, GameObject, MeshFilter or Renderer from being silently connected to a same-numbered object in another internal file.

## Combined export

Combined OBJ/GLB export now uses the same reconstructed hierarchy as multi-select preview. Transform-only selections are expanded to their visible renderer descendants and exported relative to the same nearest common ancestor.

## Primary acceptance case

The Mars Gardens rover/truck axle is the first v2.1 reference case:

- left wheel and right wheel must Shift-select successfully;
- both wheel instances must remain separate;
- the axle common parent must be reported;
- the complete truck must retain the same relative wheel placement;
- origin markers must show the reconstructed renderer-instance pivots.
