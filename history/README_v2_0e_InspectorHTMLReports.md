# UBE v2.0e — Inspector HTML Reports

This build separates **native asset export** from **inspector report export**.

## Why

AnimationClip, AnimatorController, Material, Shader, MonoBehaviour and many other Unity records are not OBJ/GLB assets. Right-clicking those branches should not lead into a mesh-format dialog. Their useful export is the decoded inspector information that UBE already displays.

## New report export

Right-click an asset or branch and use **Export inspector report**.

Available scopes:

- This asset
- This branch
- Filtered results in this branch
- All filtered results

Output modes:

- **One combined HTML report** — default for branches; includes a linked contents list.
- **One HTML file per asset** — useful when records need to be shared individually.

Reports include:

- Asset name and type
- SerializedFile identity and Path ID
- Full decoded UBE inspector text
- Relationships exposed by the inspector decoder
- External JSON comment text
- Bundle name, SHA-256 and Unity version

HTML is UTF-8, human-readable, printable, searchable, and opens in any browser.

## UI clarification

The existing asset exporters are now explicitly labelled **native asset data**. Unsupported record types no longer imply OBJ/GLB export. Selecting such a record changes the main export button to **Export Inspector Report...**.

For an Animation Clip type branch containing 85 clips, the default result is one HTML file with all 85 inspectors and a contents list.
