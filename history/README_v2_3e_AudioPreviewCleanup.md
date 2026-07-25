# UBE v2.3e Build 318 — Audio Preview Cleanup

Audio preview playback was working, but Windows could report a `WinError 32` traceback when UBE closed because Qt Multimedia / FFmpeg still held the temporary WAV while Python attempted to remove its preview folder.

This build adds a complete audio-preview shutdown path:

- stops playback and clears the `QMediaPlayer` source;
- allows Qt/FFmpeg event processing to release the Windows file handle;
- detaches and disposes the multimedia output during application shutdown;
- explicitly cleans the current audio preview directory;
- uses Windows-safe `TemporaryDirectory(ignore_cleanup_errors=True)` handling; and
- runs the same teardown from both the window close event and Qt's `aboutToQuit` signal.

Audio playback and FSB5/vgmstream decoding behaviour are otherwise unchanged.
