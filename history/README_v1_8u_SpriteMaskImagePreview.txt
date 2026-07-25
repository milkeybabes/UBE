UBE v1.8u build 241 - SpriteMask Linked Sprite Preview

Improves SpriteMask preview.

Before:
  SpriteMask used a symbolic preview card only.

Now:
  SpriteMask resolves its linked Sprite reference and previews that Sprite image
  directly where possible.  This makes the mask shape obvious, e.g. a rounded
  button mask sprite or circular UI cut-out.

Fallback:
  If the Sprite cannot be resolved, UBE still shows the symbolic SpriteMask card.

Also updated:
  - preview context wording
  - SpriteMask inspector insight text
