UBE v1.5y - Sprite External Resolver / Sprite Export
====================================================

Build 182 adds the next Sprite/SpriteRenderer investigation step.

New:
- SpriteRenderer inspector now follows external Sprite PathIDs through the project PathID index / hydrated external bundle cache.
- SpriteRenderer now shows raw PathID/FileID, resolved Sprite name, owning bundle, loaded-vs-metadata state, Sprite texture, rect, pivot, PPU, and geometry when hydrated.
- Sprite inspector now shows raw/resolved Texture2D and alpha texture references.
- Selecting a SpriteRenderer hydrates the referenced external Sprite bundle on demand, e.g. common_assets_all.bundle for ArrowFilled.
- Basic preview for Sprite and SpriteRenderer: shows the backing Texture2D in the preview pane.
- Sprite PNG export: crops the Sprite rect from the backing Texture2D into Sprites/.
- SpriteRenderer PNG export: exports the Sprite used by the renderer.

Notes:
- Sprite export uses Unity sprite rect as bottom-origin and converts to PNG/Pillow top-origin.
- Tight/custom sprite geometry is inspected but not yet drawn as the preview mesh; that is the next sensible step after seeing more samples.
- Existing GLB ball export, OpenGL normal preview, filtered export, and UV crash fixes are retained.
