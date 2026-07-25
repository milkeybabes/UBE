# UBE v2.1a Build 286 — K-key Strict Hierarchy Test

## Purpose

Some complex Unity assemblies reuse common model-space geometry while also carrying deep Transform hierarchies. UBE v2.1a keeps the current reconstruction intact and adds a safe live comparison.

## Key

Press **K** while viewing an assembled transform-only parent/group or a Shift/Ctrl multi-selection.

- **CURRENT descendant-chain assembly** multiplies the local Transform path from the preview root down to each renderer.
- **STRICT inverse-root-world assembly** independently calculates the preview root world matrix and renderer world matrix, then uses `inverse(root world) × renderer world`.

The viewer rebuilds the same exported child geometry using the alternative matrices while preserving the current camera and group debug state.

## Scope

This is preview-only in Build 286. OBJ/GLB export continues to use the established path so experimental placement cannot alter saved assets. Once the Mars truck and other known-good objects establish the correct interpretation, export can be updated deliberately.
