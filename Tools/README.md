# UBE Companion Utilities v1

The **UBE Companion Utilities Launcher** is an optional, lean graphical front end for the standalone Unity Bundle Explorer utilities.

Nothing has been removed from the command-line workflow. Every utility remains a normal independent Python script. The launcher simply lets less command-line-oriented users select a tool, read a short explanation, choose files and folders, run it, and watch the real output in one window.

## Start the launcher

### Windows

Double-click:

```text
Launch UBE Utilities.bat
```

Or run it directly with Python:

```bat
python ube_utilities_gui.py
```

### macOS

Double-click:

```text
Launch UBE Utilities.command
```

The first time macOS encounters a downloaded script, you may need to **right-click it and choose Open**.

If the executable permission was removed while copying or extracting the file, open Terminal in the utility folder and run:

```bash
chmod +x "Launch UBE Utilities.command"
./Launch\ UBE\ Utilities.command
```

You can always bypass the launcher script and start the GUI directly:

```bash
python3 ube_utilities_gui.py
```

The `.command` file checks common Apple Silicon and Intel Python locations, a local virtual environment, and the normal command path.

### Linux and other systems

Run:

```bash
python3 ube_utilities_gui.py
```

## Launcher layout

- **Utility list:** choose the required tool.
- **Help paragraph:** explains what the selected utility does.
- **Settings:** only the relevant paths and options are shown.
- **Advanced options:** hidden until requested.
- **Dependency status:** shows UnityPy, optional LZ4, or Blender readiness.
- **Command preview:** displays the exact command that will run.
- **Run / Cancel:** the GUI remains responsive while the utility works.
- **Output panel:** shows the utility's live console results.
- **Open Output Folder:** opens the expected destination.
- **Remembered settings:** last-used paths and options are restored next time.

The launcher itself uses only Python's standard library, including Tkinter.

On macOS, a Python installation without Tk support may report:

```text
ModuleNotFoundError: No module named 'tkinter'
```

In that case, use a Python installation that includes Tk/Tcl support. The individual utilities still retain their own optional requirements, such as UnityPy, LZ4 or Blender.

## Included utilities

| Utility | Purpose |
|---|---|
| `huntunity.py` | Extract UnityFS bundles from Android APK and OBB archives. |
| `unity_bundle_header_scan.py` | Identify Unity signatures, versions and header details. |
| `unity_bundle_audit.py` | Deep-audit and compare UnityFS bundles. |
| `unity_bundle_texture_extractor.py` | Batch-export Texture2D images as PNG. |
| `ube_lookup_search.py` | Find assets by name, PathID, bundle or other remembered text. |
| `ube_export_validator.py` | Validate UBE OBJ/MTL/texture and GLB exports. |
| `glb_presentation_corrector.py` | Centre, ground and rotate GLBs for presentation. |
| `glb_thumbnail_batch.py` | Render batch GLB thumbnails through Blender. |

---

# 1. Extract Android bundles

```bat
python huntunity.py "G:\Android Games" "G:\Unity Bundles"
```

Useful options:

```bat
python huntunity.py "G:\Android Games" "G:\Unity Bundles" --primary-only
python huntunity.py "G:\Android Games" "G:\Unity Bundles" --overwrite
python huntunity.py "G:\Android Games" "G:\Unity Bundles" --flat
```

---

# 2. Scan Unity headers

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive
```

With hashes:

```bat
python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --sha256
```

Output:

```text
unity_header_scan_YYYYMMDD_HHMMSS.tsv
unity_header_scan_YYYYMMDD_HHMMSS.txt
```

---

# 3. Audit and compare bundles

```bat
python unity_bundle_audit.py "G:\Bundles\*.bundle" --csv report.csv
```

Compare two releases:

```bat
python unity_bundle_audit.py "G:\Game\v6.5" "G:\Game\v6.6" ^
  --csv v65_vs_v66.csv --compare
```

LZ4 directory decoding is optional:

```bat
python -m pip install lz4
```

---

# 4. Batch-extract textures

```bat
python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages"
```

Choose an output folder:

```bat
python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages" ^
  --out "G:\Pico4\Extracted Course Images"
```

Useful options:

```bat
python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages" --overwrite
python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages" --dry-run
python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages" --include-sprites
```

The real Walkabout Mini Golf batch exported **147 easy and hard course images** in one run.

Requirement:

```bat
python -m pip install UnityPy
```

---

# 5. Search UBE lookup data

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" head_00
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" 4643
```

Require all terms in one record:

```bat
python ube_lookup_search.py "G:\Pico4\WalkAboutMiniGolf\UBE" ^
  head_00 4643 --mode all
```

---

# 6. Validate UBE exports

```bat
python ube_export_validator.py "G:\UBE Exports\Model.obj"
python ube_export_validator.py "G:\UBE Exports\Model.glb"
python ube_export_validator.py "G:\UBE Exports" --recursive
```

Write JSON:

```bat
python ube_export_validator.py "G:\UBE Exports" --recursive ^
  --json validation_report.json
```

---

# 7. Correct GLB presentation

```bat
python glb_presentation_corrector.py "Model.glb"
```

Rotate and centre:

```bat
python glb_presentation_corrector.py "Model.glb" --rotate-y 180
```

Use the complete animation travel area:

```bat
python glb_presentation_corrector.py "Model.glb" ^
  --bounds animation --samples 120
```

The original GLB is not overwritten unless the command-line `--overwrite` option is explicitly used.

---

# 8. Render GLB thumbnails

```bat
python glb_thumbnail_batch.py "G:\GLB Exports" --recursive
```

Write thumbnails beside the GLBs:

```bat
python glb_thumbnail_batch.py "G:\GLB Exports" ^
  --same-folder --overwrite
```

Choose view and size:

```bat
python glb_thumbnail_batch.py "Model.glb" ^
  --view front --size 1024
```

The renderer uses model-scale-corrected lighting so tiny objects such as golf balls are not washed out.

Blender must be installed, in PATH, or selected in the launcher's Advanced options.

---

# Troubleshooting

## UnityPy is missing

```bat
python -m pip install UnityPy
```

## LZ4 audit support is missing

```bat
python -m pip install lz4
```

The bundle audit can still run without LZ4, but it cannot decode LZ4-compressed directory information.

## Blender is not found

Install Blender or select its executable in the GLB Thumbnail Renderer's Advanced options.

Typical locations include:

```text
Windows: C:\Program Files\Blender Foundation\Blender <version>\blender.exe
macOS:   /Applications/Blender.app/Contents/MacOS/Blender
```

The current launcher automatically checks the usual Windows installations. On macOS, select the executable through **Show advanced options** when Blender is not already available through the command path.

## A Windows path causes a Python `unicodeescape` error

Inside Python source code, use a raw string:

```python
path = r"G:\Pico4\WalkAboutMiniGolf\UBE"
```

Normal quoted paths entered in Command Prompt or selected through the launcher do not require changes.

---

## Responsible use

Use these utilities only with files that you own or have permission to inspect. Extracted game assets may remain subject to copyright, licences and other restrictions.
