#!/usr/bin/env python3
"""
UBE Export Validator
====================

Validate exported OBJ/MTL/texture sets and GLB files from Unity Bundle Explorer.

Usage:
  python ube_export_validator.py exported_model.obj
  python ube_export_validator.py exported_model.glb
  python ube_export_validator.py exported_folder --recursive
  python ube_export_validator.py exported_folder --json report.json

The validator checks:
  OBJ:
    - vertex / normal / UV counts
    - face indices in range
    - degenerate faces
    - mtllib exists
    - usemtl names exist in MTL
    - texture files referenced by MTL exist

  GLB:
    - header, version, chunk lengths
    - JSON chunk parses
    - BIN chunk length matches buffer
    - bufferViews stay within buffer
    - accessors stay inside bufferViews
    - index accessor max is inside POSITION vertex count
    - material / texture / image counts
"""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
from pathlib import Path
from typing import Any


def _issue(level: str, msg: str, **extra: Any) -> dict[str, Any]:
    out = {"level": level, "message": msg}
    out.update(extra)
    return out


def validate_obj(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    stats = {
        "type": "OBJ",
        "path": str(path),
        "vertices": 0,
        "texcoords": 0,
        "normals": 0,
        "faces": 0,
        "triangles_estimate": 0,
        "mtllibs": [],
        "usemtl": [],
        "materials_defined": [],
        "textures_referenced": [],
    }

    if not path.exists():
        return {"ok": False, "stats": stats, "issues": [_issue("error", "OBJ file does not exist")]}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "stats": stats, "issues": [_issue("error", f"Could not read OBJ: {e}")]}    

    faces_for_range: list[tuple[int, list[tuple[int | None, int | None, int | None]]]] = []
    usemtl_names: set[str] = set()
    mtllibs: list[str] = []

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        head = parts[0]
        if head == "v":
            stats["vertices"] += 1
        elif head == "vt":
            stats["texcoords"] += 1
        elif head == "vn":
            stats["normals"] += 1
        elif head == "mtllib" and len(parts) > 1:
            name = " ".join(parts[1:])
            mtllibs.append(name)
            stats["mtllibs"].append(name)
        elif head == "usemtl" and len(parts) > 1:
            name = " ".join(parts[1:])
            usemtl_names.add(name)
        elif head == "f":
            stats["faces"] += 1
            verts = []
            for token in parts[1:]:
                vals = token.split("/")
                def parse_idx(i: int) -> int | None:
                    if i >= len(vals) or vals[i] == "":
                        return None
                    try:
                        return int(vals[i])
                    except Exception:
                        return None
                verts.append((parse_idx(0), parse_idx(1), parse_idx(2)))
            faces_for_range.append((lineno, verts))
            if len(verts) >= 3:
                stats["triangles_estimate"] += len(verts) - 2

    stats["usemtl"] = sorted(usemtl_names)

    if stats["vertices"] == 0:
        issues.append(_issue("error", "OBJ has no vertices"))
    if stats["faces"] == 0:
        issues.append(_issue("error", "OBJ has no faces"))

    # Range checks. OBJ positive indices are 1-based. Negative indices are relative.
    vc, tc, nc = stats["vertices"], stats["texcoords"], stats["normals"]
    bad_face_count = 0
    for lineno, verts in faces_for_range:
        if len(verts) < 3:
            issues.append(_issue("error", "Face has fewer than 3 vertices", line=lineno))
            bad_face_count += 1
            continue
        seen_pos: list[int] = []
        for vi, vti, vni in verts:
            if vi is None:
                issues.append(_issue("error", "Face vertex missing position index", line=lineno))
                bad_face_count += 1
                break
            pos = vi if vi > 0 else vc + vi + 1
            if pos < 1 or pos > vc:
                issues.append(_issue("error", f"Position index out of range: {vi}", line=lineno))
                bad_face_count += 1
                break
            seen_pos.append(pos)
            if vti is not None:
                tex = vti if vti > 0 else tc + vti + 1
                if tex < 1 or tex > tc:
                    issues.append(_issue("error", f"UV index out of range: {vti}", line=lineno))
                    bad_face_count += 1
                    break
            if vni is not None:
                nor = vni if vni > 0 else nc + vni + 1
                if nor < 1 or nor > nc:
                    issues.append(_issue("error", f"Normal index out of range: {vni}", line=lineno))
                    bad_face_count += 1
                    break
        if len(set(seen_pos)) < 3:
            issues.append(_issue("warning", "Degenerate face uses fewer than 3 unique position vertices", line=lineno))

        if bad_face_count > 25:
            issues.append(_issue("error", "Too many face index errors; stopping detailed face checks"))
            break

    # MTL checks.
    material_defs: set[str] = set()
    texture_refs: list[Path] = []
    for mtllib in mtllibs:
        mtl_path = (path.parent / mtllib).resolve()
        if not mtl_path.exists():
            issues.append(_issue("error", f"MTL file missing: {mtllib}"))
            continue
        try:
            mtl_text = mtl_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            issues.append(_issue("error", f"Could not read MTL {mtllib}: {e}"))
            continue

        for raw in mtl_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] == "newmtl" and len(parts) > 1:
                material_defs.add(" ".join(parts[1:]))
            elif parts[0] in {
                "map_Kd", "map_Ka", "map_Ks", "map_Bump", "map_bump", "bump",
                "disp", "decal", "map_d", "map_Pr", "map_Pm", "map_Ps", "norm",
            } and len(parts) > 1:
                # OBJ map statements can have options. The file is normally the final token.
                tex = parts[-1]
                texture_refs.append((mtl_path.parent / tex).resolve())

    stats["materials_defined"] = sorted(material_defs)
    stats["textures_referenced"] = [str(x) for x in texture_refs]

    for name in sorted(usemtl_names):
        if material_defs and name not in material_defs:
            issues.append(_issue("error", f"usemtl references undefined material: {name}"))

    for tex_path in texture_refs:
        if not tex_path.exists():
            issues.append(_issue("error", f"Texture file referenced by MTL is missing: {tex_path.name}"))

    if not mtllibs and usemtl_names:
        issues.append(_issue("warning", "OBJ uses materials but has no mtllib statement"))
    if stats["texcoords"] == 0:
        issues.append(_issue("warning", "OBJ has no UV coordinates"))
    if stats["normals"] == 0:
        issues.append(_issue("warning", "OBJ has no normals"))

    ok = not any(i["level"] == "error" for i in issues)
    return {"ok": ok, "stats": stats, "issues": issues}


