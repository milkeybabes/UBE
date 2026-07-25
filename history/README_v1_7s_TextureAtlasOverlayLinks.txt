UBE v1.7s - Texture Atlas Overlay Links
=======================================

Build 212.

Adds interactive atlas rows for Texture2D inspector output.

When a Texture2D has Texture Atlas Region Finder rows, the row number becomes
clickable. Clicking it draws the estimated UV rectangle over the texture preview.

Useful for large shared level atlases where many renderers use different tiny
patches of one 2048/4096 texture.

Also links the object row name to the renderer where the renderer PathID is
available, making it quicker to jump from atlas usage to the actual object chain.

Notes:
- The atlas box uses the automatically estimated mesh UV bounds.
- It is an educational/debug visual, not a Unity material renderer.
- Extremely tiny/zero-size UV rows are expanded to a small visible marker.
