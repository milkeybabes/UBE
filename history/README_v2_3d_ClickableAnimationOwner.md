# UBE v2.3d Build 317 — Clickable Animation Owner

AnimationClip preview already reported the resolved owner in the status line, but locating that GameObject still required manually typing its name into search.

The AnimationClip inspector now adds a clickable **Animation owner** card after preview resolution. It shows:

- the resolved owner GameObject name and PathID;
- a direct link to open that owner; and
- the resolution evidence used by UBE, such as Legacy Animation ownership, Animator/controller wiring, clip-named ownership, numbered variant ownership or coherent hierarchy resolution.

The owner is retained separately from any render-only ancestor promotion, so a promoted preview root does not replace the actual animation owner. The inspector refreshes once after the first frame is prepared, without creating a duplicate history entry.
