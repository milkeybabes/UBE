UBE v1.5x Sprite Inspector
==========================

Added first-pass specialised inspectors for Unity Sprite and SpriteRenderer.

Sprite inspector shows:
- texture reference
- sprite rect
- texture size
- pivot / border / offset / PPU where exposed
- packing / mesh hints
- sprite geometry counts
- UV insight or rect-derived UVs

SpriteRenderer inspector shows:
- GameObject
- Sprite reference
- colour tint
- flip X/Y
- draw mode / size / tile mode
- renderer flags
- material slots
- resolved sprite texture/rect summary

This is an inspection-only pass so we can see what UnityPy exposes before adding preview/export.
