# UBE v2.3 Build 313 — Animated GLB and External Colour Maps

UBE v2.3 promotes the animation work from the v2.2 series into a major release.
The selected AnimationClip can now be exported as a portable animated GLB when
UBE has enough trustworthy data to reproduce it.

## Animated GLB

Compatible exports support:

- rigid Transform animation;
- skinned meshes, bones, bind poses, joint indices and vertex weights;
- mixed skinned characters and rigid animated props in one GLB;
- source-rate position, rotation and scale animation;
- strict glTF animation timestamps and validated skin layout;
- the current V/I preview visibility state;
- external comments as useful filenames; and
- automatic `_1`, `_2`, ... suffixes instead of overwriting an earlier export.

The export option remains unavailable for unresolved runtime/constraint cases or
incomplete visual linkage rather than producing a guessed file.

## `_ColorMap` and custom base-colour slots

Custom Amplify/Shader Graph materials may store visible colour in `_ColorMap`
instead of `_BaseMap` or `_MainTex`. UBE now treats these slots as base colour:

- `_BaseMap`
- `_ColorMap` / `_ColourMap`
- `_BaseColorMap`
- `_MainTex` / `_MainTexture`
- `_Albedo`
- `_BaseTex`
- `_BaseMap1`

This recognition is used by material preview, object/mesh texture selection,
OBJ/MTL export and GLB export.

When the slot points to an external texture that is not loaded, the inspector no
longer presents the grey fallback as an unexplained shader failure. It reports
the property, FileID, PathID and external SerializedFile/CAB name when available,
and explains that the dependency bundle must be present in the scanned project
folder/PathID index.

Recognising `_ColorMap` is necessary but cannot manufacture a missing atlas. Once
the referenced bundle is available and resolvable, UBE will use the colour map
automatically.
