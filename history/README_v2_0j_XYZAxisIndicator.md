# UBE v2.0j — XYZ Axis Indicator

Adds a compact camera-oriented coordinate triad to the lower-left corner of every OpenGL 3D preview.

- X is red, Y is green, and Z is blue, following the conventional RGB axis scheme.
- The triad follows mouse orbit, corrective rotation, and the numbered 0–6 standard views.
- It also includes UBE's selected authored ground/up basis, so Ctrl+X/Y/Z basis changes are reflected correctly.
- An axis pointing almost directly into or out of the screen is represented by a small coloured dot/ring rather than a misleading sideways line.
- Press **A** to toggle the indicator.
- The enabled/disabled choice is remembered through QSettings for later sessions.
- The overlay does not affect mesh bounds, clipping, camera controls, preview geometry, or OBJ/GLB export.

The 3D Preview Help panel now documents the A shortcut.
