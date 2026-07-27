#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Batch GLB Thumbnail Renderer using Blender — scale-correct lighting
=========================================

Run this from normal Python. It launches Blender once in background mode and
renders one PNG/JPG thumbnail per .glb file.

Examples:
  python glb_thumbnail_batch.py "G:\Exports\GLB" --same-folder
  python glb_thumbnail_batch.py "G:\Exports\GLB" --out "G:\Exports\Thumbs" --recursive
  python glb_thumbnail_batch.py "G:\Exports\GLB" --blender "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
  python glb_thumbnail_batch.py "G:\Exports\GLB" --view front --size 1024 --format jpg
  python glb_thumbnail_batch.py "G:\Exports\GLB" --light-strength 0.75 --overwrite

Output:
  - thumbnail images
  - glb_thumbnail_report.tsv
  - glb_thumbnail_report.json

Notes:
  - Requires Blender installed.
  - Blender must be in PATH, or pass --blender with the full path to blender.exe.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


BLENDER_WORKER = r"""
from __future__ import annotations

import argparse
import csv
import json
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = list(__import__("sys").argv)
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--files-json", required=True)
    ap.add_argument("--same-folder", action="store_true")
    ap.add_argument("--recursive", action="store_true")
    ap.add_argument("--size", type=int, default=768)
    ap.add_argument("--format", choices=["png", "jpg"], default="png")
    ap.add_argument("--jpg-quality", type=int, default=92)
    ap.add_argument("--view", choices=["iso", "front", "back", "left", "right", "top"], default="iso")
    ap.add_argument("--transparent", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--suffix", default="__preview")
    ap.add_argument("--material-mode", choices=["TEXTURED", "MATERIAL", "SOLID"], default="TEXTURED")
    ap.add_argument("--light-strength", type=float, default=1.0)
    return ap.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for datablock_collection in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.textures,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(datablock_collection):
            try:
                if block.users == 0:
                    datablock_collection.remove(block)
            except Exception:
                pass


def enable_gltf_importer():
    try:
        bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        pass


def import_glb(path: Path):
    enable_gltf_importer()
    bpy.ops.import_scene.gltf(filepath=str(path))


def scene_mesh_objects():
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def world_bounds(objects):
    mins = Vector((float("inf"), float("inf"), float("inf")))
    maxs = Vector((float("-inf"), float("-inf"), float("-inf")))
    any_corner = False

    for obj in objects:
        try:
            for corner in obj.bound_box:
                v = obj.matrix_world @ Vector(corner)
                mins.x = min(mins.x, v.x)
                mins.y = min(mins.y, v.y)
                mins.z = min(mins.z, v.z)
                maxs.x = max(maxs.x, v.x)
                maxs.y = max(maxs.y, v.y)
                maxs.z = max(maxs.z, v.z)
                any_corner = True
        except Exception:
            pass

    if not any_corner:
        return Vector((0, 0, 0)), Vector((1, 1, 1)), Vector((1, 1, 1))

    center = (mins + maxs) * 0.5
    dims = maxs - mins
    return center, dims, maxs


def look_at(obj, target: Vector):
    direction = target - obj.location
    if direction.length == 0:
        direction = Vector((0, -1, 0))
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def view_direction(name: str) -> Vector:
    if name == "front":
        return Vector((0, -1, 0.12)).normalized()
    if name == "back":
        return Vector((0, 1, 0.12)).normalized()
    if name == "left":
        return Vector((-1, 0, 0.12)).normalized()
    if name == "right":
        return Vector((1, 0, 0.12)).normalized()
    if name == "top":
        return Vector((0, 0, 1)).normalized()
    return Vector((1.8, -2.4, 1.25)).normalized()


def setup_camera_and_lights(size: int, view: str, transparent: bool, material_mode: str, light_strength: float):
    scene = bpy.context.scene

    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except Exception:
        try:
            scene.render.engine = "BLENDER_EEVEE"
        except Exception:
            scene.render.engine = "BLENDER_WORKBENCH"

    scene.render.resolution_x = int(size)
    scene.render.resolution_y = int(size)
    scene.render.film_transparent = bool(transparent)
    # Use Blender's highlight-preserving colour management where available.
    # "Standard" clips bright PBR materials very easily, especially on small
    # glossy objects such as golf balls.
    view_transform_set = False
    for transform_name in ("AgX", "Filmic", "Standard"):
        try:
            scene.view_settings.view_transform = transform_name
            view_transform_set = True
            break
        except Exception:
            continue

    try:
        scene.view_settings.look = "Medium High Contrast"
    except Exception:
        try:
            scene.view_settings.look = "None"
        except Exception:
            pass

    try:
        scene.view_settings.exposure = 0
        scene.view_settings.gamma = 1
    except Exception:
        pass

    try:
        scene.eevee.taa_render_samples = 32
    except Exception:
        pass

    try:
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = material_mode
    except Exception:
        pass

    objects = scene_mesh_objects()
    center, dims, _ = world_bounds(objects)
    max_dim = max(dims.x, dims.y, dims.z, 0.001)

    cam_data = bpy.data.cameras.new("UBE_Thumbnail_Camera")
    cam = bpy.data.objects.new("UBE_Thumbnail_Camera", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    direction = view_direction(view)
    distance = max_dim * 3.0 + 2.0
    cam.location = center + direction * distance
    look_at(cam, center)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max_dim * 1.35
    cam_data.clip_end = max(1000, distance * 10)

    # Blender light power is expressed in real-world units. The light
    # positions and sizes below scale with the model, so their power must scale
    # with model_size squared as well. Without this, a 4 cm object receives the
    # same 450 W intended for a roughly 1 m object while the light is only a few
    # centimetres away, causing severe white clipping.
    safe_dim = max(float(max_dim), 1.0e-6)
    power_scale = safe_dim * safe_dim
    user_strength = max(float(light_strength), 0.0)

    light_data = bpy.data.lights.new("UBE_Key_Area", "AREA")
    light = bpy.data.objects.new("UBE_Key_Area", light_data)
    scene.collection.objects.link(light)
    light.location = center + Vector((safe_dim * 1.8, -safe_dim * 2.0, safe_dim * 2.2))
    light_data.energy = 450.0 * power_scale * user_strength
    light_data.size = safe_dim * 3.0
    look_at(light, center)

    fill_data = bpy.data.lights.new("UBE_Fill", "POINT")
    fill = bpy.data.objects.new("UBE_Fill", fill_data)
    scene.collection.objects.link(fill)
    fill.location = center + Vector((-safe_dim * 1.5, safe_dim * 1.4, safe_dim * 1.0))
    fill_data.energy = 65.0 * power_scale * user_strength

    # A small neutral world contribution softens the unlit side without
    # washing out the imported material colours.
    try:
        scene.world.use_nodes = True
        background = scene.world.node_tree.nodes.get("Background")
        if background is not None:
            background.inputs["Color"].default_value = (0.055, 0.055, 0.055, 1.0)
            background.inputs["Strength"].default_value = 0.35
    except Exception:
        pass

    return center, dims


def output_path_for(glb_path: Path, input_root: Path, out_root: Path, same_folder: bool, suffix: str, fmt: str) -> Path:
    ext = ".png" if fmt == "png" else ".jpg"
    if same_folder:
        return glb_path.with_name(glb_path.stem + suffix + ext)
    try:
        rel = glb_path.relative_to(input_root)
    except Exception:
        rel = Path(glb_path.name)
    return out_root / rel.with_name(rel.stem + suffix + ext)


def render_one(glb_path: Path, out_path: Path, args) -> dict:
    row = {
        "glb": str(glb_path),
        "thumbnail": str(out_path),
        "status": "ERROR",
        "message": "",
        "meshes": 0,
        "objects": 0,
    }

    try:
        if out_path.exists() and not args.overwrite:
            row["status"] = "SKIPPED"
            row["message"] = "thumbnail exists"
            return row

        clear_scene()
        import_glb(glb_path)

        mesh_objects = scene_mesh_objects()
        row["objects"] = len(bpy.context.scene.objects)
        row["meshes"] = len(mesh_objects)

        if not mesh_objects:
            row["status"] = "ERROR"
            row["message"] = "no mesh objects after import"
            return row

        setup_camera_and_lights(
            args.size,
            args.view,
            args.transparent,
            args.material_mode,
            args.light_strength,
        )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        scene = bpy.context.scene
        if args.format == "png":
            scene.render.image_settings.file_format = "PNG"
            scene.render.image_settings.color_mode = "RGBA" if args.transparent else "RGB"
        else:
            scene.render.image_settings.file_format = "JPEG"
            scene.render.image_settings.quality = int(args.jpg_quality)
            scene.render.image_settings.color_mode = "RGB"

        scene.render.filepath = str(out_path)
        bpy.ops.render.render(write_still=True)

        if out_path.exists() and out_path.stat().st_size > 0:
            row["status"] = "OK"
            row["message"] = "rendered"
        else:
            row["status"] = "ERROR"
            row["message"] = "render finished but output file missing/empty"

    except Exception as exc:
        row["status"] = "ERROR"
        row["message"] = f"{type(exc).__name__}: {exc}"
        row["traceback"] = traceback.format_exc()

    finally:
        try:
            clear_scene()
        except Exception:
            pass

    return row


def main():
    args = parse_args()
    input_root = Path(args.input_root)
    out_root = Path(args.out_root)
    files = [Path(p) for p in json.loads(Path(args.files_json).read_text(encoding="utf-8"))]

    out_root.mkdir(parents=True, exist_ok=True)
    rows = []

    for i, glb_path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {glb_path}", flush=True)
        out_path = output_path_for(glb_path, input_root, out_root, args.same_folder, args.suffix, args.format)
        row = render_one(glb_path, out_path, args)
        print(f"  {row['status']}: {row['message']}", flush=True)
        rows.append(row)

    tsv_path = out_root / "glb_thumbnail_report.tsv"
    json_path = out_root / "glb_thumbnail_report.json"

    with tsv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["status", "glb", "thumbnail", "message", "meshes", "objects"],
            delimiter="\t",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    ok = sum(1 for r in rows if r["status"] == "OK")
    skipped = sum(1 for r in rows if r["status"] == "SKIPPED")
    errors = sum(1 for r in rows if r["status"] == "ERROR")
    print(f"Done: {ok} rendered, {skipped} skipped, {errors} errors")
    print(f"Report: {tsv_path}")
    print(f"Report: {json_path}")

    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
"""


