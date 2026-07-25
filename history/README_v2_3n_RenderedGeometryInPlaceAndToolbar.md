# UBE v2.3n — Rendered-Geometry In-Place Anchor and Toolbar Restore

- In-place preview now has a final rendered-geometry anchor.
- The largest visible render part is measured after hierarchy evaluation and CPU skinning.
- Every later frame is translated back to its frame-zero displayed centre.
- This catches duplicate rigs, hidden controller parents and motion distributed across several Transform branches.
- The scrubber time/frame readout is visible again in a fixed-width label.
- The readout uses a concise stable format and keeps verbose range details in its tooltip.
- Speed selector reduced to 52 logical pixels.
- Play, Reset pose and Export GLB buttons tightened further.
