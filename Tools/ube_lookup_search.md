# ube_lookup_search.py

Search UBE lookup/index/cache/report files for a name, PathID, bundle name, or other text.

This tool is useful when you have a screenshot or note such as:

```text
head_00
PathID 4643
model_84_StrongBad-HomestarIAP
avatarsandputters_assets_all.bundle
```

but you no longer remember which bundle or project it came from.

## What it searches

The script searches these file types:

```text
.json
.jsonl
.txt
.tsv
.csv
.log
.db
.sqlite
.sqlite3
```

For SQLite databases, it scans all tables and stringifies each row for matching.

For JSON files, it tries a structured JSON walk first, then falls back to line search.

## Basic usage

Search a folder for an asset name:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00
```

Search by PathID:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" 4643
```

Search by object/model name:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" model_84_StrongBad-HomestarIAP
```

Search by bundle name:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" avatarsandputters_assets_all.bundle
```

Search a specific file:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE\.ube_pathid_index.json" head_00
```

## Output

Matches are printed to the console and also written to:

```text
ube_lookup_search_results.tsv
```

Each match includes:

- source file searched
- where the match was found, such as a line number, JSON path, or SQLite table row
- a short match snippet

Example:

```text
1. G:\Pico4\WalkAboutMiniGolf\UBE\.ube_pathid_index.json
   $.bundles[12].objects[430]
   name=head_00; unity_type=GameObject; path_id=4643; bundle=avatarsandputters_assets_all.bundle
```

## Common options

### `--mode any`

Match if any search term appears.

This is the default.

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00 4643 --mode any
```

### `--mode all`

Match only when all search terms appear in the same searchable record/line/row.

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00 4643 --mode all
```

### `--no-recursive`

Only search the top folder level.

The script is recursive by default.

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00 --no-recursive
```

### `--max-per-file`

Limit matches per searched file.

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00 --max-per-file 10
```

### `--out`

Choose a custom TSV output path.

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00 --out "G:\Pico4\Reports\lookup_results.tsv"
```

## Good search terms

When looking for a forgotten asset, try any of these:

```text
asset name
GameObject name
Mesh name
Material name
Texture name
PathID
bundle filename
owning GameObject
parent object name
Unity type, such as Texture2D, MeshRenderer, AnimationClip
```

Examples:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" Nautilus_CombinedAssets
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" MeshRenderer_-9221883136110663692
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" 7271676646510737621
```

## Why this is useful

UBE browsing often involves jumping between:

```text
GameObject
Transform
MeshFilter
MeshRenderer
Material
Texture
MonoBehaviour
external bundle references
```

If you take a screenshot and later forget where it came from, this script can search the generated lookup/cache/report data and help you find the original bundle/object again.

## Limitations

This tool only searches files that already exist on disk. It does not open Unity bundles directly and does not build new indexes by itself.

For a live GUI search inside the currently opened project, use UBE's built-in Project Search / PathID Lookup feature.