def find_blender(user_value: str | None) -> str:
    if user_value:
        p = Path(user_value)
        if p.exists():
            return str(p)
        found = shutil.which(user_value)
        if found:
            return found
        raise SystemExit(f"Blender not found: {user_value}")

    found = shutil.which("blender")
    if found:
        return found

    candidates = [
        r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender\blender.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c

    raise SystemExit(
        "Could not find blender.exe. Either add Blender to PATH or pass:\n"
        '  --blender "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe"'
    )


def collect_glbs(root: Path, recursive: bool) -> list[Path]:
    if root.is_file() and root.suffix.lower() == ".glb":
        return [root.resolve()]
    if not root.exists():
        raise SystemExit(f"Input path does not exist: {root}")
    if not root.is_dir():
        raise SystemExit(f"Input path must be a .glb file or folder: {root}")
    pattern = "**/*.glb" if recursive else "*.glb"
    return sorted(p.resolve() for p in root.glob(pattern) if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch render PNG/JPG thumbnails for GLB files using Blender")
    ap.add_argument("input", help="Input .glb file or folder of .glb files")
    ap.add_argument("--out", help="Output thumbnail folder. Default: <input>_thumbnails")
    ap.add_argument("--same-folder", action="store_true", help="Write thumbnails next to each GLB file")
    ap.add_argument("--recursive", "-r", action="store_true", help="Scan subfolders")
    ap.add_argument("--blender", help="Path to blender.exe, or command name if in PATH")
    ap.add_argument("--size", type=int, default=768, help="Thumbnail size in pixels. Default: 768")
    ap.add_argument("--format", choices=["png", "jpg"], default="png", help="Output image format. Default: png")
    ap.add_argument("--jpg-quality", type=int, default=92, help="JPG quality. Default: 92")
    ap.add_argument("--view", choices=["iso", "front", "back", "left", "right", "top"], default="iso", help="Camera view. Default: iso")
    ap.add_argument("--transparent", action="store_true", help="Transparent background for PNG")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing thumbnails")
    ap.add_argument("--suffix", default="__preview", help="Output filename suffix. Default: __preview")
    ap.add_argument("--material-mode", choices=["TEXTURED", "MATERIAL", "SOLID"], default="TEXTURED", help="Fallback viewport material mode")
    ap.add_argument("--light-strength", type=float, default=1.0, help="Lighting multiplier after automatic model-scale correction. Default: 1.0")
    ap.add_argument("--dry-run", action="store_true", help="Only list files and planned command")
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    input_root = input_path.parent if input_path.is_file() else input_path

    glbs = collect_glbs(input_path, args.recursive)
    if not glbs:
        raise SystemExit("No .glb files found")

    if args.out:
        out_root = Path(args.out).resolve()
    elif args.same_folder:
        out_root = input_root
    else:
        out_root = input_root.with_name(input_root.name + "_thumbnails")

    blender = find_blender(args.blender)

    with tempfile.TemporaryDirectory(prefix="ube_glb_thumbs_") as td:
        td_path = Path(td)
        worker = td_path / "blender_glb_thumbnail_worker.py"
        files_json = td_path / "glb_files.json"
        worker.write_text(BLENDER_WORKER, encoding="utf-8")
        files_json.write_text(json.dumps([str(p) for p in glbs], indent=2), encoding="utf-8")

        cmd = [
            blender,
            "--background",
            "--python-exit-code", "1",
            "--python", str(worker),
            "--",
            "--input-root", str(input_root),
            "--out-root", str(out_root),
            "--files-json", str(files_json),
            "--size", str(args.size),
            "--format", args.format,
            "--jpg-quality", str(args.jpg_quality),
            "--view", args.view,
            "--suffix", args.suffix,
            "--material-mode", args.material_mode,
            "--light-strength", str(args.light_strength),
        ]
        if args.same_folder:
            cmd.append("--same-folder")
        if args.recursive:
            cmd.append("--recursive")
        if args.transparent:
            cmd.append("--transparent")
        if args.overwrite:
            cmd.append("--overwrite")

        print(f"Found {len(glbs)} GLB file(s)")
        print(f"Blender: {blender}")
        print(f"Output: {out_root}")
        if args.dry_run:
            print("Dry run command:")
            print(" ".join(f'"{c}"' if " " in c else c for c in cmd))
            return 0

        out_root.mkdir(parents=True, exist_ok=True)
        return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
