UBE v1.6a - AnimatorController Inspector
========================================

This build adds a first-pass, educational AnimatorController inspector.

It is not animation playback yet. The goal is to make the asset understandable when a user clicks it:

- AnimatorController is the state machine / logic board.
- AnimationClip is the timeline/keyframe data.
- The controller wires clips into states, layers, parameters and transitions.

New inspector sections try to show:

- String/hash table (TOS) when available
- Parameters if exposed
- Layers
- State machines and state counts
- Basic state summaries
- Referenced AnimationClips / motions
- Exposed fields
- A plain-language explanation of what the controller does

Kept from previous checked builds:

- AnimationClip inspector
- Sprite and SpriteRenderer inspectors/preview/export
- Sprite external resolver
- GLB golf-ball texture/normal fixes
- OpenGL normal/bump preview
- filtered export
- UV infinity crash fix

Version: 1.6a
Build: 184
