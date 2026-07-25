UBE v1.7g Shift+O Fix
======================

Fixes the group origin-offset debug shortcut.

Problem in v1.7f:
- Shift+O was intercepted by the main-window preview hotkey filter as plain O.
- Result: it only toggled origin/pivot markers instead of zeroing child-origin offsets.

Fixed in v1.7g:
- Shift+O is checked before plain O in the main-window event filter.
- Shift+O now calls toggle_group_origin_offset_mode().
- O still toggles child origin / pivot markers.

Expected status messages:
- O:       Group child origins: ON/OFF
- Shift+O: Group origin offsets: ZEROED / test mode
          or Group origin offsets: APPLIED / Unity transform mode
