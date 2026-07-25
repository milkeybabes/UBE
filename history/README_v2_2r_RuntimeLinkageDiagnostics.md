# UBE v2.2r — Runtime Linkage Diagnostics

Build 307 adds bounded diagnostics for AnimationClips whose motion data is intact but whose visible geometry is not directly serialized beneath the animated Transform.

This targets cases such as the orange and purple Meow Wolf flag variants:

- The position/Euler curves resolve normally.
- The named owner and animated child Transform are found.
- A descendant MeshFilter or SkinnedMeshRenderer has a null mesh reference, or a MeshRenderer has no usable MeshFilter.
- Visible geometry may exist in a separate Perfect Culling/runtime/proxy branch that is not a child of the animated Transform.

UBE now reports this as **motion decoded; visible runtime linkage incomplete** rather than attaching unrelated geometry by guesswork. The inspector lists the named owner, animated paths, null visual references, and any separate runtime/culling branches with visible geometry.

The diagnostic is read-only and bounded. It does not change animation playback, object ownership, or reconstruction logic. Existing working animations remain unchanged.
