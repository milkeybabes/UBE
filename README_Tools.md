# Unity Bundle Explorer — Companion Utilities ( Tools Folder )

These command-line utilities extend **Unity Bundle Explorer (UBE)** before, during, and after the main inspection workflow.

UBE provides the visual environment for opening Unity bundles, browsing assets, previewing textures, meshes, audio and animations, and exporting selected content. The companion utilities handle the surrounding jobs that are often needed when working with real game data:

- finding Unity bundles inside Android APK and OBB archives;
- identifying Unity versions and file types;
- comparing bundles from different game versions;
- rediscovering an asset from a name, PathID, screenshot or old note;
- validating UBE OBJ and GLB exports;
- correcting the position and orientation of exported GLB models for viewing, rendering or video.

These tools are intentionally separate from the UBE interface. They can be used independently, included in batch workflows, or kept beside the main UBE installation.

---

## Utilities at a glance

| Utility | Main purpose |
|---|---|
| `huntunity.py` | Find and extract UnityFS bundles from Android `.apk` and `.obb` archives. |
| `unity_bundle_header_scan.py` | Quickly identify Unity bundle signatures, versions and header information. |
| `unity_bundle_audit.py` | Produce a deeper UnityFS audit and compare bundles from different folders or releases. |
| `ube_lookup_search.py` | Search UBE indexes, caches, reports and databases for asset names, PathIDs or bundle names. |
| `ube_export_validator.py` | Check exported OBJ/MTL/texture sets and GLB files for structural problems. |
| `glb_presentation_corrector.py` | Re-centre, ground and rotate GLB exports without changing their original geometry or animation tracks. |

---

## Recommended workflow

A typical investigation can use the utilities in this order:

1. **Extract bundles** from APK or OBB archives with `huntunity.py`.
2. **Identify Unity versions and file types** with `unity_bundle_header_scan.py`.
3. **Audit or compare bundle releases** with `unity_bundle_audit.py`.
4. **Open and inspect the bundles in UBE.**
5. **Rediscover a previously seen asset** with `ube_lookup_search.py`.
6. **Validate exported models** with `ube_export_validator.py`.
7. **Prepare GLB files for presentation** with `glb_presentation_corrector.py`.

Not every investigation needs every step. Each utility is useful on its own.

---

## Requirements

- Python **3.10 or newer**
- No Unity installation is required
- Most utilities use only the Python standard library

The deeper UnityFS audit can optionally decode LZ4-compressed directory information. Install the `lz4` package when required:

```bat
python -m pip install lz4
```

Display the built-in help for any utility with:

```bat
python utility_name.py --help
```

The examples below use Windows paths, but the scripts also work with normal macOS and Linux paths.

---

# 1. Extract Unity bundles from APK and OBB archives

## `huntunity.py`

`huntunity.py` recursively scans a source folder for Android `.apk` and `.obb` archives. It looks inside each archive for genuine UnityFS files and extracts them as normal `.bundle` files that can be opened in UBE.

The expected primary Unity player bundle is:

```text
assets/bin/Data/data.unity3d
```

That file is renamed using the cleaned archive name. Additional UnityFS files are also extracted unless `--primary-only` is used.

## Basic usage

```bat
python huntunity.py "G:\Pico4\OVRports" "G:\Pico4\Unity Bundles"
```

## Extract only the primary `data.unity3d`

```bat
python huntunity.py "G:\Pico4\OVRports" "G:\Pico4\Unity Bundles" --primary-only
```

## Overwrite files from a previous extraction

```bat
python huntunity.py "G:\Pico4\OVRports" "G:\Pico4\Unity Bundles" --overwrite
```

## Put primary bundles directly in the destination folder

```bat
python huntunity.py "G:\Pico4\OVRports" "G:\Pico4\Unity Bundles" --flat
```

## Show additional scan information

```bat
python huntunity.py "G:\Pico4\OVRports" "G:\Pico4\Unity Bundles" --verbose
```

## Typical output layout

For an archive named:

```text
main.12345.com.company.game.obb
```

the normal output is similar to:

```text
Unity Bundles
└── com.company.game
    ├── com.company.game.bundle
    └── extra_bundles
        └── assets
            └── additional_file.bundle
```

The utility cleans Android expansion-file names, creates Windows-safe paths, prevents archive path traversal, writes files atomically, and does not overwrite existing output unless requested.

