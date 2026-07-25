# UBE v2.2b Build 291 — Root Motion and Constraint Preview

v2.2b closes the two repeatable edge cases discovered while testing the Meow Wolf AnimationClips.

## In-place animation preview

A new **In place** checkbox appears for clips whose topmost animated target contains position or scale curves. UBE automatically enables it when those curves move far from the serialized preview pose or contain a suspicious scale range.

With **In place** enabled, UBE keeps the topmost animated position and scale at the serialized pose while continuing to apply:

- bone animation
- child Transform animation
- root rotation
- CPU skinning

Clear the checkbox to inspect the clip exactly as authored, including scene/root movement. This is intended for isolated character clips that otherwise fly away from the inspection camera.

## Constraint and transform-driver propagation

UBE now evaluates a first useful subset of serialized transform links after ordinary AnimationClip curves:

- RotationConstraint
- PositionConstraint
- ScaleConstraint
- ParentConstraint
- WAM-style Transform-driver MonoBehaviours exposing `target` plus position/rotation/scale channel flags

The custom Transform-driver pattern is used by the Meow Wolf windmill animation and is searched in both the opened bundle and resolved external/sibling records: the clip rotates invisible `Constraint` helper Transforms, and a serialized component copies the selected channels to the visible windmill assembly.

The evaluator preserves the target's serialized offset by applying the source's change from its default pose, rather than snapping the target directly onto the source. Descendant renderers move with the constrained target.

## Status information

The animation status line now reports:

- CPU-skinned renderers
- supported constraint/driver links
- limited multi-source cases
- the in-place target selected from the animation hierarchy

## Deliberate limits

This remains an inspection-oriented first pass, not a complete Unity runtime solver. Multi-source constraint blending, AimConstraint, IK, physics, Animator state machines and script code outside the recognized serialized Transform-driver pattern remain later stages.
