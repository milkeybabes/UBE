UBE v1.7p - ReflectionProbe Inspector / Preview

Added lightweight ReflectionProbe support.

What is new:
- ReflectionProbe tree icon and friendly name.
- Inspector for ReflectionProbe fields:
  - owning GameObject
  - enabled state
  - probe mode/type: baked/custom/realtime where exposed
  - refresh mode and time slicing
  - cubemap resolution
  - box projection, box size and offset
  - blend distance, importance, intensity
  - HDR, dynamic objects, occlusion culling
  - culling mask, clear flags, clip/shadow distance
  - baked/custom cubemap references when present
- Symbolic preview panel showing probe volume, cubemap centre and blend region.

This is not a Unity reflection renderer. It is an educational/diagnostic view showing how the probe is set up and what region it influences.
