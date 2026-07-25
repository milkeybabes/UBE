UBE v1.7r - Texture Atlas Region Finder
========================================

Adds an automatic atlas-region section to the Texture2D inspector.

When a Texture2D is selected, UBE now tries to trace:

  Texture2D -> Material -> MeshRenderer/SkinnedMeshRenderer -> Mesh UV bounds

and then converts the mesh UV bounds into pixel regions on the selected texture.

This helps answer:

  "I can see this part of a big atlas texture, but which object/mesh uses it?"

The section shows:

  * GameObject name
  * Renderer name
  * Mesh name
  * Material name and texture slot
  * UV channel used
  * Estimated pixel region on the selected texture
  * Whether the region looks like a small atlas tile, large atlas area, or mostly full texture

This is an automatic first pass, not yet a manual click-and-drag rectangle picker.
It should still be very useful for level atlases and shared mobile/VR textures.
