UBE v1.6f - Canvas / CanvasGroup / CanvasRenderer inspectors
=============================================================

Build 189 adds educational inspectors for Unity UI Canvas components.

Added inspectors:
- Canvas
- CanvasGroup
- CanvasRenderer

Canvas inspector shows:
- GameObject reference
- enabled state
- render mode: Screen Space Overlay / Screen Space Camera / World Space
- camera / plane distance / target display where exposed
- pixel perfect and event flags
- scale factor and reference pixels per unit
- sorting layer/order and extra shader channels
- sibling UI components on the same GameObject
- plain-English explanation of what a Canvas does

CanvasGroup inspector shows:
- alpha / opacity
- interactable
- blocks raycasts / clicks
- ignore parent groups
- sibling UI components
- explanation of fade/interaction behaviour

CanvasRenderer inspector shows:
- GameObject reference
- colour/cull fields where exposed
- material slots and pop materials where exposed
- sibling UI components on the same object
- explanation that CanvasRenderer is the low-level draw component for UI graphics

Kept from v1.6e:
- BoxCollider visual preview
- Camera frustum visual preview
- Camera / BoxCollider inspectors
- AnimatorController / AnimationClip inspectors
- Sprite / SpriteRenderer inspectors and external resolver
- GLB golf-ball texture/normal fixes
- OpenGL normal/bump preview
- filtered export
- UV infinity crash guard
