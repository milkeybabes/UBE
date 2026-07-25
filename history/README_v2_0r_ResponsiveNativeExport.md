# UBE v2.0r — Responsive Native Export

Build 280

Native exports now stay visibly responsive while UBE assembles and writes large models.

- Shows a modal **Exporting — please wait…** notice before expensive work begins.
- Displays simple stages such as descendant scanning, material/texture resolution, mesh decoding, assembly writing, and ground-axis conversion.
- Runs expensive PNG/audio/OBJ/GLB writing off the Qt GUI thread.
- Keeps Qt/Windows repainting while work continues, avoiding the misleading **Not Responding** title.
- Render-only parent exports resolve child records incrementally before writing the combined assembly.
- The same responsive path is used for single meshes, objects, parent groups, textures, sprites, audio, texture arrays, and combined multi-selection exports.
- Unexpected exporter exceptions are reported per asset instead of leaving the wait dialog visible.

There is deliberately no percentage bar because the Unity decoding and texture/material workload cannot always be predicted accurately before export.
