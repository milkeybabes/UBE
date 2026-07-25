UBE v1.8g - Cubemap Inspector

Adds first-pass Cubemap support:
- Cubemap icon/name in the tree and object counts.
- Cubemap inspector with face resolution, format, mip count, face/image count,
  GPU/stream size, decoded RGBA estimate, sampling settings, external stream data.
- Educational explanation of cubemaps as six-sided environment textures used for
  skyboxes, reflection probes, ambient/environment lighting and shiny materials.
- Cubemap preview: decoded contact-sheet image when UnityPy exposes one, otherwise
  a symbolic six-face +X/-X/+Y/-Y/+Z/-Z layout.
- Export Selected Asset attempts PNG/contact-sheet export when the decoder exposes
  a Cubemap image.
