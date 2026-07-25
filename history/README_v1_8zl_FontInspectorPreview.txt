UBE v1.8zl build 258 - Font Inspector + Sample Preview

Adds a first-pass Font / TMP_FontAsset inspector and preview.

Inspector:
  - Font name
  - Embedded font data size and file signature when exposed
  - Basic metrics where UnityPy exposes them
  - Material / atlas links where exposed
  - Character rect and kerning counts
  - First glyph rect samples when available
  - Educational note explaining dynamic fonts vs bitmap/atlas font assets

Preview:
  - Sample card in the top preview pane
  - Tries to load embedded TrueType/OpenType bytes using Qt
  - Falls back to a system font using the asset name
  - Shows alphabet, numbers, pangram and UI-style sample text

Coverage:
  - Font upgraded from Basic to Good coverage
  - TMP_FontAsset gets first-pass preview support
