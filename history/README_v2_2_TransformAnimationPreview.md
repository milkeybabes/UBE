# UBE v2.2 Build 289 — Basic Transform AnimationClip Preview

v2.2 begins animation reconstruction with the smallest useful step: ordinary
Transform curves can now be applied to the static GameObject hierarchy completed
in v2.1.

## First-pass playback

Select an `AnimationClip`. When UBE can resolve its hierarchy paths and the clip
exposes ordinary curves, the top panel reconstructs the animation root and adds:

- Play / pause
- Timeline scrubbing
- Loop toggle
- 0.25x to 2x playback speed
- Reset to the original static/default pose
- Matched path, curve and render-instance summary

Supported in this first pass:

- Local position curves
- Local quaternion rotation curves
- Local Euler rotation curves
- Local scale curves
- Transform-only hierarchy nodes and repeated mesh instances

The viewer caches each child mesh once and updates its matrix in memory. It does
not re-export OBJ geometry for every animation frame.

## Educational behaviour

Animation paths are resolved against the loaded GameObject/Transform hierarchy.
The clip panel reports how many curves and target paths matched. Reset pose returns
to the exact serialized Transform pose, making the difference between the authored
static hierarchy and the clip pose easy to compare.

## Deliberate limits of this first step

Not yet played:

- Dense/streamed/constant curve storage
- Humanoid muscle/retargeted clips
- Skinned-mesh bone deformation
- Blend shapes
- Visibility, material, sprite, light or script-property curves
- Animator Controller states, transitions and blend trees
- Root motion, IK, physics or script-driven motion

Those clips remain fully inspectable through the established AnimationClip and
Relationship Flow inspectors. UBE states why playback is unavailable rather than
guessing at unsupported data.

## Test case

The Mars bundle `Scene` clip with three satellite quaternion curves resolves to
one hierarchy, loads nine render instances, plays through a 139.933-second
timeline, scrubs correctly, and returns byte-for-byte to the original preview
vertex positions on Reset pose.
