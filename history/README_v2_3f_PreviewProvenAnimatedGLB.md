# UBE v2.3f Build 319 — Preview-Proven Animated GLB Export

Some Unity clips play perfectly in UBE even though their runtime owner/linkage
points at an unrelated scene object or their binding table also contains
unidentified non-Transform renderer properties. Earlier builds treated those
advisory diagnostics as hard export blockers.

This build makes the resolved preview hierarchy authoritative for Animated GLB
export:

- a strange or unrelated runtime owner link no longer hides export when the
  actual skeleton and renderable hierarchy are fully resolved;
- complete Transform and quaternion skeletal animation is baked from the same
  sampled pose data used by the working preview;
- unsupported non-Transform bindings are reported and omitted rather than
  blocking the whole export;
- unresolved Transform paths, incomplete skin/weight/bind-pose data,
  constraints, duplicate renderer instances and unsafe scale/shear cases remain
  hard structural blockers; and
- the button tooltip, animation status and successful-export dialog state any
  omitted property channels or ignored runtime-linkage warning.

This specifically supports well-resolved character clips such as the tested
Angry Birds skeletal animations while keeping the existing conservative checks
for genuinely incomplete exports.
