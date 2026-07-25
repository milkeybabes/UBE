Unity Bundle Explorer v1.9c - UV Toggle Preserve View

Change
------
Pressing U to cycle UV channels now preserves the current 3D inspection view:

- zoom / camera distance
- orbit rotation
- pan position
- field of view
- model corrective rotation
- close-up clipping mode

Previously the UV-channel reload called the normal mesh framing routine, returning
the object to its initial isometric position and zoom. The U toggle now snapshots
the existing view before reloading and restores it immediately afterward.

No UV selection, export, material, texture, or mesh-rendering behaviour was changed.
