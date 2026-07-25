# UBE v2.2h Build 297 — Hashed Constraint Types and Live-Instance Selection

Unity 6 can serialize built-in constraints under a hashed type ID rather than the familiar public class name. The Meow Wolf Easy scene stores its three `RotationConstraint` components under class ID `1818360609`, while the embedded type-tree root still identifies them as `RotationConstraint`.

UBE now:

- recognises built-in constraints from the embedded type-tree name and strict field signatures;
- performs reverse constraint discovery across hashed/unknown type groups without decoding every object;
- prefers duplicate animation hierarchy instances that are actually referenced by scene constraints, rather than an inert `*.sharedAssets` template copy;
- reports `constraint-linked targets` and the applied constraint count in the animation status line.

Acceptance case: `h16_windmills` in `meowwolfcommon_scenes_meowwolf_easy.bundle` should decode 9 streamed Euler channels, select the live scene helper hierarchy, discover 3 RotationConstraints, and rotate the three visible windmills.
