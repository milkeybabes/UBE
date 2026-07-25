# UBE v2.0v Build 284 — Decoded WAV Export

UBE can now export AudioClips in either of two forms:

1. **Original Unity audio container**
   - Preserves the exact recovered `.fsb`, `.ogg`, `.wav`, `.m4a` or other native container.
   - FSB banks retain all internal samples/subsongs.

2. **Decoded standard WAV via vgmstream**
   - Available when UBE can locate `vgmstream-cli`.
   - Converts the selected AudioClip to a normal RIFF/WAV file suitable for ordinary players and editors.
   - Does not modify the game data or the original FSB/resource file.

## Sample/subsong handling

For a single selected FSB5 AudioClip, WAV export follows the sample/subsong currently selected in the AudioClip preview. The sample number is added to the filename when it is greater than 1.

For multi-clip/batch WAV export, UBE decodes sample/subsong 1 from each AudioClip. Native export remains the better choice when a multi-sample FSB bank must be preserved intact.

## Output

Files are written below the chosen folder in:

```text
Audio/
    ClipName.wav
    ClipName__metadata.json
```

The metadata records the source container, selected subsong, decoder path and external `.resource`/`.resS` source where applicable.

Decoder installation remains optional and is described in `AUDIO_HELP.txt`.
