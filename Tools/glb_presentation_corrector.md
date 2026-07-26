# GLB Presentation Corrector v1.1

A standalone, dependency-free Python utility that makes GLB assets convenient
to view, render or convert to video while leaving their original geometry,
materials, skinning and animation tracks intact.

## Important v1.1 correction for skinned GLBs

glTF skinning applies transforms from the **joint hierarchy**, and the transform
of the node containing the skinned mesh is ignored.

Version 1.0 placed the complete scene beneath one correction node. That works
for ordinary rigid meshes, but compliant viewers may ignore the correction for
a skinned mesh and report:

```text
NODE_SKINNED_MESH_NON_ROOT
Node with a skinned mesh is not root.
Parent transforms will not affect a skinned mesh.
```

Version 1.1 handles the two cases separately:

```text
Scene
├── SkinnedMeshNode                    remains a direct scene root
└── PresentationRoot_Corrector
    ├── Rig / joint hierarchy          correction acts through the joints
    └── Ordinary rigid/static roots
```

It also evaluates the **actual skinned vertex positions** when calculating
first-frame or animation bounds. This is important when inverse bind matrices
and a distant Unity rig origin make the undeformed POSITION accessor misleading.

## Default operation

```bat
python glb_presentation_corrector.py "Model.glb"
```

This:

- centres the visible asset around X=0 and Z=0;
- places its lowest visible point on Y=0;
- uses the first frame of animation 0 when animation exists;
- writes `Model_presented.glb`;
- leaves the input file untouched.

## Centre on all three axes

```bat
python glb_presentation_corrector.py "Model.glb" --center xyz --no-ground
```

## Turn a backwards-facing model around

```bat
python glb_presentation_corrector.py "Model.glb" --rotate-y 180
```

Other useful values are `90`, `-90` and `270`.

## Centre using the complete animation travel area

```bat
python glb_presentation_corrector.py "Model.glb" --bounds animation --samples 120
```

For very dense skinned meshes, full-animation mode samples at most 12,000
vertices per primitive by default:

```bat
python glb_presentation_corrector.py "Model.glb" --bounds animation --max-skin-vertices 25000
```

Use `--max-skin-vertices 0` to evaluate every vertex at every sampled pose.

First-frame and rest-pose modes always evaluate every skinned vertex.

## Process a folder

```bat
python glb_presentation_corrector.py "G:\GLB Exports" --recursive
```

## Output to another folder

```bat
python glb_presentation_corrector.py "G:\GLB Exports" --recursive --output-dir "G:\Corrected GLB"
```

## Preview the correction without writing

```bat
python glb_presentation_corrector.py "Model.glb" --dry-run
```

## Reprocessing

Running v1.1 on a file previously processed by v1.0 automatically unwraps the
old correction root and replaces it with the corrected scene structure. It does
not stack multiple presentation roots.

## Limitations

- GLB 2.0 with an embedded primary buffer is supported.
- Sparse accessors and external `.gltf` buffers are not supported.
- Node TRS animation is evaluated.
- Morph-target deformation is not currently included in presentation bounds.
- Full-animation skinned bounds may be vertex-sampled for performance.
- A malformed source in which a skinned mesh is already below another node is
  rejected rather than rewritten unsafely.
- The source is overwritten only when `--overwrite` is explicitly supplied.

## Full help

```bat
python glb_presentation_corrector.py --help
```
