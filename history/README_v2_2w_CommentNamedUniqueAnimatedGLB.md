# UBE v2.2w Build 312 — Comment-Named, Non-Overwriting Animated GLB

Animated GLB export filenames now prefer the selected AnimationClip's external
comment. This is especially useful for bundles containing many clips named
`Scene`; a comment such as `March Hare sitting down` produces:

`March Hare sitting down__animated.glb`

Only the first non-empty comment line is used. When no comment exists, UBE falls
back to the serialized AnimationClip name.

Exports never silently replace an existing GLB. Repeated exports receive a
numeric suffix shared by the GLB, log and metadata files:

- `March Hare sitting down__animated.glb`
- `March Hare sitting down__animated_1.glb`
- `March Hare sitting down__animated_2.glb`

The completion dialog reports whether the filename came from the external
comment or the clip name. All v2.2v mixed rigid/skinned animation, validated skin
weights, strict timing and V/I preview visibility behaviour remain unchanged.
