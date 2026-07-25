# UBE v2.3c Build 316 — Audio Mixer Inspectors

UBE now has dedicated inspectors for Unity audio-routing assets:

- `AudioMixerController`
- `AudioMixerGroupController`
- `AudioMixerSnapshotController`
- `AudioMixerEffectController`

## Audio Mixer Group

The group inspector shows the owning mixer, parent/child routing, volume/pitch/send parameter IDs, mute/solo/bypass state, effect-chain references and other exposed fields.

Most importantly, reverse relationships are indexed from every loaded `AudioSource`. Opening a mixer group therefore shows every AudioSource routed through that group.

This is a routing relationship rather than an AudioClip assignment. A mixer group can lead back to the source components, but an AudioSource whose clip field is null still receives its sound from runtime code, events or another audio manager.

## Mixer, snapshots and effects

The mixer inspector shows the master/output group, group and snapshot references, exposed parameters and runtime/suspend settings where available. Snapshot inspection reports stored parameter values and transition overrides. Effect inspection reports group/send wiring and effect parameters where Unity exposes them.

All mixer assets use the relationship-flow preview so the routing graph can be followed visually and clicked in either direction.
