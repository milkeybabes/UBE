# UBE v2.3h Build 321 — In-Place First Frame and Numeric Focus Fix

This build corrects two animation-control problems found while testing long
marine-life animations.

## First-frame-safe In place

In-place preview previously removed top-level position/scale tracks by falling
back to the serialized/rest Transform. Some environmental rigs store that rest
pose far away from the authored first animation sample, causing the model to
teleport or appear to move at extreme speed as soon as In place was enabled.

UBE now captures the authored position and scale at animation time 0 for every
locked root-motion Transform. In-place preview, looping, size checks and
Animated GLB export freeze those channels to the same first-frame values. The
first in-place frame therefore matches the normal authored first frame before
world-travel motion is removed.

## Numeric fields own numeric keys

The application-wide 3D-view shortcuts use keys 0-6 for standard camera views.
Those shortcuts previously intercepted digits typed into the animation Limit
spin box, leaving only unmapped digits such as 7 and 8 usable.

Editable line controls, plain-text editors, spin boxes and editable combo boxes
now take priority over all global preview hotkeys while focused. The Limit value
can be typed normally using every digit, decimal point, editing key and cursor
key.
