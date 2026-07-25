UBE v1.8f - AnimationClip Motion Summary
========================================

Adds a clearer learner-friendly AnimationClip summary before the raw curve list.

New inspector section:
  🧭 Motion summary

It estimates:
  - likely clip role: skeletal/armature, transform/object, property/material, or object-reference animation
  - animated target count
  - curve channel count
  - total exposed keyframes
  - motion style: sparse/tweened, moderate, or dense baked motion
  - main root targets
  - busiest animated paths/bones

Also adds a short "How to read this" explanation so AnimationClips are easier to understand as timeline/keyframe data.
