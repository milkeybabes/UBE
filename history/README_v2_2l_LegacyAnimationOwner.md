# UBE v2.2l — Legacy Animation owner resolution

Build 301 resolves Legacy AnimationClips through the `Animation` component that explicitly owns the clip.

- Prevents repeated target names such as `flagRaiser` from selecting every prefab/colour variant in a bundle.
- Uses `AnimationClip -> Animation component -> owning GameObject` as the authoritative preview hierarchy.
- Resolves playable Transform paths inside that owner's local hierarchy.
- Keeps AnimatorController ownership for Mecanim clips and the v2.2h fallback for unresolved mixed clips.
- `flagStopper_pink_FlagRaise_WAM_Legacy` is the acceptance case.
