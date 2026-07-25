UBE v1.7b - Group / Assembly Preview
===================================

Adds a first-pass visual preview for transform-only GameObject parents.

If a selected GameObject/Transform has no direct renderer but has renderable child
GameObjects underneath it, UBE now assembles those child meshes in the 3D preview
panel using their local transforms relative to the selected parent.

This is intended for Unity scene/group objects such as:

  *_GRP
  prop groups
  machinery assemblies
  fish/decor clusters
  transform-only parent nodes

First-pass behaviour:

  - renderable descendants are found recursively, with a safe limit
  - child local position/rotation/scale are composed under the selected group
  - preview is centred and scaled to fit as one assembled object
  - parts are drawn with simple per-child colours, not full multi-material rendering yet

This is preview-only for now. Group/branch export as one assembled GLB/OBJ can be
added later once the visual behaviour is checked.
