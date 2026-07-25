# UBE v2.0s Build 281 — Responsive Finalizing

The remaining Windows **Not Responding** state during bundle opening occurred after UnityPy decoding had completed. The synchronous final stage was still sorting and inserting tens of thousands of QTreeWidget rows, auto-sizing a column across the complete tree, and building the detailed bundle-summary dashboard on the Qt GUI thread.

This update changes that final stage:

- Asset records are sorted in a worker while the loading notice remains responsive.
- QTreeWidget rows are inserted in short timer-driven slices through a real nested Qt event loop.
- Large trees no longer call `resizeColumnToContents()` across 100,000+ rows; they receive a sensible user-resizable width instead.
- Uniform tree-row heights and disabled branch animations reduce large-tree layout cost.
- The detailed Mesh/Material/Renderer summary dashboard is calculated in a worker, then its finished HTML is assigned on the GUI thread.
- Loading stages now distinguish sorting, tree construction, tree layout, summary analysis, and final display.

No percentage progress bar is used. The change is specifically aimed at keeping the native Windows message queue serviced throughout the complete open operation, including the former **Finalizing the bundle view** freeze.
