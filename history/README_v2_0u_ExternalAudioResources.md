# UBE v2.0u Build 283 — External Audio Resources

Unity player-data folders often keep `AudioClip` metadata in a main file such
as `data.unity3d`, while the actual compressed audio bytes are stored in sibling
files such as `sharedassets3.resource` or `sharedassets4.resource`.

## What changed

- Opening the main Unity file now automatically discovers sibling `.resource`
  and `.resS` streamed-data files.
- These raw support files are registered for export/preview resolution but are
  not displayed as standalone assets in the tree.
- AudioClip extraction first uses UnityPy's normal resource resolver, then falls
  back to a direct sibling-file lookup using the clip's source, offset and size.
- Unity archive-style names such as
  `archive:/CAB-.../sharedassets3.resource` are normalised automatically.
- Common Unity naming variants such as `.resource`, `.resS` and `.assets.resS`
  are matched case-insensitively.
- If the source name differs, UBE can safely identify a sibling range by known
  audio container magic such as FSB5, FSB4, OGG or RIFF/WAV.
- Successfully resolved clips show the external resource path in the AudioClip
  preview and record it in the exported metadata JSON.
- Missing external data now produces a clear message naming the expected file,
  offset, size and folder rather than the vague “no readable audio data” error.

## Expected workflow

Keep the extracted Unity files together in their original folder, for example:

```text
data.unity3d
sharedassets2.resource
sharedassets3.resource
sharedassets4.resource
```

Open only `data.unity3d` in UBE. The `.resource` files do not need to be opened
separately; UBE uses them automatically as streamed-data companions.

FSB5 decoding still uses the optional `vgmstream-cli` setup described in
`AUDIO_HELP.txt`.
