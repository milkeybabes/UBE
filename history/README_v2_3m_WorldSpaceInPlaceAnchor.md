# UBE v2.3m — World-Space In-Place Anchor

## Change

`In place` now holds the effective visible render branch in world space rather than relying only on freezing selected local animation channels.

This handles rigs where hidden ancestors, sibling travel controllers, nested rotation, or animated non-uniform scale combine to move the rendered character even though the obvious root channels have been locked.

UBE selects the detected motion root that contains the visible skinned/rendered branch, evaluates its complete frame-zero matrix, and applies the inverse world delta to the whole preview hierarchy on later frames. Internal skeletal animation remains unchanged.

The same correction is used by live preview and Animated GLB export.
