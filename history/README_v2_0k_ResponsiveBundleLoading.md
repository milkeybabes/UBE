# UBE v2.0k — Responsive Bundle Loading

Large Unity bundles no longer leave the main window appearing frozen while they open.

- Shows a simple **Loading bundle — please wait…** dialog before expensive work begins.
- Uses stage text rather than a misleading percentage progress bar.
- Safety preflight is polled without blocking the Qt event loop.
- Main UnityPy decoding runs on a worker thread while the UI keeps repainting.
- Asset-tree construction yields to Qt every 500 records.
- Related course/sibling bundles use the same responsive loader.
- The notice closes automatically when loading finishes or a header-only warning must be shown.

Version: **2.0k**  
Build: **273**
