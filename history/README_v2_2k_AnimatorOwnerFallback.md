# UBE v2.2k — Animator Owner Fallback

Mixed AnimationClips can contain one playable Transform channel plus renderer property bindings. Bundle-global path hashes are ambiguous when several prefabs reuse the same helper names. v2.2k follows the clip through its AnimatorController to the Animator GameObject, builds a bounded path index inside that owner hierarchy, and resolves the playable tracks there.

If no Animator owner is available, UBE falls back to the known-good v2.2h playable-track-only preview rather than disabling playback. Ctrl+A / Command+A text selection remains fixed.
