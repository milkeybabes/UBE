# UBE v2.0t Build 282 — FSB5 Audio Preview

UBE already exposed Unity `AudioClip` metadata and exported the original audio
container.  This update adds practical playback for the FMOD FSB5 containers
used by Walkabout Mini Golf and many other Unity games.

## What changed

- Correctly recognises the real 60-byte FSB5 v1 header.
- Displays FSB5 version, codec, sample/subsong count, frequency, channels and
  calculated duration where available.
- Adds an FSB5 sample/subsong selector for banks containing multiple sounds.
- Adds **Play**, **Stop**, and **Locate vgmstream...** controls to the AudioClip
  preview.
- Uses `vgmstream-cli` only as an optional decoder.  The selected FSB5 sample is
  converted to a temporary WAV, then played by the existing Qt Multimedia
  player.
- Remembers the chosen `vgmstream-cli` path in UBE settings.
- Searches automatically beside UBE, on PATH, and in common folders including
  `Tools/vgmstream` and `ExternalTools/vgmstream`.
- Runs decoding on a worker while Qt continues processing Windows messages, so
  the application should remain responsive.
- Preserves UBE's native export behaviour: the original `.fsb` remains the
  exported asset; temporary WAV files are only for preview.

## Installing the optional decoder

Download the Windows vgmstream command-line bundle and keep its supplied DLLs
with `vgmstream-cli.exe`.  Either:

1. Put the complete folder at `Tools/vgmstream` inside UBE; or
2. Click **Locate vgmstream...** in the AudioClip preview and select
   `vgmstream-cli.exe`; or
3. Put `vgmstream-cli.exe` on the Windows PATH; or
4. Set the `UBE_VGMSTREAM` environment variable to the executable or its folder.

UBE itself still starts and all non-audio features continue to work when
vgmstream is absent.
