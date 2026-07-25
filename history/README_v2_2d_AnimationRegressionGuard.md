# UBE v2.2d — Animation Regression Guard

Build 293 restores known-good rigid animation behaviour while retaining the optional fringe-case tools.

## Changes

- **In place is manual.** It is never selected automatically, because valid clips such as RingLoc legitimately animate position and scale.
- When enabled, In place locks the top animated position/scale Transform in each independent hierarchy branch.
- Constraint and Transform-driver propagation is used only when the selected AnimationClip directly animates that driver source.
- The bounded hierarchy scan from v2.2c remains in place, avoiding the v2.2b GUI freeze.

## Expected checks

1. RingLoc and other previously working rigid clips should match v2.2a with In place off.
2. Character clips that fly away can be inspected by manually checking In place.
3. Windmill/helper clips still propagate where their animated helper is the actual constraint source.
