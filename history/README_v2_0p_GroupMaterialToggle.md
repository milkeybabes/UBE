# UBE v2.0p Build 278 — Group Material Toggle

Generic parent/GameObject assembly previews can now switch between the existing
per-child debug palette and the children’s resolved material/texture appearance.

## Controls

- **P** — toggle **Debug palette** / **Real materials**.
- The mode is remembered between sessions and is used for later group previews.
- Camera distance, orbit, pan, model rotation, FOV, close clipping, hidden/solo
  child state and origin markers are preserved while switching.

## Rendering behaviour

- Real-material mode exports each renderable child using the same object-preview
  pipeline as normal selections.
- Each child may use its own resolved base texture.
- Shared textures are uploaded only once and reused by all matching children.
- Children without a decoded texture use their material colour, or a neutral grey
  when no usable colour is exposed.
- **T** remains available to test material tint multiplication on textured assets.
- Debug palette mode is unchanged and remains useful for identifying individual
  descendants and transform placement problems.

The toggle applies to generic assembled parent/group previews. LOD previews and
normal multi-selection previews already use their own material-aware paths.
