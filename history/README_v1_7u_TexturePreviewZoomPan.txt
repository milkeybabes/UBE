UBE v1.7u - Texture Preview Zoom / Pan
======================================

Adds a small 2D viewer mode for Texture2D previews.

Controls when a texture preview is visible:

  Mouse wheel       Zoom in / out around the mouse pointer
  Left drag         Pan while zoomed in
  Middle drag       Pan while zoomed in
  Double-click      Reset to fit view

Notes:

  * Texture previews now use a larger 2048px on-demand cache so large
    4096x4096 atlas textures have enough detail for inspection.
  * Atlas overlay boxes remain locked to the correct texture pixels while
    zooming and panning.
  * If already zoomed in, clicking a UV atlas row recentres the selected
    atlas box in the preview.

This keeps the Texture Atlas Region Finder educational: click UV0/UV1,
then wheel-zoom into the highlighted patch to see the actual artwork.
