UBE v1.7f - Group Origin Offset Debug
====================================

Adds Shift+O in group/assembly preview.

O toggles child origin/pivot markers as before.
Shift+O toggles a debug-only mode that temporarily zeroes each child Transform
origin offset before drawing the group. This is useful when comparing common/prefab
asset groups against level-instance groups and checking whether a visible mismatch
is caused by child Transform origins being applied to meshes that already contain
their authored offset.

Status text reports:
  Group origin offsets: ZEROED / test mode
  Group origin offsets: APPLIED / Unity transform mode

This does not alter assets or export data. It is a visual/debug mode only.
