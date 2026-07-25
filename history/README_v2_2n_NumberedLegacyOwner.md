# UBE v2.2n — Numbered Legacy Owner

Build 303 fixes Legacy clips whose playable target names repeat across many prefabs while the clip name identifies a numbered owner instance.

For example, `CupSheepAnim (4)_sheepMove1_WAM_Legacy` now resolves the generic `CupSheep` and `CupSheep/Flag` paths through the ancestor branch matching `CupSheepAnim (4)`, rather than promoting all repeated `CupSheep` targets to the broad `Hole17` owner.

The resolver is bounded, requires every playable path below one coherent owner, strongly prefers the same parenthesized instance number, and retains the existing clip-named owner fallback used by `flagStopper_pink`.
