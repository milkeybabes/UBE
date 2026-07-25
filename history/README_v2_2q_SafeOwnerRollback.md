# UBE v2.2q — Safe Animation Owner Rollback

Build 306 removes the compact Legacy-owner searches introduced in v2.2o and v2.2p. Those searches could perform too much repeated hierarchy work on bundles containing many duplicate target names and block the GUI.

This build restores the last responsive v2.2n resolver:

- Legacy `Animation` component ownership remains supported.
- Clip-named owners such as `flagStopper_pink` remain supported.
- Numbered owners such as `CupSheepAnim (2)` remain supported.
- The v2.2o/v2.2p compact coherent-owner fallback is completely absent.
- Ambiguous unnumbered duplicate clips may fall back to a broader preview, but animation selection will not run the removed expensive search.

This is a deliberate safety rollback rather than another speculative resolver change.
