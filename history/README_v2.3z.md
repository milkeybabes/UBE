# UBE v2.3z Build 339 — Alternate Character Colour UV Recovery

## v2.3z alternate character colour UV recovery

Textureless external character materials can now recover a detailed colour
unwrap from UV1 when UV0 is absent or constant. This fixes Labyrinth
`MiscGoblin01_Rig_03:h14_metalPS_011`, whose 3,383 vertices all share one UV0
coordinate while UV1 contains the complete 3,242-point atlas unwrap. The switch
is evidence-based, applies only to decisive recovered character materials, and
preserves explicit non-zero U-key selections.


## v2.3y compact character palette recovery

Textureless external character-material shells can now be recovered when a
skinned mesh uses a compact multi-swatch UV0 layout, not only a broad atlas
unwrap. Labyrinth's chicken skins have 511 vertices but repeat only four UV0
coordinates inside a small section of the shared character texture. The old
span threshold rejected them, leaving the successfully resolved external URP
`Lit` shell grey.

The new evidence check accepts either a conventional atlas unwrap or a strongly
repeated multi-point palette lookup. A single constant UV point is still
rejected, and recovery still requires a SkinnedMeshRenderer plus one decisive
local character-material donor. Existing resolved textured materials remain
authoritative.

## v2.3x mutually-exclusive animation renderer variants

Animation owners can contain several numbered complete skinned rigs at the same
transform. The bundle may serialize every renderer as active because runtime code
chooses the visible model variant. UBE previously drew all alternatives together,
which caused z-fighting, a composite silhouette and colours sampled from several
atlas layouts at once.

UBE now detects this pattern conservatively: every candidate must be a numbered
namespace variant with the same rendered suffix, identical transform, equivalent
mesh topology/bounds/skinning structure, and a distinct Mesh asset. One renderer
is shown by default and the existing I hotkey cycles the alternatives. Ordinary
multi-part characters and assemblies remain fully visible because their rendered
roles or transforms differ.

## v2.3w rigid index-only skinning

CPU animation skinning now supports Unity meshes where every vertex belongs to
exactly one bone. Unity may optimise these meshes by storing only a single
BlendIndices value per vertex and omitting BlendWeight entirely; the implicit
weight is 1.0. UBE previously rejected that valid layout and therefore decoded
the eye-joint animation while leaving the visible eye geometry static.

The recovery is structural rather than name-based: it requires an index-only
channel, one component per vertex, and indices that fit the mesh bind-pose table.
Ordinary four-weight skinned meshes and static meshes continue through their
existing paths unchanged. Vertex-channel labels now also use Unity's modern
format names, so format 10 is reported correctly as UInt32.

## v2.3v external material shell recovery

Skinned mesh preview now distinguishes a truly usable resolved external Material
from a textureless shared-material shell. Labyrinth characters can resolve the
generic URP `Lit` Material successfully while receiving no base texture at all.
When the mesh has atlas UV evidence and one complete local character Material is
an unambiguous match, UBE recovers that local texture setup. Genuine resolved
external materials with base textures remain authoritative and unchanged.

## v2.3u object/animation external material pass-through

Object and AnimationClip preview now preserves the selected renderer's unresolved
Material PPtrs while enforcing exact renderer slots. This lets the v2.3t local
character-template recovery reach the actual animated render instance instead of
being hidden by the object-specific graph wrapper.

The change is intentionally narrow: only unresolved Material slots from the
selected MeshRenderer/SkinnedMeshRenderer are passed through. Resolved renderer
materials remain authoritative, and unrelated materials used elsewhere by a shared
Mesh are not added. OBJ and GLB object export share the corrected path.

UBE v2.3 promotes the animation work from the v2.2 series into a major release.
The selected AnimationClip can now be exported as a portable animated GLB when
UBE has enough trustworthy data to reproduce it.

## v2.3i frame-accurate animation timeline

Animation scrubbing and live playback now sample exact authored frames rather
than arbitrary 1/1000 timeline divisions. This prevents impossible one-tick
intermediate poses on streamed rigs with animated non-uniform scale.

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

The export option remains unavailable for unresolved Transform paths,
incomplete skin/bind-pose data, constraints, or other structural cases that
cannot be represented safely. Runtime owner/linkage diagnostics and unsupported
non-Transform property bindings are now advisory when the resolved preview
hierarchy itself is complete.

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


## v2.3a — Animation External Colour Hydration

