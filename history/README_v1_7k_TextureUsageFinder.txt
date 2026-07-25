UBE v1.7k - Texture Usage Finder
================================

Build 204 adds a first-pass Texture Usage Finder to the Texture2D inspector.

When you select a Texture2D, UBE now tries to trace:

  Texture2D -> Materials/Sprites -> Renderer/GameObject

It shows:

  - Materials that use the texture
  - The material slot/property name, such as _BaseMap or _EmissionMap
  - Renderer/GameObject users found through those materials
  - Sprites that use the texture, including sprite rects where available
  - A short explanation of common texture roles

This is intentionally a fast current-bundle/course-local lookup. It uses the
same related-bundle resolver already used by UBE, but it does not open every
bundle in a very large game folder while you click around.

This is useful when you find a texture/atlas and want to know which material,
object, sprite, or renderer is probably using it.

Kept from v1.7j:
  - bump-preview crash guard
  - zero default model rotation
  - group assembly preview/debug keys
  - shader intent preview
  - Recent menu
  - all v1.6 and earlier preview/export features
