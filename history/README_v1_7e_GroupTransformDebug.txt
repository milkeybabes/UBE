UBE v1.7e - Group Transform Debug Helpers

Adds two group/assembly preview debug tools aimed at mismatched child transforms:

  I       Solo/isolate one child at a time in group preview
  Shift+I Show all children again
  O       Toggle child origin/pivot markers

Existing V/Shift+V hide-cycle remains unchanged.  Solo mode and hide mode are
mutually exclusive so the preview always has a clear meaning.  The status bar
shows the child number, name, and local group origin where available.
