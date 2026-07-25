# UBE v2.2p — Bounded Compact Legacy Owner

Fixes a GUI lock introduced by v2.2o when selecting Legacy clips with many repeated target names.

The compact-owner resolver no longer rebuilds and scans a full descendant path index for every possible owner. It now derives candidate owners directly from authored path depth, intersects those owners across all animated paths, and performs only a small bounded renderability check.

Safety limits:
- maximum 64 target candidates per authored path
- maximum 24 coherent owner roots checked
- maximum 3 parent promotions
- maximum 96 rendered items / 12 hierarchy levels
- strict time budget; incomplete searches return to the established resolver rather than blocking the GUI

Existing Legacy, Animator, streamed curve, CPU skinning, first-frame pose, and Ctrl+A fixes remain included.
