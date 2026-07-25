UBE v1.7o - Clickable Component Links
=====================================

Small navigation improvement for GameObject/component inspection.

Added:
- GameObject component lists are now clickable in the UI inspector.
  Example: click Transform, LODGroup, Light, Renderer, Collider, Script, etc.
  directly from the selected GameObject instead of searching for its PathID.

- Component records now show a Quick Links card when they expose m_GameObject.
  This lets you jump back from a component such as LODGroup_28227 to the
  owning GameObject such as WildFlowers_Merged_08_LODGroup.

This is especially useful for LODGroup browsing, because the parent GameObject
contains the LODGroup component and the child LOD0/LOD1 objects.
