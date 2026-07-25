# UBE v2.4f Build 346 — Null Renderer Material Family Recovery

## New Unity case

Tokyo's `Scene` / Onsen Chimes animation uses eight visible rigid meshes whose MeshRenderer material arrays contain one explicit null pointer:

```text
m_Materials[0] = PPtr(m_FileID=0, m_PathID=0)
```

This is not an unresolved external Material and not a saved Material shell. Earlier recovery stages therefore had no Material record from which to infer a texture.

The same bundle retains the authored source family:

```text
Onsen_Wind_Chimes_showMPS.*
        ↓ exact normalized family
Onsen_Wind_Chimes_woodPS
        ↓ real renderer material
Tokyo_Easy_Color
        ↓ _BaseMap
Tokyo_Texture
```

The moving meshes and the static donor use the same repeated UV0 palette/swatch convention. UBE can therefore restore the missing appearance without changing geometry or animation.

## Safety gates

Recovery runs only when all of these are true:

- the selected Mesh is used by a MeshRenderer or SkinnedMeshRenderer;
- every saved slot on that exact renderer is a literal null PPtr;
- UV0 contains convincing repeated palette/swatch lookup points;
- target and donor names reduce to the same authored mesh-family key after known runtime/static suffixes are removed;
- the donor is genuinely used by a renderer with a saved base texture;
- close competing donors all resolve to the same base texture.

A non-zero unresolved external reference, a genuine Material, constant/ordinary UV data, or an ambiguous donor keeps the existing conservative result.

## Scope

The recovered material is shared by Mesh, Object and AnimationClip preview and by OBJ/GLB export. Export metadata records the null renderer, donor mesh, donor Material, base texture and UV evidence.
