# UBE v2.2f Build 295 — Streamed Animation Curves

## What changed

UBE can now preview generic Transform animation stored in Unity's nested `StreamedClip` data, rather than only ordinary `m_PositionCurves`, `m_RotationCurves`, `m_EulerCurves`, and `m_ScaleCurves` arrays.

The decoder reads the streamed frame records, maps scalar curve indices through `m_ClipBindingConstant.genericBindings`, rebuilds Vector3/quaternion tracks, resolves the path hashes to loaded Transform hierarchies, and feeds the resulting tracks into the existing v2.2 animation timeline.

## Meow Wolf Hole 16 acceptance case

`h16_windmillsHARD` contains:

- 143 streamed data words
- 9 streamed scalar curves
- 3 generic Transform bindings
- Local Euler rotation on three `Constraint` targets
- A 24-second looping timeline

Those nine scalar channels are reconstructed as three Euler Vector3 tracks. Existing constraint/driver propagation can then pass the animated helper rotations to the visible windmill assemblies.

## Scope

v2.2f supports streamed generic Transform bindings for:

- Local position
- Local quaternion rotation
- Local scale
- Local Euler rotation

Other streamed binding types, dense/constant storage, humanoid muscle curves, blend shapes, materials, scripts, and visibility/property animation remain outside this stage.

## Safety

Malformed or truncated streamed data is rejected with a bounded error message. Frame and key-count guards prevent corrupt clips from blocking the interface.
