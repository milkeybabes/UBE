# UBE v2.2c Build 292 — Bounded Constraint Discovery

v2.2c fixes the animation-selection freeze introduced by v2.2b.

## Cause

v2.2b searched and decoded every MonoBehaviour in the opened bundle and all loaded sibling records whenever an AnimationClip was selected. Large courses can contain hundreds or thousands of script records, so the synchronous scan blocked the Qt GUI and looked like an endless loop.

## Fix

Constraint discovery is now limited to the selected animation hierarchy:

- starts at the resolved AnimationClip root Transform
- follows only its child Transform subtree
- examines only components attached to those GameObjects
- uses visited-Transform cycle protection
- caps hierarchy depth and total scanned nodes
- never scans unrelated MonoBehaviours elsewhere in the course

Built-in RotationConstraint, PositionConstraint, ScaleConstraint and ParentConstraint support remains, along with the WAM-style Transform-driver component used by helper-driven animations.

Affected descendant Transform keys are also cached when the preview opens, instead of recalculating ancestry for every constraint on every frame.

The In-place/root-motion option from v2.2b is unchanged.
