# UBE v2.0g — Relationship Flow View

This build adds a compact clickable flow diagram for Unity assets that do not have a useful visual preview of their own.

## Deliberately shallow diagram

The view is intentionally limited to the nearest useful layer:

- Root parent, direct parent, owning GameObject, or known user above
- The selected asset in the centre
- Direct children, components, references, clips, or animation targets below

This avoids turning a large Unity scene into an unreadable whole-project dependency graph.

## Clickable navigation

Every resolved asset box is clickable and uses the same Back/Forward selection history as inspector hyperlinks. External sibling-bundle boxes load the referenced bundle and select the asset.

## Animation-aware wiring

- AnimationClip shows controllers/legacy Animation components that use it.
- Resolved binding paths appear as animation-target boxes.
- When a binding path maps back to a loaded scene GameObject, the box is clickable.
- Animator shows its owner, Controller and Avatar.
- AnimatorController / AnimatorOverrideController show using Animators and direct AnimationClips.

## Object and component flow

Transform-only parents, script holders and non-rendering components now show this diagram instead of a static “no mesh attached” message.

For GameObjects and Transforms it shows:

- Root parent and direct parent
- Owning GameObject where applicable
- Direct components
- Direct child GameObjects

Materials, renderers, meshes, shaders and MonoBehaviours also use UBE's existing relationship graph to expose their nearest references and users.

## Manual access

Right-click any asset and choose **Show relationship flow**. This lets the diagram be opened even when the asset normally has another 2D, symbolic or 3D preview.
