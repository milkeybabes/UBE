# UBE v2.0n Build 276 — Texture Focus Layout Restore

## Fix

Texture2D focus mode now restores the normal UBE layout without collapsing the asset sidebar.

- Saves the outer splitter widths before focus mode.
- Restores them after the hidden panels have re-entered the Qt layout.
- Repeats the restore over a few event-loop turns to accommodate Windows geometry settling.
- Prevents the fullscreen-sized QLabel pixmap from becoming a minimum layout width.
- Preserves texture zoom, pan and the texture pixel under the centre of the view.

The 3D focus behaviour is unchanged.
