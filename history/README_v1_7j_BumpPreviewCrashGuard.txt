UBE v1.7j - Bump Preview Crash Guard
====================================

This build hardens the OpenGL lit + bump preview path.

Fixed:
- Some odd meshes/drivers could raise GL_INVALID_OPERATION inside the lit bump preview, usually when L/bump mode was active.
- The error was isolated to QOpenGLWidget paintGL, but could kill the 3D preview loop.

Changed:
- The lit bump path now catches OpenGL errors, resets shader/texture state, clears stale GL error flags, disables lit bump for that mesh, and falls back to the regular preview instead of crashing.
- Non-finite vertices/normals/UVs are skipped in the bump-preview path.

Kept:
- v1.7i zero default model rotation.
- v1.7 group assembly/debug features.
- v1.6/v1.7 shader/material/sprite/camera/collider/recents features.
