UBE v1.7w - Bundle Summary Dashboard
====================================

Adds a richer bundle-level dashboard when the root bundle item is selected or a bundle is first opened.

New dashboard sections:
- Header/version/file summary
- Object count and key component metrics
- Texture overview: total compressed/GPU size, approximate decoded RGBA size, texture format mix, largest textures
- Mesh overview: approximate total vertices/triangles, largest meshes
- Most-used visual assets: textures and materials used by the most renderer slots
- Scene/asset indicators: quick badges for LODGroup, lights, probes, particles, colliders, UI etc.
- External resolver status and full object counts table

Dashboard asset names are clickable where a local asset PathID is known.