def _component_size(component_type: int) -> int:
    return {
        5120: 1,  # BYTE
        5121: 1,  # UNSIGNED_BYTE
        5122: 2,  # SHORT
        5123: 2,  # UNSIGNED_SHORT
        5125: 4,  # UNSIGNED_INT
        5126: 4,  # FLOAT
    }.get(component_type, 0)


def _type_components(type_name: str) -> int:
    return {
        "SCALAR": 1,
        "VEC2": 2,
        "VEC3": 3,
        "VEC4": 4,
        "MAT2": 4,
        "MAT3": 9,
        "MAT4": 16,
    }.get(type_name, 0)


def validate_glb(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "type": "GLB",
        "path": str(path),
        "version": None,
        "declared_length": None,
        "actual_length": None,
        "meshes": 0,
        "primitives": 0,
        "materials": 0,
        "textures": 0,
        "images": 0,
        "buffers": 0,
        "bufferViews": 0,
        "accessors": 0,
    }

    if not path.exists():
        return {"ok": False, "stats": stats, "issues": [_issue("error", "GLB file does not exist")]}

    data = path.read_bytes()
    stats["actual_length"] = len(data)
    if len(data) < 12:
        return {"ok": False, "stats": stats, "issues": [_issue("error", "File is too small for GLB header")]}

    magic, version, declared_len = struct.unpack_from("<4sII", data, 0)
    stats["version"] = version
    stats["declared_length"] = declared_len
    if magic != b"glTF":
        issues.append(_issue("error", f"Bad GLB magic: {magic!r}"))
    if version != 2:
        issues.append(_issue("error", f"Unsupported GLB version: {version}"))
    if declared_len != len(data):
        issues.append(_issue("error", f"Declared length {declared_len} does not match actual length {len(data)}"))

    off = 12
    json_chunk = None
    bin_chunk = b""
    chunk_index = 0
    while off + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<II", data, off)
        off += 8
        if off + chunk_len > len(data):
            issues.append(_issue("error", "Chunk extends beyond end of file", chunk=chunk_index))
            break
        chunk = data[off:off + chunk_len]
        off += chunk_len
        if chunk_type == 0x4E4F534A:  # JSON
            json_chunk = chunk
        elif chunk_type == 0x004E4942:  # BIN
            bin_chunk = chunk
        else:
            issues.append(_issue("warning", f"Unknown GLB chunk type: 0x{chunk_type:08x}", chunk=chunk_index))
        chunk_index += 1

    if off != len(data):
        issues.append(_issue("warning", f"Trailing or unparsed bytes: parser ended at {off}, file length {len(data)}"))

    if json_chunk is None:
        return {"ok": False, "stats": stats, "issues": issues + [_issue("error", "No JSON chunk found")]}

    try:
        gltf = json.loads(json_chunk.decode("utf-8").rstrip("\x00 "))
    except Exception as e:
        return {"ok": False, "stats": stats, "issues": issues + [_issue("error", f"Could not parse GLB JSON: {e}")]}    

    stats["meshes"] = len(gltf.get("meshes", []) or [])
    stats["materials"] = len(gltf.get("materials", []) or [])
    stats["textures"] = len(gltf.get("textures", []) or [])
    stats["images"] = len(gltf.get("images", []) or [])
    stats["buffers"] = len(gltf.get("buffers", []) or [])
    stats["bufferViews"] = len(gltf.get("bufferViews", []) or [])
    stats["accessors"] = len(gltf.get("accessors", []) or [])
    stats["generator"] = (gltf.get("asset") or {}).get("generator", "")

    primitives = []
    for mi, mesh in enumerate(gltf.get("meshes", []) or []):
        for pi, prim in enumerate(mesh.get("primitives", []) or []):
            primitives.append((mi, pi, prim))
    stats["primitives"] = len(primitives)

    if stats["meshes"] == 0:
        issues.append(_issue("error", "GLB has no meshes"))
    if stats["primitives"] == 0:
        issues.append(_issue("error", "GLB has no mesh primitives"))

    buffers = gltf.get("buffers", []) or []
    if buffers:
        declared = int(buffers[0].get("byteLength", 0) or 0)
        if declared > len(bin_chunk):
            issues.append(_issue("error", f"Buffer declares {declared} bytes, BIN chunk only has {len(bin_chunk)} bytes"))
        elif declared < len(bin_chunk):
            issues.append(_issue("warning", f"BIN chunk has {len(bin_chunk) - declared} extra padding/bytes beyond declared buffer"))
    elif bin_chunk:
        issues.append(_issue("warning", "GLB has BIN chunk but no buffers entry"))

    bviews = gltf.get("bufferViews", []) or []
    accessors = gltf.get("accessors", []) or []
    for i, bv in enumerate(bviews):
        bo = int(bv.get("byteOffset", 0) or 0)
        bl = int(bv.get("byteLength", 0) or 0)
        if bo < 0 or bl < 0 or bo + bl > len(bin_chunk):
            issues.append(_issue("error", f"bufferView {i} points outside BIN chunk", byteOffset=bo, byteLength=bl))

    for i, acc in enumerate(accessors):
        bv_i = acc.get("bufferView")
        if bv_i is None:
            continue
        if not isinstance(bv_i, int) or bv_i < 0 or bv_i >= len(bviews):
            issues.append(_issue("error", f"accessor {i} references invalid bufferView {bv_i}"))
            continue
        bv = bviews[bv_i]
        comp = _component_size(int(acc.get("componentType", 0) or 0))
        comps = _type_components(str(acc.get("type", "")))
        count = int(acc.get("count", 0) or 0)
        offset = int(acc.get("byteOffset", 0) or 0)
        stride = int(bv.get("byteStride", 0) or 0)
        elem = comp * comps
        if comp == 0 or comps == 0:
            issues.append(_issue("error", f"accessor {i} has unsupported component/type"))
            continue
        if count > 0:
            needed = offset + (count - 1) * (stride or elem) + elem
        else:
            needed = offset
        if needed > int(bv.get("byteLength", 0) or 0):
            issues.append(_issue("error", f"accessor {i} overruns bufferView {bv_i}", needed=needed, bufferViewLength=bv.get("byteLength")))

    # Primitive-specific sanity.
    for mi, pi, prim in primitives:
        attrs = prim.get("attributes", {}) or {}
        pos_i = attrs.get("POSITION")
        idx_i = prim.get("indices")
        pos_count = None
        if isinstance(pos_i, int) and 0 <= pos_i < len(accessors):
            pos_count = int(accessors[pos_i].get("count", 0) or 0)
        else:
            issues.append(_issue("error", f"mesh {mi} primitive {pi} has no valid POSITION accessor"))
        if isinstance(idx_i, int) and 0 <= idx_i < len(accessors):
            idx_acc = accessors[idx_i]
            idx_count = int(idx_acc.get("count", 0) or 0)
            max_list = idx_acc.get("max") or []
            if pos_count is not None and max_list:
                try:
                    max_idx = int(max_list[0])
                    if max_idx >= pos_count:
                        issues.append(_issue("error", f"indices max {max_idx} exceeds POSITION count {pos_count}", mesh=mi, primitive=pi))
                except Exception:
                    pass
            if idx_count % 3 != 0 and int(prim.get("mode", 4) or 4) == 4:
                issues.append(_issue("warning", f"triangle indices count is not divisible by 3", mesh=mi, primitive=pi, indices=idx_count))
        else:
            issues.append(_issue("warning", f"mesh {mi} primitive {pi} has no indices accessor"))

    if stats["images"] == 0:
        issues.append(_issue("warning", "GLB has no embedded/external images; export is geometry-only or material fallback"))
    if stats["materials"] == 0:
        issues.append(_issue("warning", "GLB has no materials"))
    elif stats["textures"] == 0:
        issues.append(_issue("warning", "GLB has materials but no texture slots"))

    ok = not any(i["level"] == "error" for i in issues)
    return {"ok": ok, "stats": stats, "issues": issues}


