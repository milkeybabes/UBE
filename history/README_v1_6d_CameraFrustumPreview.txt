UBE v1.6d build 187 - Camera Frustum Preview
============================================

Added a real preview-panel camera frustum visual for Camera assets.

What changed:
- Camera selection now draws a CAD-style frustum diagram in the top preview panel.
- Perspective cameras show a lens point, near plane, far plane, sensor/focal-length hint, and lens-feel comparison.
- Orthographic cameras show a parallel viewing box.
- The old text-only ASCII cone in the inspector has been replaced with a cleaner note that the visual is in the preview panel.
- Camera inspector still reports focal length, sensor size, approximate FOV and lens feel.

This keeps the inspector educational without turning it into a wall of text.
