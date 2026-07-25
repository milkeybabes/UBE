# UBE v2.0f — Animation Wiring Inspector

This build turns modern Unity animation bindings into readable investigative data.

## AnimationClip binding resolver

Unity stores target hierarchy paths as 32-bit hashes. UBE now builds a Transform/GameObject hierarchy index from the opened bundle and its automatically loaded course siblings, then resolves those hashes back into readable paths.

For each AnimationClip the inspector now shows:

- Reliable start/stop duration from `m_MuscleClip`
- Loop-time status
- Dense, streamed and constant clip storage counts
- Binding target type and readable property names
- Resolved hierarchy paths
- Source bundle and internal SerializedFile
- Duplicate hierarchy-instance count without duplicating the whole report
- Unresolved hashes when the required scene/prefab hierarchy is not loaded
- Motion classification: skeletal rig, Transform hierarchy, Transform + visibility, object activation, or property animation

Examples from Cherry Blossom:

- `Heron` resolves 48 bone-style paths and is classified as skeletal/rig animation.
- `CherryBlossom_WaterFeatureTipping2` resolves five targets and is classified as Transform + GameObject visibility animation.
- `Take 001` resolves to one scale-only Transform path.

## Animator component inspector

Animator now has a dedicated inspector showing:

- Owner GameObject
- External/local AnimatorController
- Avatar
- Culling/update/root-motion settings
- Resolved controller AnimationClips
- Clip duration and sample rate
- A learner-friendly motion-source summary

## Motion-source investigation

GameObject, Material, MeshRenderer and SkinnedMeshRenderer inspectors now explain where visible movement is likely coming from:

- Modern Animator/Mecanim
- Legacy Animation component
- Bone/skinned deformation
- ParticleSystem simulation
- Shader/material wind, deformation, ripple, flow, noise or time-driven movement
- Possible parent animation or runtime MonoBehaviour movement when no direct source is present

This is deliberately an investigation layer rather than an incomplete animation player. It explains the wiring first, using the actual Cherry Blossom scene/common bundle relationship as a validated test case.
