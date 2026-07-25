UBE v1.7za - Preview Context Notes / 1.7 Final Polish
======================================================

Version: 1.7za
Build:   220

This is the final polish build for the 1.7 first-pass feature set.

Added an educational "Preview context" note in the inspector.  The note explains
what the top preview panel is actually showing when the selected asset is a
component or diagnostic record rather than a visible mesh.

Examples:

- MonoBehaviour selected:
  Shows the owning GameObject because scripts are not visible by themselves.

- MeshFilter selected:
  Shows the linked mesh with sibling renderer/material context where possible.

- MeshRenderer / SkinnedMeshRenderer selected:
  Shows the owning GameObject using this renderer's material slots.

- Transform selected:
  Shows the owning GameObject or renderable child group where available.

- Inactive GameObject:
  Notes that UBE still previews the object for inspection even if it is disabled
  in the saved Unity scene/prefab data.

- Light / Camera / Probe / Particle / Collider / UI records:
  Notes when the preview is a symbolic diagnostic diagram rather than Unity's
  final runtime rendering.

This keeps UBE aligned with its educational goal: show the component's place in
the Unity object chain, not just the raw serialized fields.

Compile check passed for:
  unity_bundle_explorer/ui/main_window.py
  unity_bundle_explorer/ui/preview_3d.py
  unity_bundle_explorer/core/asset_details.py
  unity_bundle_explorer/app_info.py
