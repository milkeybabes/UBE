# UBE v2.1c Build 288 — Permanent Hierarchy Basis

## Final reconstruction rule

Testing across the Mars rover, the 20,000 Leagues ship and several other large assembled objects confirmed that the old placement path mixed two coordinate systems:

- Unity hierarchy matrices were in Unity coordinates.
- UnityPy OBJ positions/normals were exported as `(-X, Y, Z)`.

UBE now always uses the matching similarity transform for UnityPy OBJ geometry:

```text
M_obj = C × M_unity × C
C = diag(-1, 1, 1, 1)
```

## What changed

- Corrected hierarchy placement is now the normal and only preview path.
- The experimental K toggle and incorrect legacy basis were removed.
- K is available for a future feature.
- Assembled OBJ export converts each Unity matrix when the child geometry came from UnityPy OBJ output.
- Native GLB geometry keeps its Unity matrix because its decoded positions are normally still in Unity coordinates.
- When GLB must fall back through UnityPy OBJ parsing, UBE automatically applies the mirrored-X matrix conversion.
- Transform-only hierarchy nodes, repeated mesh instances and nearest-common-ancestor multi-selection from v2.1 remain active.

## Confirmed cases

- Mars rover wheel and axle assemblies align correctly.
- The previously broken 20,000 Leagues ship sections reconstruct correctly.
- Several large objects that were already close or apparently correct remain correct.

This confirms the issue was a general coordinate-basis mismatch rather than game-specific control objects or missing runtime information.
