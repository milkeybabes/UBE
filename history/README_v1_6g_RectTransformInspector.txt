UBE v1.6g - RectTransform Inspector
===================================

Added a specialised RectTransform inspector.

RectTransform now shows:
- GameObject and parent transform reference
- child count and root/order index
- local position / rotation / scale
- UI anchors: anchor min/max
- anchor mode: fixed, horizontal stretch, vertical stretch, or both
- anchored position
- size delta
- pivot
- simple local-rect estimate for fixed-anchor UI elements
- plain-English explanation of RectTransform vs normal Transform
- sibling UI components on the same GameObject

This is an educational/inspection pass only; no extra preview visual was added because RectTransform is usually more useful as layout data inside Canvas/UI than as an isolated 3D object.

Kept from v1.6f:
- Canvas / CanvasGroup / CanvasRenderer inspectors
- Camera frustum visual
- BoxCollider visual
- Sprite / SpriteRenderer resolver and preview/export
- AnimationClip / AnimatorController inspectors
- GLB ball texture/normal fixes
- OpenGL normal/bump preview
- filtered export
- UV crash guards
