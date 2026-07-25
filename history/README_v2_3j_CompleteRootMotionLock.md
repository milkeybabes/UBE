# UBE v2.3j — Complete Root-Motion Lock

**In place** now holds the complete authored first-frame transform of each detected world-motion controller: position, rotation/euler and scale.

Earlier builds identified motion roots from position/scale tracks but allowed their root rotation to continue. On rigs such as the Atlantis manta ray, the visible mesh is offset beneath `RayMover_CTRL`; rotating that parent swings the entire ray through a large world-space arc even while the controller position is frozen.

Only the selected top motion-controller roots are held. Descendant skeletal animation—including body, fin, wing, tail, jaw and other local rotations—continues unchanged. Preview, duration-limited looping and Animated GLB sampling use the same first-frame TRS baseline.
