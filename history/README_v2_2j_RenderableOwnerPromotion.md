# UBE v2.2j — Renderable Owner Promotion

Some AnimationClips bind to a skeleton or helper hierarchy whose root contains
no renderer. The visible SkinnedMeshRenderer can be a sibling beneath the next
character/object owner. v2.2i correctly used unsupported property bindings to
identify the animation family, but could stop at that non-renderable branch.

v2.2j keeps the resolved curve and bone targets and walks upward through a
bounded maximum of 12 parent Transforms. It selects the first nearby owner that
contains renderable descendants and uses that as the preview root. This avoids
promoting all the way to an entire scene while allowing clips such as CaterJaw
to recover their character mesh.

The animation status line reports when the preview root was promoted.
Ctrl+A / Command+A text selection and all v2.2i binding-context behavior remain.
