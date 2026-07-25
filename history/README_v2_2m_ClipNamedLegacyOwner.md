# UBE v2.2m — Clip-Named Legacy Owner

Build 302 fixes Legacy clips whose target path is repeated across many prefabs but whose exact clip copy is not directly referenced by a serialized `Animation` component in the opened bundle.

For example, `flagStopper_pink_FlagRaise_WAM_Legacy` now uses the longest matching GameObject owner name (`flagStopper_pink`) and resolves `flagRaiser` only inside that owner. It no longer promotes the generic path match to the broad `Hole17` parent or assembles every flag colour variant.

The fallback is conservative: it is used only for Legacy clips, requires every playable Transform path to exist beneath the named owner, rejects very short ambiguous owner names, and prefers the smallest matching renderable subtree.
