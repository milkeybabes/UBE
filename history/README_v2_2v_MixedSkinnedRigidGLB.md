# UBE v2.2v Build 311 — Mixed Skinned + Rigid Animated GLB

This build expands the validated v2.2u skinned GLB path to animation scenes that
combine a skinned character with ordinary rigid props.

## Why valid clips were hidden

v2.2u bypassed rigid hierarchy-shear checks only when every visible renderer was
skinned. A clip such as the March Hare scene contains a complete skinned rig plus
rigid targets such as a chair and tea set. The presence of those props caused the
entire clip—including hundreds of valid bone scale tracks—to be checked as if it
were rigid wrapper animation, hiding the export option.

## Mixed-scene export

- Skinned renderer records and every Transform in their exported local rig
  hierarchy are evaluated through glTF skin/node TRS rules.
- Rigid props continue to use baked visual wrapper animation.
- Non-uniform scale is rejected only when it belongs to a rigid target where
  global-matrix baking could create unrepresentable shear.
- Non-uniform bone/helper scale remains allowed for a validated skin.
- Existing V/I preview visibility remains authoritative for the exported parts.

## Clear eligibility reporting

The Animated GLB button remains hidden for unsupported clips, but the animation
status line now reports the first concrete reason, for example:

`Animated GLB unavailable: constraint-driven motion is not exported`

This distinguishes an exporter limitation from missing or undecodable animation
data.
