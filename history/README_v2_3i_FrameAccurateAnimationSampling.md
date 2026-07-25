# UBE v2.3i Build 322 — Frame-Accurate Animation Sampling

This build fixes a one-tick pose explosion found in the Atlantis manta-ray
animation while scrubbing a five-second in-place range.

## What happened

The old timeline always used 1,000 slider divisions.  With a five-second range,
the first slider step was 0.005 seconds.  On a 60 fps clip that is not an
authored frame: real frames are 0.016667 seconds apart.

UBE's streamed-curve preview uses practical linear interpolation.  Most rigs
look correct at arbitrary sub-frame times, but a hierarchy containing animated
non-uniform scale can pass through an impossible intermediate pose.  The manta
therefore appeared to teleport or enlarge for a single tiny slider step even
though its authored frames were sound.

## Frame-accurate timeline

- One slider unit now equals one authored animation frame.
- The slider maximum follows the active Full/Limit duration and clip sample rate.
- Arrow/single-step movement advances one exact frame.
- Page movement advances approximately one second.
- Playback keeps a continuous wall-clock accumulator but displays only authored
  frame samples, so 30 fps clips remain correctly timed on a faster UI timer.
- Animated GLB export was already baked on source-rate frame boundaries and is
  unchanged.

For a 60 fps, five-second range the slider now contains 300 frame steps rather
than 1,000 arbitrary time steps.  The first non-zero sample is 0.016667 s, not
0.005 s.
