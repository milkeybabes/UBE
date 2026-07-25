UBE v1.8b - Safe Bundle Open Guard

- Adds a UnityPy preflight in a child process before full UI object loading.
- If a third-party bundle makes UnityPy/native decoding crash or quit, UBE now opens the bundle header-only and shows a clear warning instead of disappearing.
- External related-bundle loading now uses the same guard, so one bad sibling bundle should not close the app.

This is especially useful when exploring unrelated Unity games with different Unity versions/compression/layouts.
