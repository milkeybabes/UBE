# UBE v2.1b Build 287 — K-key UnityPy OBJ Basis Test

## Why Build 286 looked identical

The descendant-chain matrix and `inverse(root world) × renderer world` matrix are mathematically equivalent when both are calculated correctly. The Mars truck therefore looked unchanged in both modes.

Inspection of the real bundle exposed a different coordinate-space issue. UnityPy exports OBJ vertices as:

```text
(-x, y, z)
```

UBE was then applying the original Unity-space Transform matrix directly to those already-mirrored vertices. The matching OBJ-space matrix is:

```text
M_obj = C × M_unity × C
C = diag(-1, 1, 1, 1)
```

## K key

On assembled parent/group and multi-select previews:

- **K off — ESTABLISHED**: preserves the existing v2.1a placement.
- **K on — CORRECTED**: converts Unity matrices into UnityPy's mirrored-X OBJ coordinate basis before transforming each child mesh.

The camera, materials/debug colours, hidden/isolated child and origin markers are preserved while toggling.

## Scope

This test is preview-only. OBJ/GLB exports remain unchanged until the Mars truck and a selection of already-correct objects confirm the safest permanent rule.
