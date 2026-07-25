# UBE v2.0l Build 274 — Texture Fullscreen Focus

## New texture-viewer focus mode

When a Texture2D preview is visible, press any of:

- `Tab`
- `F11`
- backtick `` ` ``
- tilde `~`

UBE hides the tree, inspector, menus and export button so the texture can use the full application window. Press the same key again to return.

## View preservation

The texture viewer preserves:

- the current fit-relative zoom level;
- the texture pixel/region located at the centre of the view;
- atlas overlays and user selection boxes;
- pan position as closely as the new viewport permits.

The layout is restored after Qt finishes resizing the preview, avoiding the jump to a different atlas region that would otherwise occur when the panel dimensions change.

## Honest 100% cap

Fit-to-window no longer enlarges small decoded previews beyond native preview size. Wheel zoom, manual window resizing and focus-mode transitions are all clamped to a maximum of one screen pixel per decoded preview pixel. This avoids suggesting detail that is not present in the decoded preview cache.

## Existing controls retained

- Mouse wheel: zoom around pointer
- Middle mouse drag: pan
- Double-click: reset to fit
- Left drag: atlas-region selection