### Useful options

| Option | Effect |
|---|---|
| `--primary-only` | Extract only `assets/bin/Data/data.unity3d`. |
| `--overwrite` | Replace existing extracted files. |
| `--flat` | Place each primary bundle directly in the destination root. |
| `--verbose` | Show additional archive entries and decisions. |
| `--include-non-unity-primary` | Extract the primary path even when it does not begin with `UnityFS`. |

Use `--include-non-unity-primary` only when you deliberately want the expected primary file regardless of its signature.

---

# 2. Identify Unity files and engine versions

## `unity_bundle_header_scan.py`

This is the fast first-pass scanner. It reads file headers and answers questions such as:

- Is this a UnityFS, UnityWeb or UnityRaw container?
- Which Unity version or revision is written in the header?
- What bundle format and size information is present?
- Is the file actually an FSB5 bank, ZIP archive, OGG, WAV or FLAC file?
- Are two files byte-identical when SHA256 calculation is enabled?

It writes both a spreadsheet-friendly TSV report and a readable TXT summary.

## Scan one folder

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer\AssetBundle"
```

## Scan all subfolders

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive
```

## Scan every file regardless of extension

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --all
```

## Include SHA256 hashes

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --sha256
```

SHA256 is useful for proving whether two files are exactly identical, but it is slower on large folders.

## Choose file extensions

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive ^
  --extensions .bundle .unity3d .obb .assets .resource .resS
```

## Write reports to another folder

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive ^
  --out-dir "G:\Pico4\Reports"
```

## Output files

Each run creates timestamped reports:

```text
unity_header_scan_YYYYMMDD_HHMMSS.tsv
unity_header_scan_YYYYMMDD_HHMMSS.txt
```

The TSV contains one row per file. The TXT report includes a summary, Unity-version counts and readable details for every scanned file.

### Best use

Use the header scanner when you have a mixed folder and first need to establish **what each file is**. Use the deeper audit below when you already know that the inputs are UnityFS bundles and want internal directory and comparison information.

---

# 3. Audit and compare UnityFS bundles

## `unity_bundle_audit.py`

This utility performs a deeper inspection of UnityFS `.bundle` files.

For each bundle it records information including:

- file size and SHA256;
- Unity version and revision;
- bundle format;
- UnityFS compression flags;
- compressed and uncompressed directory sizes;
- block and node counts;
- contained `.assets`, `.resS` and `.resource` nodes;
- basic binary string hits related to textures, shaders and materials.

The string search is intended for quick triage. It is not a replacement for UBE's proper asset inspection.

## Audit a wildcard group

```bat
python unity_bundle_audit.py "G:\Pico4\Bundles\*.bundle" ^
  --csv "G:\Pico4\Reports\bundle_audit.csv"
```

## Audit a complete folder

```bat
python unity_bundle_audit.py "G:\Pico4\Bundles" ^
  --csv "G:\Pico4\Reports\bundle_audit.csv"
```

Folders are searched recursively for `.bundle` files.

## Compare two game versions

```bat
python unity_bundle_audit.py ^
  "G:\Pico4\Walkabout\v6.5" ^
  "G:\Pico4\Walkabout\v6.6" ^
  --csv "G:\Pico4\Reports\v65_vs_v66.csv" ^
  --compare
```

`--compare` groups files with the same filename and shows whether their sizes and hashes are the same or different.

## Default output

Without a custom filename, the report is written as:

```text
unity_bundle_report.csv
```

A compact table is also printed to the console.

### Optional LZ4 support

Some UnityFS bundles store their directory information using LZ4 or LZ4HC. Install the optional package when the audit reports that it is required:

```bat
python -m pip install lz4
```

### Best use

This tool is particularly helpful when comparing an older working game release against a newer release and trying to identify:

- changed bundle files;
- changed Unity revisions;
- different resource-stream sizes;
- changes in texture, shader or material-related strings;
- bundles that are identical despite having come from separate installations.

---

# 4. Rediscover assets from names, PathIDs or notes

## `ube_lookup_search.py`

UBE investigations often produce screenshots, notes or comments containing only part of the original context:

```text
head_00
PathID 4643
model_84_StrongBad-HomestarIAP
avatarsandputters_assets_all.bundle
```

