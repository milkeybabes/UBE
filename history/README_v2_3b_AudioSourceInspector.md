# UBE v2.3b Build 315 — AudioSource Inspector

UBE now has a dedicated inspector for Unity `AudioSource` components.

The inspector resolves the scene playback chain:

```
GameObject → AudioSource → AudioClip
```

It shows:

- the owning GameObject;
- the assigned AudioClip as a clickable relationship;
- resolved clip name, duration, channels, frequency, compression and storage;
- play-on-awake, loop, mute, volume, pitch and priority;
- bypass and mixer-routing fields when present;
- 2D/3D spatial blend, pan, Doppler, spread, min/max distance and rolloff;
- custom distance/spatial curves when exposed by the Unity typetree; and
- a clear explanation when no serialized clip is assigned and runtime script assignment is likely.

AudioClip reverse relationships now index AudioSources, so opening an AudioClip
also shows every loaded AudioSource that uses it. This makes companion audio much
easier to identify for animation roots such as `MightyAudioPlayer`, while noting
that exact synchronisation may still be triggered by a MonoBehaviour,
AnimationEvent, Timeline, or other runtime controller.
