# Unity Bundle Explorer (UBE)

**Current version:** v2.4h — Build 348  
**Application:** Unity Bundle Explorer  
**Status:** Active research and inspection tool

Unity Bundle Explorer is a desktop application for examining Unity bundles and serialized asset files. It combines a searchable asset tree, relationship-aware inspectors, OpenGL previews, animation playback, material and texture recovery, audio inspection, and practical export tools.

UBE is designed for investigation rather than blind extraction. Its main goal is to explain how Unity assets are connected and to preview them as faithfully as the available serialized data allows.

> UBE is read-only with respect to the original Unity files. Comments are stored separately and exports are written as new files.

---

## Contents

- [Why UBE exists](#why-ube-exists)
- [Highlights](#highlights)
- [Requirements](#requirements)
- [Installation](#installation)
- [Running UBE](#running-ube)
- [Opening Unity data](#opening-unity-data)
- [Main features](#main-features)
- [Animation support](#animation-support)
- [Material and texture recovery](#material-and-texture-recovery)
- [Export support](#export-support)
- [Audio preview](#audio-preview)
- [3D preview controls](#3d-preview-controls)
- [External comments and reports](#external-comments-and-reports)
- [Known limitations](#known-limitations)
- [Performance notes](#performance-notes)
- [Reporting a problem](#reporting-a-problem)
- [Project history](#project-history)
- [Legal and responsible use](#legal-and-responsible-use)
- [Acknowledgements](#acknowledgements)

---

## Why UBE exists

UBE began as a diagnostic tool while investigating a device-specific texture problem in **Walkabout Mini Golf** on a Pico 4 Pro headset. Some assets appeared with missing, incorrect or garbled materials on that device even though the same content rendered correctly elsewhere.

The original aim was to answer a simple question:

> Is the source asset damaged, or is the problem occurring later in the device, shader, driver or SDK rendering path?

That investigation required more than a normal asset extractor. It required a tool that could follow Path IDs, reconstruct GameObject hierarchies, resolve external materials and textures, inspect unusual UV layouts, preview animations, compare static and runtime variants, and show why a particular appearance had been selected.

The project gradually became a general-purpose Unity asset investigation tool. It has since been tested extensively across more than 30 Walkabout Mini Golf courses and against unrelated Unity content, including Angry Birds assets.

UBE does not include any game files and is not intended to replace Unity or run the original game logic.

---

## Highlights

- Open UnityFS bundles and Unity serialized asset files.
- Scan a folder or project so external CAB, material, texture and audio references can be resolved.
- Browse assets by type, name, Path ID and relationship.
- Search across the loaded project and jump directly to Path IDs.
- Inspect GameObjects, components, meshes, materials, textures, sprites, animations, audio, cameras, lights, colliders, particles, UI assets and more.
- Preview static meshes, object assemblies and compatible animations in OpenGL.
- Reconstruct transform hierarchies and renderer context.
- Preview rigid, skinned and mixed rigid-plus-skinned animations.
- Recover colours from external, stripped, textureless or null runtime material references when the bundle contains decisive supporting evidence.
- Inspect UV0, UV1, UV2, UV3, vertex colours, normals, tangents and other mesh channels.
- Export textures, sprites, meshes, object assemblies, audio and readable inspector reports.
- Export compatible AnimationClips as self-contained animated GLB files.
- Store research notes externally without modifying the Unity data.

---

## Requirements

### Software

- **Python 3.10 or newer**
- Python 3.12 is the primary tested version.
- A working OpenGL graphics driver.
- Windows 11 is the primary development and test platform.
- macOS has also been used successfully.
- Linux may work through the same Python dependencies, but it is not currently a regularly tested target.

### Python packages

The supplied `requirements.txt` installs:

- UnityPy
- Pillow
- lz4
- PyOpenGL
- PySide6
- pygltflib
- NumPy

### Optional audio decoder

`vgmstream-cli` is optional. UBE works without it, but FMOD FSB5 audio cannot be decoded to WAV for preview or conversion until vgmstream is installed.

See [Audio preview](#audio-preview).

---

## Installation

### 1. Download or clone the repository

```bash
git clone <your-repository-url>
cd <repository-folder>
```

A GitHub ZIP download is also fine. Extract the complete repository before running UBE.

### 2. Create a virtual environment

#### Windows

```bat
python -m venv .venv
.venv\Scripts\activate
```

#### macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Upgrade pip and install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Start UBE

```bash
python -m unity_bundle_explorer
```

On Windows, where several Python installations exist, use the full interpreter path when necessary:

```bat
C:\Python312\python.exe -m unity_bundle_explorer
```

---

## Running UBE

The main entry point is:

```bash
python -m unity_bundle_explorer
```

UBE opens as a PySide6 desktop application. No Unity installation is required.

A typical workflow is:

1. Open a bundle, serialized asset file or project folder.
2. Search or browse the asset tree.
3. Select an asset to view its inspector and preview.
4. Follow clickable Path ID, component, owner, material and texture links.
5. Use the 3D and UV controls to investigate the asset.
6. Export the selected asset, a branch, filtered results or an inspector report.
7. Add an external comment when a discovery should be recorded.

---

## Opening Unity data

The **File** menu provides several opening modes.

### Open Bundle

Use **File → Open Bundle...** for UnityFS bundle files, including files commonly named with `.bundle`, `.unity3d` or no helpful extension.

### Open Unity Serialized Assets

Use **File → Open Unity Serialized Assets...** for files such as:

- `sharedassets*.assets`
- `resources.assets`
- `data.unity3d`
- other Unity serialized files supported by UnityPy

### Open Serialized Assets Folder

Use this when a Unity title stores several related `.assets`, `.resource` or `.resS` files together.

### Open Folder / Project

This is the preferred mode when assets reference other bundles or serialized files. UBE builds a project-level reference and Path ID index so it can resolve external materials, textures, audio resources and related objects.

Keep sibling dependency files together whenever possible. For example:

```text
GameData/
├── data.unity3d
├── sharedassets0.assets
├── sharedassets0.assets.resS
├── sharedassets1.assets
└── sharedassets1.resource
```

Do not open a `.resource` or `.resS` file directly. Open its associated serialized asset file and let UBE read the external resource automatically.

---

## Main features

### Asset tree and navigation

- Assets grouped by Unity type.
- Optional Kind, Path ID and comment-preview columns.
- Back and forward selection history.
- Recent-file list.
- Clickable component, owner, material, texture and Path ID relationships.
- Project-wide search and Path ID lookup.
- Branch-scoped and filtered operations.
- Return-to-source-list navigation after opening a referenced external file.
- Session selection history with TSV export.
- Inspector coverage report showing specialised, basic and raw asset support.

### Relationship-aware inspection

UBE does not treat every object as an isolated file. It follows relationships such as:

```text
GameObject
├── Transform
├── MeshFilter
│   └── Mesh
└── MeshRenderer
    └── Material
        └── Texture2D
```

It also follows:

- AnimationClip to Animation or Animator owner.
- Renderer to material slots.
- Material to shader properties and texture references.
- Mesh to the GameObjects and renderers that use it.
- AudioSource to AudioClip and mixer group.
- SpriteRenderer to Sprite and texture.
- External FileID and PathID references.
- Reverse “used by” relationships.

### Specialised inspectors

UBE includes dedicated or enhanced inspection for many Unity types, including:

- AudioClip, AudioSource and audio mixer assets
- Animation, AnimationClip, Animator and animator controllers
- Avatar
- Cameras and lights
- Colliders and Rigidbody
- Cubemap and Texture2DArray
- Fonts and TMP font assets
- GameObject and Transform
- LODGroup
- Material and Shader
- Mesh, MeshFilter, MeshRenderer and SkinnedMeshRenderer
- MonoBehaviour and MonoScript relationships
- NavMesh assets and settings
- ParticleSystem and ParticleSystemRenderer
- PlayableDirector
- ReflectionProbe and light-probe/lightmap settings
- Sprite, SpriteRenderer and SpriteMask
- TextAsset and Texture2D
- UI assets including Canvas and RectTransform
- LineRenderer and TrailRenderer

Unknown or unsupported types remain visible through a generic readable-field fallback when UnityPy exposes their serialized data.

---

## 3D and image previews

UBE provides several preview modes rather than one generic viewer.

### Mesh and object preview

- Static Mesh preview.
- MeshFilter preview with sibling renderer and material context.
- GameObject and transform-group assembly preview.
- SkinnedMeshRenderer preview.
- Multiple selected meshes as a temporary combined view.
- Child debug colours or recovered real materials.
- Per-child visibility, isolation and origin markers.
- Ground/up-axis selection shared by preview and export.

### Texture and UV inspection

- Texture2D image preview.
- Sprite crop and SpriteMask preview.
- Cubemap and texture-array inspection.
- Zoom and pan.
- UV0, UV1, UV2 and UV3 inspection where available.
- Atlas rectangle and repeated-swatch analysis.
- Clamp/repeat and UV-domain diagnostics.
- Base, normal, emission and metal texture cycling.
- Normal-map alignment and green-channel checks.
- Material tint and neutral-material comparison.

### Symbolic and diagnostic previews

Some Unity assets are better explained symbolically than rendered literally. UBE includes diagnostic previews for cameras, lights, colliders, reflection probes, LOD groups, particle emitters, RectTransforms, shader intent, avatars, navmesh and helper geometry.

---

## Animation support

Animation is one of UBE's major investigation features.

### Preview support

UBE can preview many combinations of:

- Legacy `Animation` ownership.
- `Animator` and controller relationships.
- Transform/object animation.
- Skinned mesh animation.
- Mixed skinned and rigid animated objects.
- Streamed and dense curve storage.
- Position, rotation and scale curves.
- CPU skinning using bind poses, joint indices and weights.
- Rigid single-bone index-only skinning.
- Frame-accurate authored sampling.
- Root-motion and world-travel animation.
- Numbered or mutually exclusive runtime renderer variants.

The inspector reports duration, sample rate, target paths, curve channels, exposed keyframe counts, likely motion style, owner-resolution method, busiest paths and export eligibility.

### Playback controls

The animation toolbar provides:

- Play/Pause
- Reset pose
- Loop
- In-place mode
- Playback speed
- Duration limit for long clips
- Full-duration restoration
- Time and authored-frame counter
- Animated GLB export when supported

`Space` toggles animation play/pause while the preview is active and no text field is being edited.

### In-place playback

In-place mode can hold the detected travel controller at its authored first rendered pose while preserving internal movement. This is useful for animals, vehicles and characters that travel around a large scene but contain a short reusable local action.

The duration limit can reduce a very long world-movement clip to its useful opening section without changing the original AnimationClip.

### Viewport visibility selection

For large animations containing several distant objects:

- **Shift + left-drag** draws a box and isolates render elements touched by it.
- **Ctrl + left-drag** draws a box and hides render elements touched by it.
- **Shift + I** or **Shift + V** restores all render elements.

Playback and Animated GLB export use the same visible renderer set.

### Animated GLB export

The **Export GLB** button appears only when UBE has enough trustworthy data to reproduce the preview as glTF.

Compatible exports may include rigid transform animation, skinned mesh animation, mixed rigid and skinned renderers, joints, inverse bind matrices, indices and weights, source-rate TRS tracks, embedded textures, current visibility state, in-place correction and duration limits.

UBE deliberately refuses Animated GLB export when required transform paths, skin data, constraints or matrices cannot be represented safely. A working preview does not always guarantee a portable glTF representation.

---

## Material and texture recovery

Unity games often contain runtime-oriented material layouts that are difficult to understand outside the original engine. UBE uses conservative, relationship-based recovery rather than selecting the first similarly named texture.

Its decision process can consider:

- The exact MeshFilter and MeshRenderer using a Mesh.
- Renderer material-slot order.
- Recognised base-colour shader properties.
- External FileID and PathID references.
- Local material-family relationships.
- Static and runtime mesh-name families.
- Palette and swatch UV patterns.
- UV0 versus UV1 evidence.
- Course-level agreement between colour materials.
- Stripped, textureless or explicit-null material references.

Recognised base-colour properties include:

- `_BaseMap`
- `_BaseTexture`
- `_ColorMap` / `_ColourMap`
- `_BaseColorMap`
- `_MainTex` / `_MainTexture`
- `_Albedo`
- `_BaseTex`
- `_BaseMap1`

Auxiliary textures such as normal maps, noise fields, masks, emission maps and wind-deformation inputs do not outrank a genuine base-colour assignment.

Recovery is intentionally evidence-based. Existing complete materials remain authoritative, and ambiguous cases fall back rather than silently inventing an appearance.

### What UBE does not reproduce

UBE is not a full shader runtime. A custom shader may animate grass, water, foliage or particles using time, vertex colours, extra UV channels and noise textures. UBE can inspect that evidence and recover the base appearance, but it does not automatically recreate every custom GPU deformation or lighting equation.

---

## Export support

Use **Export Selected Asset...** or the asset-tree context menu.

| Asset family | Export |
|---|---|
| Texture2D | PNG + JSON metadata |
| Sprite / SpriteRenderer | Cropped PNG + JSON metadata |
| Cubemap | PNG faces/contact sheet + JSON metadata |
| Texture2DArray | PNG slices + JSON metadata |
| Mesh / GameObject / assembly | OBJ + MTL + textures, or GLB |
| Compatible AnimationClip | Animated GLB |
| AudioClip | Original Unity container |
| AudioClip with vgmstream | Decoded WAV |
| Inspector content | Readable UTF-8 HTML |
| Search, history and coverage data | TSV |

UBE can export one asset, several selected assets, a branch, filtered results, a complete bundle, separate mesh/object files, or one combined authored-coordinate assembly.

Combined exports preserve authored/shared coordinates rather than individually centring every object.

### Coordinate basis

**View → Ground / Up Axis** controls the preview and OBJ/GLB export basis. UBE preserves original placement whenever possible because world coordinates are important when reconstructing an assembly or part of a level.

---

## Audio preview

UBE reads AudioClip metadata directly. Standard supported audio can be previewed through Qt multimedia. FMOD FSB5 data requires the optional `vgmstream-cli` decoder.

### Windows

1. Download the complete Windows vgmstream command-line package.
2. Keep `vgmstream-cli.exe` with all DLL files supplied in that package.
3. Place the folder at `Tools/vgmstream/`, or select the executable using **AudioClip preview → Locate vgmstream...**.

Do not copy only the EXE; its accompanying DLL files may be required.

### macOS

```bash
brew install vgmstream
which vgmstream-cli
```

Select the returned executable through **Locate vgmstream...** in UBE.

### Audio export behaviour

- Original export preserves the Unity/FSB/OGG/WAV container.
- WAV export decodes through vgmstream and does not alter the source.
- A single selected FSB5 bank exports the currently selected sample/subsong.
- Batch WAV export uses sample/subsong 1 from each AudioClip.
- External `.resource` and `.resS` files must remain beside the corresponding serialized asset file.

See `AUDIO_HELP.txt` for the full setup guide.

---

## 3D preview controls

Press **H** while the 3D preview is active to open the complete built-in help.

### Mouse

| Control | Action |
|---|---|
| Left-drag | Orbit |
| Shift + left-drag | Box-isolate touched renderers |
| Ctrl + left-drag | Box-hide touched renderers |
| Right-drag | Rotate around selected correction axis |
| Shift + right-drag | Rotate in 15° steps |
| Middle-drag | Pan |
| Mouse wheel | Zoom |
| Ctrl + wheel | Change field of view |

### Essential keys

| Key | Action |
|---|---|
| `0` | Isometric/reset view |
| `1`–`6` | Top, bottom, front, back, left and right views |
| `X`, `Y`, `Z` | Select right-drag rotation axis |
| `Q`, `E` | Roll around Z by -15° / +15° |
| `A` | Toggle XYZ indicator |
| `U` | Cycle UV channel |
| `M` | Toggle UV-domain/remap mode |
| `W` | Cycle texture wrap mode |
| `T` | Toggle texture tint/neutral material |
| `B` | Cycle base, normal, emission and metal textures |
| `N` | Show normal texture against UV0 |
| `L` | Toggle lit normal/bump preview |
| `G` | Flip normal-map green channel |
| `[` / `]` | Lower/raise bump strength |
| `P` | Toggle debug child colours / real materials |
| `V` | Cycle one hidden child |
| Shift + `V` | Restore all children and box filters |
| `I` | Solo/isolate one child |
| Shift + `I` | Restore all children and box filters |
| `O` | Toggle child origins |
| Shift + `O` | Toggle zero-offset origin diagnostics |
| `Space` | Play/pause active AnimationClip |
| `` ` `` / `~` / `F11` | Toggle preview focus |
| `H` | Open complete 3D help |

---

## External comments and reports

### Comments

UBE stores comments outside the original Unity data in:

```text
UBE_Comments/
```

Comment files are JSON and are associated with the source bundle plus Path ID. They can record names, discoveries, unresolved questions or export notes without modifying the bundle.

### Inspector reports

Inspector displays can be exported as readable UTF-8 HTML. Search results, selection history and inspector-coverage reports can also be exported as TSV.

This is useful for documenting Path IDs and relationships, preserving animation summaries, comparing Unity versions and reporting reproducible rendering problems.

---

## Known limitations

UBE is an inspector, not a complete Unity runtime.

### Runtime game logic

UBE does not execute MonoBehaviour code, gameplay scripts, procedural spawning, physics simulation, runtime material assignment code or game-specific state logic. An object driven only by the original game code may remain static or contain no previewable animation data.

### Shaders and visual effects

Custom shaders may use time-driven vertex deformation, wind/noise fields, water equations, GPU instancing, procedural colour, special transparency or particle simulation. UBE can explain many inputs but cannot reproduce every custom shader. Some previews therefore show recovered base colour rather than the exact final in-game result.

### Animation

- Some clips contain incomplete or unresolved binding paths.
- Some visible runtime motion is not stored in an AnimationClip.
- Constraints may require logic that cannot be reconstructed safely.
- CPU skinning can be expensive on very large characters or scenes.
- Animated GLB is offered only when the result can be represented safely.

### Unity formats and dependencies

Unity serialization changes over time. UnityPy provides broad support, but some Unity versions, custom compression, encryption or proprietary containers may not open correctly.

Materials, textures and audio may be stored in another bundle or resource file. Open the containing folder/project and keep dependencies together for best results.

---

## Performance notes

### CPU-heavy work

- Bundle parsing and decompression
- Path ID indexing
- External-reference resolution
- Animation-curve decoding
- Hierarchy reconstruction
- CPU skinning
- GLB/OBJ construction and export

### GPU/OpenGL work

- Viewport triangle drawing
- Texture display
- Depth testing
- Preview lighting
- Camera movement and final presentation

A faster external GPU can improve heavy OpenGL drawing, but long animation preparation may still be CPU-bound.

UBE displays coarse stage-based progress for large animation preparation and exports. It intentionally does not report every vertex or every frame.

---

## Reporting a problem

A useful issue report should include:

- UBE version and build number
- Operating system and Python version
- Source file type
- Asset name and Unity asset type
- Path ID
- Inspector report or copied inspector text
- Screenshot of the preview
- Whether the raw Mesh, MeshFilter and owning GameObject show different results
- Whether the problem affects preview, export or both
- Relevant external bundle/resource filenames
- Complete exception text when an error is shown

A good issue title looks like:

```text
[v2.4h] Raw Mesh chooses different material from its exact MeshRenderer
```

Do not upload copyrighted game bundles publicly unless you have permission. A textual inspector report and focused screenshots are often enough to diagnose a problem.

---

## Project history

This README describes only the current release.

Detailed historical release notes may be retained under:

```text
history/
```

UBE developed incrementally through real asset investigations. Many compatibility paths came from finding different generations of Unity content, shader conventions, material layouts and animation pipelines coexisting inside long-lived games.

---

## Legal and responsible use

UBE is an unofficial independent project and is not affiliated with Unity Technologies, Pico, Mighty Coconut, Rovio or other game and hardware developers.

Use UBE only with files that you own or are legally entitled to inspect. Respect copyright, licences, game terms and local law.

UBE does not bypass DRM, decrypt protected content or modify the original Unity files.

Game, engine, product and company names are trademarks of their respective owners.

---

## Acknowledgements

UBE is built with open-source Python projects including:

- UnityPy
- PySide6
- PyOpenGL
- Pillow
- NumPy
- pygltflib
- lz4

Optional FSB5 decoding is provided externally by vgmstream.

The tool also benefited from extensive hands-on testing across many real Unity asset layouts, including years of content created under different Unity versions and rendering pipelines.

---

## License

Unity Bundle Explorer is licensed under the
[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0.txt).

Copyright © 2026 Michael Archer.

Redistributions and derivative works must preserve the applicable copyright,
licence and attribution notices as required by the Apache License 2.0.
See [NOTICE](./NOTICE) for the original project attribution.

## Support the project

Unity Bundle Explorer is provided free of charge.

Development has involved extensive investigation and testing across many Unity
asset formats, animation systems, material layouts and game versions. If UBE
has been useful to you and you would like to support its continued development:

☕ [Buy Me a Coffee](https://buymeacoffee.com/mikeybabes)

Support is entirely optional and does not affect access to the project.

## Contact and issue reports

For bugs, compatibility problems and feature requests, please use the GitHub
Issues page so that reports and solutions remain available to other users.

For direct contact:

**Michael Archer**  
**Email:** [mikeybabes@gmail.com](mailto:mikeybabes@gmail.com)
