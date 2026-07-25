UBE v1.8t build 240 - Five Inspector Wins

Adds first-pass specialised inspectors for five useful Unity systems found in
larger/older games such as Angry Birds VR:

1. SpriteMask
   - sprite mask shape, alpha cutoff, sorting range
   - explains that it is an invisible 2D stencil for SpriteRenderers

2. LineRenderer / TrailRenderer
   - material slots, width, positions where saved, alignment, texture mode
   - explains generated ribbon geometry vs normal Mesh assets

3. Physics group
   - Rigidbody: mass, gravity, kinematic state, damping, collision/constraints
   - SphereCollider / CapsuleCollider / MeshCollider: shape, trigger/material/layer fields
   - PhysicMaterial: friction and bounce settings

4. TextAsset
   - byte size
   - readable text/JSON/config preview when possible
   - binary hex preview when not text

5. PlayableDirector
   - playable/timeline asset reference, playback/update/wrap settings
   - scene bindings/exposed references where visible
   - explains Timeline/cutscene/sequencer role

Also updates:
  - tree icons/friendly names for these types
  - inspector coverage report levels
  - preview context notes
  - simple symbolic preview cards for these new families

Compile check passed for touched files.
