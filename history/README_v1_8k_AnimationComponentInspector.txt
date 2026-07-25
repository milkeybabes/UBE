UBE v1.8k - Animation Component Inspector
========================================

Build 231

Adds a specialised inspector for Unity's legacy Animation component.

What it shows:
- Owner GameObject reference and resolution diagnostics.
- Enabled / Play Automatically / Animate Physics settings.
- Wrap mode and culling type, with friendly enum names where known.
- User bounds where exposed by UnityPy.
- Default AnimationClip and clip list.
- Clip summaries for resolved clips: approximate duration, sample rate, legacy flag and clip wrap mode.
- Role summary explaining single-clip vs multi-clip legacy animation setup.

Why this matters:
The AnimationClip contains the keyframes, but the Animation component is the bridge on the GameObject that decides which clip is attached, which one starts automatically, and what playback behaviour Unity should use.

This complements the existing AnimationClip and AnimatorController inspectors.