`ube_lookup_search.py` searches UBE lookup files, caches, reports and databases to help find the original bundle or object again.

## What it searches

Text and structured files:

```text
.json
.jsonl
.txt
.tsv
.csv
.log
```

SQLite files:

```text
.db
.sqlite
.sqlite3
```

JSON is searched structurally when possible. SQLite databases are opened read-only and searched table by table.

## Search by asset name

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00
```

## Search by PathID

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" 4643
```

PathIDs may be positive or negative and can be searched as ordinary text.

## Search by bundle name

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" ^
  avatarsandputters_assets_all.bundle
```

## Require several terms in the same record

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" ^
  head_00 4643 --mode all
```

The default `--mode any` returns a match when any supplied term appears. `--mode all` is useful for narrowing common names.

## Limit results per file

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" ^
  head --max-per-file 10
```

## Search only the top folder

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" ^
  head_00 --no-recursive
```

## Choose the report path

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" ^
  head_00 --out "G:\Pico4\Reports\head_lookup.tsv"
```

## Output

Matches are printed to the console and written by default to:

```text
ube_lookup_search_results.tsv
```

Each match records:

- the source file;
- the line number, JSON path or SQLite table row;
- a short matching snippet.

### Good search terms

Useful search terms include:

- asset or GameObject name;
- mesh, material or texture name;
- PathID;
- bundle filename;
- owning or parent GameObject;
- component name;
- Unity type such as `Texture2D`, `MeshRenderer` or `AnimationClip`.

---

# 5. Validate UBE model exports

## `ube_export_validator.py`

This utility checks UBE exports before they are archived, shared, imported into another program or used in an automated pipeline.

It supports:

- OBJ files and their related MTL and texture files;
- binary glTF 2.0 `.glb` files;
- folders containing OBJ and GLB files.

## Validate one OBJ export

```bat
python ube_export_validator.py "G:\UBE Exports\Model.obj"
```

## Validate one GLB export

```bat
python ube_export_validator.py "G:\UBE Exports\Model.glb"
```

## Validate a complete folder

```bat
python ube_export_validator.py "G:\UBE Exports"
```

## Include all subfolders

```bat
python ube_export_validator.py "G:\UBE Exports" --recursive
```

## Write a machine-readable JSON report

```bat
python ube_export_validator.py "G:\UBE Exports" --recursive ^
  --json "G:\UBE Exports\validation_report.json"
```

## OBJ checks

The validator checks items including:

- vertex, normal, UV and face counts;
- position, UV and normal indices;
- faces with fewer than three vertices;
- degenerate faces;
- referenced MTL files;
- `usemtl` names against defined materials;
- texture files referenced by MTL statements.

## GLB checks

The validator checks items including:

- GLB magic, version and declared file length;
- JSON and BIN chunk structure;
- buffer and bufferView boundaries;
- accessor boundaries;
- index ranges against POSITION vertex counts;
- mesh, primitive, material, texture and image counts.

## Exit status

The utility returns a successful exit code when all checked files pass and a failure code when structural errors are found. This makes it useful in batch files and automated export checks.

### Important limitation

Passing validation means that the file is structurally consistent according to the checks performed. It does not guarantee that the model is visually correct, uses the intended Unity shader appearance, or will look identical in every external viewer.

---

# 6. Prepare GLB exports for viewing, rendering or video

## `glb_presentation_corrector.py`

Unity assets can be technically correct but inconvenient to present because they are:

- far from the world origin;
- below or above the ground plane;
- facing the wrong direction;
- centred around a distant rig origin;
- animated across a large world-space travel area.

The GLB Presentation Corrector adds a presentation transform while preserving the original meshes, materials, skins and animation tracks.

It supports ordinary rigid scenes and skinned GLBs. Skinned mesh nodes remain valid scene roots while the correction is applied through their joint hierarchy.

No third-party Python packages are required.

## Default operation

```bat
python glb_presentation_corrector.py "G:\UBE Exports\Model.glb"
```

By default, the utility:

- centres the visible model on the X and Z axes;
- places its lowest visible point on `Y=0`;
- uses the first frame of animation 0 when animation exists;
- writes `Model_presented.glb`;
- leaves the original file unchanged.

## Turn a model around

```bat
python glb_presentation_corrector.py "Model.glb" --rotate-y 180
```

Other useful rotations include `90`, `-90` and `270`.

## Centre on all three axes without grounding

```bat
python glb_presentation_corrector.py "Model.glb" ^
  --center xyz --no-ground
