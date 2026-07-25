# UBE v2.3t Build 333 — External Character Material Recovery

## Problem

Labyrinth character animations such as `KillingFairies` and `Sleepy` play
correctly, but their SkinnedMeshRenderers reference Material PathID
`6824069125264728142` in external FileID 2. Opening only the common bundle leaves
that runtime material unresolved, so otherwise valid colourful characters fall
back to flat shading.

The same common bundle contains the complete local material
`Labyrinth_Characters`, with `Labyrinth_CombinedAssets_Texture 1` as `_BaseMap`
and the matching metalness map.

## Fix

When a Mesh has an unresolved external Material relationship and is demonstrably
used by a SkinnedMeshRenderer, UBE ranks complete local character/creature
materials using course/source context. Recovery occurs only when one candidate
wins by a wide margin. Generic course, Easy/Hard, water, glass, flame, particle,
terrain and rigid-prop materials are not guessed.

This affects mesh/object previews, AnimationClip previews, OBJ/MTL export and GLB
export because they share the same material-gathering path.
