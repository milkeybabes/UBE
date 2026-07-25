# UBE v2.2a Build 290 — Basic Skinned-Bone Animation Preview

v2.2a extends the proven Transform AnimationClip timeline into the first useful
character-animation stage.

## What now plays

When a resolved animation hierarchy contains a compatible `SkinnedMeshRenderer`,
UBE reads:

- The renderer's ordered bone Transform list
- The Mesh bind-pose matrices
- Per-vertex bone indices and weights
- Ordinary local position, quaternion/Euler rotation and scale curves

At each timeline position UBE evaluates the animated bone hierarchy and performs
linear-blend skinning on the cached preview vertices. Rigid child objects in the
same hierarchy continue using the established v2.2 matrix path.

## Controls

- Play / Pause
- Timeline scrubber
- Loop
- 0.25x to 2x playback speed
- Reset pose

The status line reports how many skinned renderers are actively deforming and how
many were detected but had unavailable/incompatible weight data.

## Compatibility paths

Bone weights are accepted from:

- Older explicit `m_Skin` / `m_BoneWeights` arrays
- Modern Mesh vertex channels `BlendWeight` and `BlendIndices`

NumPy is used for vectorised CPU deformation when available. The existing
requirements already include NumPy.

## Deliberate first-pass limits

Not yet reproduced:

- Blend-shape curves
- Humanoid muscle retargeting
- Dense/streamed/constant clip storage not exposed as ordinary curves
- Root motion, IK or physics
- Animator Controller states, transitions and blend trees
- Animated material/script properties
- Recalculated animated normals and tangents

A renderer that cannot expose compatible weights remains visible in its static
pose, and UBE reports that fact instead of hiding it or guessing.

## Test direction

The Meow Wolf bundle is the main v2.2a test source. Start with a simple
single-renderer character such as ToadPiggy, then move to larger rigs and
multi-renderer characters after the basic deformation path is confirmed.
