UBE v1.8r build 238 - Serialized Folder Return Action

Fixes navigation after opening a source from:
  File -> Open Serialized Assets Folder...

When viewing a .assets/globalgamemanagers/level source opened from that list,
UBE now exposes a proper return path:

  File -> Return to Serialized Assets Folder
  Alt+Left
  Right-click tree -> Return to serialized assets folder

The same action still works for normal project/course folders:
  File -> Return to Project / Course List
  Alt+Left
  Right-click tree -> Return to project / course list

This avoids needing to re-open the same Serialized Assets Folder just to get
back to the root source list.
