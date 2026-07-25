UBE v1.8v build 242 - Collider Shape Previews

Adds visual previews for primitive collider types beyond BoxCollider:

  SphereCollider
    - scaled wire sphere from local center and radius
    - shows diameter, trigger/solid state, offset from local origin
    - useful for pickup/proximity/hit/detection volumes

  CapsuleCollider
    - scaled capsule schematic from center, radius, height and direction
    - useful for character/body/controller rounded collision

  MeshCollider
    - follows and previews the linked collision Mesh where resolvable
    - notes that this is the collision mesh, not necessarily visible artwork

Also updates collider preview context and inspector insight text.
