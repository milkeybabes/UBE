# UBE v2.0d — Asset-Type Isolation

Build 266

## Isolate one asset type

Right-click a top-level asset-type group such as **Mesh**, **Material**, **Texture2D**, **GameObject**, or any other type and tick:

**Isolate asset type: _Type_**

UBE hides every other asset-type branch while leaving the selected type available for inspection. Only one asset type can be isolated at a time.

Untick the same checked menu item to restore all asset types.

## Works with the existing filters

The normal search box and branch-scoped keyword filter continue to work inside the isolated type. For example:

1. Isolate **Mesh**.
2. Search for `floor`.
3. Only matching Mesh assets remain visible.
4. **Export all filtered results** exports exactly those visible Mesh results.

Asset-type isolation is treated as an active tree filter, so filtered-result counts and exports follow the isolated view even when the keyword box is empty.

## Large-bundle behaviour

Isolation changes only the tree visibility; it does not discard or reload assets. Clearing it is immediate.

Non-selected type branches are rejected before UBE walks their children. This avoids unnecessarily visiting tens of thousands of hidden assets when a bundle contains 100,000 or more objects.

The isolated type heading remains visible even when a keyword matches zero assets, allowing it to be right-clicked and unticked without first clearing the search.

## Source changes

Opening another bundle, SerializedFile, or project folder clears the current type isolation automatically.
