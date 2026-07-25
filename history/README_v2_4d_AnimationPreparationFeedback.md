# UBE v2.4d Build 344 — Animation Preparation Feedback and Space Play/Pause

Large AnimationClip previews now show a responsive preparation notice with an
elapsed-time readout and honest stage descriptions. UBE reports substantial
operations only: curve/binding decoding, hierarchy and owner resolution,
renderable collection, external material hydration, preview geometry assembly,
CPU skinning, constraints and bounded Animated GLB compatibility checks.

Streamed clips report coarse 10% decoding/reconstruction milestones. Group
geometry, dependency hydration and skinning report bounded renderer batches.
Animated GLB eligibility still checks at most 96 representative poses. UBE does
not issue an update for every vertex or every authored frame, so clips containing
thousands of frames do not flood the UI or waste time repainting labels.

`Space` is now the universal AnimationClip play/pause shortcut. It works while
the tree, inspector or compact toolbar owns focus, ignores auto-repeat, and does
not intercept typing in comments, search fields or numeric editors. Modal export
work continues to process safe keyboard/timer events, so an already prepared
animation keeps playing and Space can pause/resume it while an animated GLB is
being written.

The animation toolbar also retains the user-confirmed compact values:

- Export GLB button width: 86 px
- Speed selector width: 58 px, labels use `x`
- Speed selector internal padding/dropdown style preserved
- Duration limit minimum width: 90 px
