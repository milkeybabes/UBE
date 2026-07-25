# UBE v2.2g Build 296 — Reverse Constraint Discovery

The Hole 16 windmill clips animate three helper `Constraint` Transforms stored under `Windmill_MotionBase`. The visible windmill meshes are in a separate scene hierarchy and each carries a `RotationConstraint` whose source points back to one of those helpers.

v2.2f decoded the streamed Euler curves correctly, but the bounded v2.2c constraint scan only searched descendants of the animated helper hierarchy. It therefore could not see the three visible constraints.

v2.2g performs a second, tightly bounded reverse lookup over built-in constraint records only. It accepts a constraint only when one of its source Transforms is animated by the selected clip. This resolves the scene-crossing rig without decoding every MonoBehaviour or blocking the GUI.
