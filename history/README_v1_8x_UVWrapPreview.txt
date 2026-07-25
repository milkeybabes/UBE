UBE v1.8x build 244 - UV Wrap / Repeat Preview

Adds a texture sampler wrap-mode diagnostic for 3D preview.

Why:
  Some Unity meshes use UVs outside 0..1 and rely on the material/texture sampler
  repeating the texture.  UBE previously forced GL_CLAMP_TO_EDGE, which can smear
  edge pixels and make custom shader character textures look badly misaligned.

New hotkey:
  W  Cycle texture wrap mode:
       Auto
       Clamp to edge
       Repeat / modulo UV

Auto behaviour:
  If the effective preview UVs extend outside 0..1 with a span larger than about
  one full texture tile, UBE assumes Repeat.
  Otherwise it assumes Clamp.

This works alongside:
  U  UV channel
  M  UV domain/remap/flip
  B  base/normal/emission/metal texture debug

BossPig/PigTex style UV ranges such as U -0.72..1.00 or V 0..1.20 should now
automatically try Repeat, and W lets the user compare Clamp vs Repeat instantly.
