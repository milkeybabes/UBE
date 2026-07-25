# UBE v2.3g Build 320 — In-Place Duration Limit

Long environmental clips often repeat a short local motion while a top-level
Transform carries the object around the Unity world for several minutes. The
full authored timeline is useful in-game but wasteful for preview loops and
portable asset export.

This build adds a precise **Limit** control beside animation Speed:

- the control becomes active when **In place** is enabled;
- the value defines the end of the preview loop and the animation scrub range;
- Animated GLB eligibility and size checks use the limited duration;
- export bakes only the selected first N seconds while preserving the original
  source sample rate;
- the successful export and filename record the limited duration;
- **Full** restores the complete AnimationClip duration; and
- disabling In place immediately restores normal authored full-length playback.

For example, a 270-second whale clip at 60 fps can be reduced to a five-second
in-place swimming cycle: approximately 301 GLB samples instead of more than
16,000 source frames. The original AnimationClip data is never modified.