```

## Use the complete animation travel area

```bat
python glb_presentation_corrector.py "Model.glb" ^
  --bounds animation --samples 120
```

This is useful for an animated object that moves around the scene rather than remaining near its first-frame position.

## Select a different animation

```bat
python glb_presentation_corrector.py "Model.glb" ^
  --bounds animation --animation-index 1
```

## Increase skinned-vertex sampling

```bat
python glb_presentation_corrector.py "Model.glb" ^
  --bounds animation --max-skin-vertices 25000
```

Use `--max-skin-vertices 0` to evaluate every vertex at every sampled animation pose. This can be considerably slower on dense models.

First-frame and rest-pose bounds evaluate all skinned vertices.

## Process a folder

```bat
python glb_presentation_corrector.py "G:\UBE Exports" --recursive
```

## Write corrected files to another folder

```bat
python glb_presentation_corrector.py "G:\UBE Exports" --recursive ^
  --output-dir "G:\Corrected GLB"
```

## Choose an exact output filename

```bat
python glb_presentation_corrector.py "Model.glb" ^
  --output "Model_For_Video.glb"
```

`--output` is available only when processing one input GLB.

## Preview the correction without writing

```bat
python glb_presentation_corrector.py "Model.glb" --dry-run
```

The dry run prints the calculated bounds, rotation and translation but does not create a file.

## Overwrite the source

```bat
python glb_presentation_corrector.py "Model.glb" --overwrite
```

Overwriting is deliberately not the default and is generally not recommended.

### Bounds modes

| Mode | Meaning |
|---|---|
| `--bounds rest` | Use the authored rest pose. |
| `--bounds first` | Use the first frame of the selected animation; this is the default. |
| `--bounds animation` | Sample the complete animation travel area. |

### Limitations

- Supports GLB 2.0 with an embedded primary buffer.
- External `.gltf` buffers are not supported.
- Sparse accessors are not supported.
- Node translation, rotation and scale animation is evaluated.
- Morph-target deformation is not included in presentation bounds.
- Full-animation bounds may use vertex sampling for performance.
- An unsafe or malformed pre-existing skinned hierarchy is rejected rather than rewritten blindly.

---

# Troubleshooting

## Python reports a `unicodeescape` error

A Windows path inside Python source code must be raw, escaped, or written with forward slashes:

```python
path = r"G:\Pico4\WalkAboutMiniGolf\UBE"
```

```python
path = "G:\\Pico4\\WalkAboutMiniGolf\\UBE"
```

```python
path = "G:/Pico4/WalkAboutMiniGolf/UBE"
```

Normal quoted Windows paths entered at the Command Prompt do not need to be changed:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00
```

## The header scanner reports no matching files

Try scanning recursively and ignoring the extension filter:

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --all
```

## Lookup search returns too many matches

Use a second identifying term together with `--mode all`:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" ^
  head_00 4643 --mode all
```

## Lookup search returns nothing

Try a broader fragment of the name, the PathID by itself, or the bundle name:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" 4643
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" avatarsandputters
```

Make sure the selected search root actually contains the UBE cache, JSON, TSV, log or database files.

## The bundle audit requests LZ4

Install the optional package:

```bat
python -m pip install lz4
```

## A GLB passes validation but looks misplaced

Validation checks structure, not presentation. Run:

```bat
python glb_presentation_corrector.py "Model.glb"
```

For an animated model with significant world movement:

```bat
python glb_presentation_corrector.py "Model.glb" ^
  --bounds animation --samples 120
```

---

# Relationship to Unity Bundle Explorer

These utilities are designed to increase the practical value of UBE without overloading the main interface.

They cover the repetitive jobs around the application:

- **before UBE:** locate, extract, identify and compare bundles;
- **during investigation:** rediscover assets and connect old notes to their source;
- **after export:** validate files and prepare models for external viewing or presentation.

Together, UBE and its companion utilities form a broader toolkit for investigating Unity game data rather than only a single bundle viewer.

---

## Responsible use

Use these utilities only with files that you own or have permission to inspect. Game assets and other extracted content may remain protected by copyright, licence agreements or other restrictions.
