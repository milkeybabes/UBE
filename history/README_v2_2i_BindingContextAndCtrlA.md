# UBE v2.2i Build 298 — Binding Context and Ctrl+A

- Animation root selection now uses all generic binding hierarchy paths as context, including unsupported SkinnedMeshRenderer/property bindings. This helps disambiguate clips with only one playable Transform track and avoids selecting an unrelated duplicate hierarchy.
- Unsupported property bindings remain diagnostic only; UBE does not pretend to animate blend shapes/material/script properties yet.
- The animation status line reports how many property bindings were used for target context.
- The A axis-indicator hotkey now responds only to an unmodified A key. Ctrl+A on Windows/Linux and Command+A on macOS are left to the focused inspector/text widget for Select All.
