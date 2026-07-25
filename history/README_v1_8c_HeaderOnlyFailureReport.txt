UBE v1.8c - Header-only Failure Report
======================================

Build: 223

This build adds clearer reporting when the safe bundle-open guard blocks a problem bundle from full object decoding.

What changed
------------
- The Bundle Summary Dashboard now shows an Open Status card near the top.
- If a bundle fails the UnityPy child-process preflight, UBE shows:
  - Header readable: yes/no
  - Full object decoding: blocked by safe preflight
  - Reason from the child process / timeout / crash
  - Explanation that the app stayed open and the file is being shown header-only.
- The top preview panel also switches to a clear Header-only safe mode message for blocked bundles.
- Normal bundles show a small “full load passed safe preflight” note.

Purpose
-------
Some third-party UnityFS bundles can make UnityPy/native decoding quit the Python process.
The v1.8b guard stops the main app from closing. v1.8c makes that state obvious to the user instead of looking like an empty or broken bundle.

Compile check
-------------
Passed for:
- unity_bundle_explorer/ui/main_window.py
- unity_bundle_explorer/core/bundle_reader.py
- unity_bundle_explorer/app_info.py
