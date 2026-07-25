# UBE v2.2e Build 294 — First-Frame Animation Holding Pose

## What changed

AnimationClip selection now samples and displays the clip at time **0.000 seconds** immediately. Previously UBE displayed the serialized/rest pose until Play was pressed, so clips whose first keyframe differed from that pose appeared to jump, shrink, or move suddenly on the first click.

The time-zero pose is also used to frame the camera, so authored root offsets do not leave the first animation frame outside the current view.

## Reset pose

**Reset pose** still restores the original serialized GameObject/bind pose and reframes it for inspection. Starting playback after Reset returns to the sampled first frame and reframes it before the timeline advances.

## In place

The manual **In place** option remains available for clips with intentional scene/root movement. Toggling it re-evaluates and reframes the current animation time.
