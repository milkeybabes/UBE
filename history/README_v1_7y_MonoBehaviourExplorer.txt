UBE v1.7y - MonoBehaviour Basic Field Explorer

Added a first-pass MonoBehaviour / custom script inspector.

What it shows:
- owning GameObject
- enabled state
- script asset / MonoScript reference
- class, namespace, assembly and execution order where Unity exposes them
- Unity typetree/custom serialized fields when available
- object references found inside custom fields
- string values found inside custom fields
- educational notes explaining when only shell data is available

Also:
- MonoBehaviour now opens the Object View / component chain panel when it has an owning GameObject.
- relationship graph now scans exposed MonoBehaviour PPtr fields so references can appear in the clickable relationship card.
