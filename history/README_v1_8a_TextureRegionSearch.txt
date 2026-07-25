UBE v1.8a - Manual Texture Atlas Region Search
================================================

This starts the 1.8 line after the v1.7 final checkpoint.

New texture atlas workflow:

  * Select a Texture2D.
  * Left-drag a box directly on the texture preview.
  * UBE searches the Texture Atlas Region Finder rows for mesh UV rectangles
    that overlap your drawn area.
  * Results are appended to the asset details panel with clickable UV/object links.
  * Existing atlas UV row links still draw their own overlay boxes.

Texture preview controls:

  * Mouse wheel: zoom in/out around the pointer.
  * Left drag: draw atlas search rectangle.
  * Middle drag: pan while zoomed in.
  * Double-click: reset to fit.

Inspector right-click helpers:

  * Expand all inspector sections.
  * Collapse all inspector sections.
  * Show/hide manual atlas search results when available.
  * Clear manual atlas search results when available.

Notes:

  The manual region search compares your drawn box against the mesh UV bounds
  already calculated by the Texture Atlas Region Finder. Very broad/full-texture
  UV regions are hidden from the main list when more useful compact atlas hits
  exist, because otherwise full-UV meshes would match every area.
