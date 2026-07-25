# UBE v2.4b Build 342 — Branch-Scoped Animation Root Promotion

Amusement Park's `H01e_Gates` clip exposed an unsafe preview fallback. The
AnimationClip correctly resolves two Euler-rotation targets beneath
`H01_Gate`, but that owner branch contains no MeshRenderer or
SkinnedMeshRenderer in the common bundle. The previous nearest-renderable-owner
fallback climbed one level to the course-wide `AmusementPark_Animation_Geo`
container and displayed every renderable sibling branch beneath it.

That produced a misleading, extremely zoomed-out preview containing geometry
from `Critters`, `H06_Teeth` and `Hole17_Birds`. None of those objects is a gate
or a target of the selected clip.

UBE now scopes render-owner promotion to coherent sibling branches:

- a renderer directly on the promoted owner remains authoritative;
- skeleton/JNT and MESH branches are paired by stable family-name evidence;
- generic imported branches can pair when they share the same authored local
  anchor;
- a small classic skeleton-plus-one-visible-sibling owner remains supported;
- promotion stops at an ancestor containing multiple unrelated renderable
  branches instead of attaching all of them to the clip.

When a clip resolves only animation-driver transforms and no coherent visual
owner exists in the loaded data, UBE now keeps the correct clickable animation
owner and reports that the visible object is likely supplied by a scene bundle,
constraint or runtime script. It no longer substitutes neighbouring animation
geometry.

For the supplied bundle, the exact hierarchy is:

```
AmusementPark_Animation_Geo
├─ Critters                 (19 renderers)
├─ H01_Gate                 (0 renderers; selected clip owner)
├─ H05_BumperCars           (0 renderers)
├─ H06_Teeth                (5 renderers)
└─ Hole17_Birds             (12 renderers)
```

The two `H01e_Gates` targets remain correctly resolved to
`GateL_anim` and `GateR_anim`; only the unsafe render overreach is removed.
