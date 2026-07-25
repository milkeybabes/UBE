UBE v1.8w build 243 - NavMesh First Pass

Adds first-pass educational inspectors and preview cards for Unity navigation /
AI pathfinding objects:

  NavMeshData
    - explains baked invisible walking/pathfinding surface
    - reports tiles, sources, off-mesh links, bounds/params/build settings where exposed
    - shows tile/raw-data summary where available

  NavMeshSettings
    - scene/source navigation settings
    - NavMeshData references and build/agent settings where exposed

  NavMeshProjectSettings
    - project-wide agent/area/build settings where exposed

Preview:
  - symbolic top-down triangulated walking surface
  - example path line
  - different area/cost region
  - off-mesh link/jump cue

This is intentionally educational first-pass support. Real decoded navmesh
triangle rendering can be added later if UnityPy exposes enough triangulated
runtime data for a given Unity version/game.
