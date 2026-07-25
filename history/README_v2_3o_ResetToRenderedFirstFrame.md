# UBE v2.3o — Reset to Rendered First Frame

- Reset pose now returns to the clip's exact authored frame-zero result.
- The reset uses the same complete Transform, constraint, CPU skinning and In-place pipeline as normal playback.
- Raw serialized/rest hierarchy transforms are no longer used for animation reset.
- This prevents environmental creatures such as the Atlantis manta rays and whale from shrinking to a dot, disappearing or forcing an extreme camera zoom after Reset pose.
- The timeline returns to frame 0 and the camera reframes the visible frame-zero geometry at its normal size.
- The original serialized transforms remain available through the ordinary asset/Object inspectors; they are simply no longer treated as the animation player's useful reset pose.