def validate_path(path: Path, recursive: bool = False) -> list[dict[str, Any]]:
    if path.is_file():
        suffix = path.suffix.lower()
        if suffix == ".obj":
            return [validate_obj(path)]
        if suffix == ".glb":
            return [validate_glb(path)]
        return [{"ok": False, "stats": {"path": str(path)}, "issues": [_issue("error", "Unsupported file type; expected .obj or .glb")]}]

    if not path.is_dir():
        return [{"ok": False, "stats": {"path": str(path)}, "issues": [_issue("error", "Path does not exist")]}]

    pattern = "**/*" if recursive else "*"
    files = [p for p in path.glob(pattern) if p.suffix.lower() in {".obj", ".glb"}]
    if not files:
        return [{"ok": False, "stats": {"path": str(path)}, "issues": [_issue("error", "No .obj or .glb files found")]}]
    return [validate_obj(p) if p.suffix.lower() == ".obj" else validate_glb(p) for p in sorted(files)]


def format_report(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    ok_count = sum(1 for r in results if r.get("ok"))
    lines.append(f"Validated {len(results)} file(s): {ok_count} OK, {len(results) - ok_count} with errors")
    lines.append("")

    for r in results:
        stats = r.get("stats", {})
        issues = r.get("issues", [])
        lines.append("=" * 72)
        lines.append(f"{'OK' if r.get('ok') else 'FAIL'}: {stats.get('path', '-')}")
        lines.append(f"Type: {stats.get('type', '-')}")
        if stats.get("type") == "OBJ":
            lines.append(f"Vertices: {stats.get('vertices')}  UVs: {stats.get('texcoords')}  Normals: {stats.get('normals')}")
            lines.append(f"Faces: {stats.get('faces')}  Triangles estimate: {stats.get('triangles_estimate')}")
            lines.append(f"MTL files: {', '.join(stats.get('mtllibs') or []) or '-'}")
            lines.append(f"Materials used: {', '.join(stats.get('usemtl') or []) or '-'}")
            lines.append(f"Textures referenced: {len(stats.get('textures_referenced') or [])}")
        elif stats.get("type") == "GLB":
            lines.append(f"Generator: {stats.get('generator') or '-'}")
            lines.append(f"GLB version: {stats.get('version')}  length: {stats.get('actual_length')} bytes")
            lines.append(f"Meshes: {stats.get('meshes')}  Primitives: {stats.get('primitives')}")
            lines.append(f"Materials: {stats.get('materials')}  Textures: {stats.get('textures')}  Images: {stats.get('images')}")
            lines.append(f"BufferViews: {stats.get('bufferViews')}  Accessors: {stats.get('accessors')}")
        if issues:
            lines.append("Issues:")
            for i in issues:
                extra = {k: v for k, v in i.items() if k not in {"level", "message"}}
                suffix = f" {extra}" if extra else ""
                lines.append(f"  [{i.get('level', '?').upper()}] {i.get('message')}{suffix}")
        else:
            lines.append("Issues: none")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate UBE OBJ/MTL/texture and GLB exports")
    ap.add_argument("path", help="OBJ, GLB, or folder to validate")
    ap.add_argument("--recursive", "-r", action="store_true", help="When PATH is a folder, scan recursively")
    ap.add_argument("--json", dest="json_out", help="Write machine-readable JSON report")
    args = ap.parse_args()

    results = validate_path(Path(args.path), recursive=args.recursive)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(format_report(results))
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