AnimationClip preview now hydrates external Renderer/Material/base-colour texture dependencies before the 3D material cache is built, so cross-bundle `_ColorMap` assets display in colour on first selection rather than only after opening a Material.


## v2.3b — AudioSource Inspector

AudioSource components now resolve their assigned AudioClip and expose playback, mixer and 2D/3D spatial settings. The clip relationship is clickable, and AudioClip reverse links identify every loaded AudioSource that uses the sound. This makes animation companion audio discoverable without guessing from raw PathIDs.
## v2.3c — Audio Mixer Inspectors

AudioMixerController, AudioMixerGroupController, AudioMixerSnapshotController and AudioMixerEffectController now have dedicated routing inspectors. Mixer groups show their hierarchy, controls/effect chain and reverse links to every AudioSource routed through them. This makes the route back to scene playback components visible while clearly distinguishing routing from actual AudioClip assignment.

## v2.3f — Preview-Proven Animated GLB Export

Animated GLB eligibility now follows the same resolved render hierarchy and
sampled pose data used by the working 3D preview. A strange or unrelated Unity
runtime owner link no longer blocks export when the skeleton, skinned renderer,
weights, bind poses and Transform tracks are otherwise complete.

Unsupported non-Transform bindings such as unidentified SkinnedMeshRenderer
properties are reported as export notes and omitted instead of hiding the
export button. The resulting GLB preserves the resolved Transform and skeletal
animation visible in UBE; omitted property channels are clearly identified in
the tooltip, status line and successful-export message.



## v2.3d — Clickable Animation Owner

After an AnimationClip preview resolves its authoritative owner, the inspector now shows a clickable **Animation owner** card. It links directly to the resolved GameObject and records whether ownership came from a Legacy Animation component, Animator/controller wiring, a clip-named owner, a numbered variant or the coherent target hierarchy. Render-only parent promotion does not replace the true animation owner.


## v2.3g — In-Place Duration Limit

Animation preview now includes a **Limit** control beside Speed. It activates
with **In place** and limits playback looping, scrubbing, export eligibility and
Animated GLB baking to the first selected number of seconds. This turns long
world-travel timelines into compact reusable local motion cycles without
changing the authored AnimationClip. The **Full** button restores the complete
clip immediately.


## v2.3j — Complete Root-Motion Lock

In-place preview now holds the detected travel controller's authored first-frame position, rotation and scale. This prevents an offset creature or vehicle from orbiting across the scene when its parent world-heading rotation continues after translation has been removed. Internal skeletal movement remains fully animated, and the same correction is used by limited playback and Animated GLB export.


## v2.3k — Compact Animation Controls

The animation row now labels the export action **Export GLB** and uses a tighter
Speed selector. This frees space for the duration and frame counter without
changing any animated export behaviour.


## v2.3l — Tight Animation Toolbar

Play, Reset pose, Export GLB, Full and the Speed selector now use fixed compact
toolbar sizing with reduced padding. The frame counter is also excluded from
the window minimum-width calculation, preventing long clips from widening the
application.

## v2.3p — Block-Colour Palette Materials

UBE now recognises the common Unity block-colour/palette UV layout where UV0
contains a small number of repeated swatch lookup points and UV1 contains a
normal full-surface unwrap. OBJ-based preview/export can now rebuild texture
coordinates per vertex when UnityPy deduplicates its `vt` rows, preventing the
whole colour atlas from being stretched across flat-colour meshes.

For runtime-assigned palette materials that serialize without a texture slot,
UBE can conservatively recover a clearly named swatch/palette Texture2D from
the loaded bundle when the mesh UV layout confirms that intent. Real-material
fallbacks also remain neutral white rather than implying a missing grey
material.


## v2.3s — Stripped Material Family Recovery

UBE now recovers empty runtime Material variants from an unambiguous complete
sibling Material family before attempting a global palette texture fallback.
This preserves per-mesh UV0 block colours for materials such as
`Blokhaven_Dynamic_Characters` without relying on a `PS` mesh-name suffix.


## v2.3v — External Material Shell Recovery

UBE now distinguishes a genuinely usable resolved external Material from a
textureless shared-material shell.  A skinned mesh such as Labyrinth's Hoggle
can resolve to the generic URP `Lit` Material in `urp_assets_all.bundle` while
still receiving no base texture.  When the mesh has real atlas UV evidence and
one complete local character Material wins unambiguously, preview/export now
recovers that local appearance template.  Successfully resolved external
materials that contain a base texture remain authoritative and unchanged.