UBE v1.7h - Shift+O Origin Marker Fix
=====================================

Build 201

Fixes the group preview zero-origin debug mode so the origin overlay matches the
mode being tested.

Previously:
- Shift+O could zero the child-origin offsets for geometry, but the O origin
  marker overlay still drew the true Unity child transform positions.
- This made the mode look as if it had not worked.

Now:
- Shift+O = ZEROED mode collapses child origin markers to the selected group
  origin in the preview, matching the zero-origin geometry test.
- O still toggles the origin/pivot marker overlay.

Keys:
- O        Toggle child origin / pivot markers
- Shift+O  Toggle child-origin offsets: APPLIED vs ZEROED
- I        Solo/isolate one child
- Shift+I  Show all children
- V        Hide one child at a time
- Shift+V  Show all children
