UBE v1.6i - Helper / Collision Flat Preview
==========================================

Adds a texture-free flat shaded preview mode for helper/gameplay meshes.

New 3D preview hotkey:
  F   Toggle flat/helper preview

This ignores the material texture and shows the mesh shape with simple flat
shading plus a wireframe edge overlay.  It is intended for objects such as:

  NavMesh_*
  *CollisionPlayer*
  DoNotWarp
  Walkway
  Trigger / helper zones

These objects can legitimately have noisy or broad UVs into a large course
texture because the texture may be a shader ingredient or leftover/default
material.  The useful information is often the collision/navigation shape.
