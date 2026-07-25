# UBE v2.2s Build 308 — Animated GLB Export

AnimationClip previews now expose **Export Animated GLB…** only when UBE can
represent the complete visible result safely as ordinary glTF node animation.

The first export stage supports rigid reconstructed hierarchies driven by:

- local position
- quaternion rotation
- Euler rotation
- local scale
- ordinary or decoded StreamedClip Transform curves

UBE bakes each visible render instance at the clip's authored sample rate (capped
at 60 fps), embeds the existing GLB materials and textures, and writes glTF
translation/rotation/scale channels. The current **In place** setting is honoured.

The button is deliberately hidden when the clip contains any condition that
would make the GLB incomplete or misleading, including:

- skinned/bone deformation (planned later)
- unresolved animation paths
- constraint-driven motion
- unsupported property, blend-shape or material bindings
- runtime/culling linkage warnings
- duplicate renderer instances that cannot yet be represented independently
- an impractically large baked sample count

This conservative availability rule means that every displayed Animated GLB
option is expected to reproduce the rigid animation UBE is currently showing.
MP4/video rendering remains a later second export stage.
