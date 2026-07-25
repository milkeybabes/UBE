# UBE v2.0h — Responsive Relationship Flow Wrapping

Relationship-flow cards no longer remain in one increasingly narrow row.

- The lane calculates how many useful-width cards fit in the current preview viewport.
- Cards wrap onto additional rows when necessary.
- A maximum of five cards is shown per row, even on very wide displays.
- A partial final row stays aligned to the same card grid instead of stretching.
- The diagram automatically reflows when the main window or splitter is resized.
- Existing clickable navigation and the ten-card shallow-flow limit are unchanged.

This prevents animation targets and component boxes from collapsing into one-character-wide columns.
