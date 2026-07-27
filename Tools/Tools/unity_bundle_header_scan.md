# unity_bundle_header_scan.py

Fast header scanner for Unity-style files.

It now recognises two important Unity file families:

## 1. UnityFS / UnityWeb / UnityRaw

These are AssetBundle-style containers. Examples:

```text
common_assets_all.bundle
data.unity3d
main.12345.com.game.obb
```

## 2. UnitySerializedFile

These are Unity serialized asset files. Examples:

```text
globalgamemanagers
globalgamemanagers.assets
globalgamemanagers.assets.split0
sharedassets0.assets
resources.assets
level0
```

These files do not start with `UnityFS`. They begin with a binary SerializedFile header and often contain a Unity version string near the start, such as:

```text
2022.3.33f1
6000.3.9f1
```

So a file can be 100% Unity data without having a `UnityFS` signature.

## Basic usage

Scan one folder:

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer\AssetBundle"
```

Scan one file:

```bat
python unity_bundle_header_scan.py "G:\BeatSaber\globalgamemanagers.assets.split0"
```

Scan subfolders recursively:

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive
```

Scan every file regardless of extension:

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --all
```

## Output files

The script writes:

```text
unity_header_scan_YYYYMMDD_HHMMSS.tsv
unity_header_scan_YYYYMMDD_HHMMSS.txt
```

## Detected signatures

| Signature | Meaning |
|---|---|
| `UnityFS` | Modern Unity AssetBundle-style container. |
| `UnityWeb` | Older Unity web-style container. |
| `UnityRaw` | Older/raw Unity container. |
| `UnitySerializedFile` | Unity `.assets` / `globalgamemanagers` / `sharedassets` style serialized file. |
| `FSB5` | FMOD audio bank/resource. |
| `ZIP/PK` | ZIP-style archive. |
| `Ogg/Vorbis` | Raw OGG/Vorbis audio. |
| `RIFF/WAV` | WAV audio. |
| `FLAC` | FLAC audio. |
| `Unknown` | Header not recognised by this simple scanner. |

## Example: Unity SerializedFile

A file like:

```text
globalgamemanagers.assets.split0
```

may report:

```text
Signature: UnitySerializedFile
SerializedFile version: 22
Unity version string: 2022.3.33f1
Serialized file size in header: 3.69 MB
Metadata size: 91.84 KB
Data offset: 94096
Header layout: SerializedFile v22+ 64-bit header
Note: header file size is larger than this split file
```

The note means the uploaded/visible file is only one split segment of the full serialized asset file.

## Common options

### `--recursive`

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive
```

### `--all`

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --all
```

### `--sha256`

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer\AssetBundle" --sha256
```

### `--extensions`

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --extensions .bundle .unity3d .obb .assets .split0
```

### `--out-dir`

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --out-dir "G:\Pico4\Reports"
```

## Limitations

This tool reads headers only. It does not decode Unity objects, meshes, textures, materials, or scripts.

For full inspection, open the file in UBE where supported.
