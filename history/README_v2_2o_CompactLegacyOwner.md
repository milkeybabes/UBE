# UBE v2.2o — Compact Legacy Owner Resolution

Build 304 fixes repeated Legacy target names that still promoted to broad course roots such as `Holes_Easy` or `Hole17`.

For clips such as `CupSheepAnim_sheepMove1_Hard_WAM_Legacy` and numbered copies such as `CupSheepAnim (4)_sheepMove1_WAM_Legacy`, UBE now evaluates every coherent hierarchy instance containing all playable target paths, then prefers the nearest and smallest renderable owner. This prevents a one-object animation from assembling dozens of unrelated course props.

The candidate-root ranking used by the general animation resolver is also render-aware, so duplicate paths no longer fall back to an arbitrary PathID when one candidate has a compact renderable subtree and another only reaches a broad scene owner.
