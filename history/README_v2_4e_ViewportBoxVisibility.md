# UBE v2.4e — Viewport Box Visibility

## Controls

- **Shift + left-drag:** isolate every render instance touched by the rectangle.
- **Ctrl + left-drag:** hide every render instance touched by the rectangle; repeated boxes accumulate.
- **Shift + I** or **Shift + V:** restore all render instances.

The filter is evaluated at the current displayed pose and remains attached to the selected render-instance identities while the animation continues. Animated GLB export maps those visible preview children back to the original animation render-item list, so the exported file matches the visible scene.

Screen bounds use a bounded per-renderer vertex sample rather than every vertex, keeping selection responsive for dense animated scenes.
