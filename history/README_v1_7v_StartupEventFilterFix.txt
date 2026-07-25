UBE v1.7v - Startup Event Filter Fix
====================================

Fixes startup crash introduced by texture preview zoom/pan in v1.7u.

Cause:
  The global QApplication event filter was installed early in MainWindow.__init__().
  Qt can deliver menu/window events before self.preview is created.
  The v1.7u texture preview eventFilter referenced self.preview immediately,
  causing AttributeError on startup.

Fix:
  eventFilter now safely returns to QMainWindow until preview/preview_stack exist.

Kept from v1.7u:
  Mouse wheel texture zoom
  Drag texture pan
  Double-click reset to fit
  Atlas overlay boxes stay aligned while zooming/panning
