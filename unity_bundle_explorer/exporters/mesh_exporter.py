from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import os
import struct
import math
import tempfile
import shutil
import copy

from .texture_exporter import safe_filename, export_texture_record, export_texture_array_slice_record
from ..app_info import APP_VERSION, APP_BUILD
from ..asset_graph.relationship import AssetRelationship


@dataclass(slots=True)
class MeshExportResult:
    path: Path | None
    log_path: Path | None
    ok: bool
    message: str
    mtl_path: Path | None = None
    json_path: Path | None = None


# =====================================================
# Preview/export ground-up basis helper
# =====================================================

def _normalise_ground_axis(axis: str | None) -> str:
    key = str(axis or "+Y").strip().upper().replace(" ", "")
    aliases = {
        "X": "+X", "+X": "+X", "POSX": "+X",
        "-X": "-X", "NEGX": "-X",
        "Y": "+Y", "+Y": "+Y", "POSY": "+Y",
        "-Y": "-Y", "NEGY": "-Y",
        "Z": "+Z", "+Z": "+Z", "POSZ": "+Z",
        "-Z": "-Z", "NEGZ": "-Z",
    }
    return aliases.get(key, "+Y")


def _ground_axis_label(axis: str | None) -> str:
    axis = _normalise_ground_axis(axis)
    return {
        "+Y": "+Y up / Unity default",
        "-Y": "-Y up",
        "+Z": "+Z up",
        "-Z": "-Z up",
        "+X": "+X up",
        "-X": "-X up",
    }.get(axis, "+Y up / Unity default")


def _ground_axis_transform_vec(v: tuple[float, float, float], axis: str | None) -> tuple[float, float, float]:
    """Rotate authored axis so it becomes +Y in exported/viewed space."""
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    axis = _normalise_ground_axis(axis)
    if axis == "+Y":
        return (x, y, z)
    if axis == "-Y":
        return (x, -y, -z)       # rotate 180° around X
    if axis == "+Z":
        return (x, z, -y)        # rotate -90° around X
    if axis == "-Z":
        return (x, -z, y)        # rotate +90° around X
    if axis == "+X":
        return (-y, x, z)        # rotate +90° around Z
    if axis == "-X":
        return (y, -x, z)        # rotate -90° around Z
    return (x, y, z)


def _ground_axis_quaternion(axis: str | None) -> list[float] | None:
    """glTF quaternion [x, y, z, w] matching _ground_axis_transform_vec."""
    axis = _normalise_ground_axis(axis)
    s = math.sqrt(0.5)
    if axis == "+Y":
        return None
    if axis == "-Y":
        return [1.0, 0.0, 0.0, 0.0]       # 180° X
    if axis == "+Z":
        return [-s, 0.0, 0.0, s]          # -90° X
    if axis == "-Z":
        return [s, 0.0, 0.0, s]           # +90° X
    if axis == "+X":
        return [0.0, 0.0, s, s]           # +90° Z
    if axis == "-X":
        return [0.0, 0.0, -s, s]          # -90° Z
    return None


def _transform_obj_file_ground_axis(obj_path: Path, axis: str | None) -> bool:
    axis = _normalise_ground_axis(axis)
    if axis == "+Y":
        return False
    try:
        lines = obj_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return False

    out: list[str] = []
    changed = False
    for line in lines:
        if line.startswith("v ") or line.startswith("vn "):
            prefix = "vn" if line.startswith("vn ") else "v"
            parts = line.split()
            if len(parts) >= 4:
                try:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                    tx, ty, tz = _ground_axis_transform_vec((x, y, z), axis)
                    if len(parts) > 4:
                        out.append(f"{prefix} {tx:.9g} {ty:.9g} {tz:.9g} " + " ".join(parts[4:]))
                    else:
                        out.append(f"{prefix} {tx:.9g} {ty:.9g} {tz:.9g}")
                    changed = True
                    continue
                except Exception:
                    pass
        out.append(line)

    if changed:
        obj_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def _wrap_glb_scene_ground_axis(glb_path: Path, axis: str | None) -> bool:
    axis = _normalise_ground_axis(axis)
    quat = _ground_axis_quaternion(axis)
    if quat is None:
        return False
    try:
        gltf, blob = _read_glb(glb_path)
    except Exception:
        return False

    scenes = gltf.setdefault("scenes", [{"nodes": []}])
    scene_index = int(gltf.get("scene", 0) or 0)
    if scene_index < 0 or scene_index >= len(scenes):
        scene_index = 0
        gltf["scene"] = 0
    scene = scenes[scene_index]
    scene_nodes = list(scene.get("nodes", []) or [])
    if not scene_nodes:
        nodes = gltf.get("nodes", []) or []
        scene_nodes = list(range(len(nodes)))

    if not scene_nodes:
        return False

    nodes = gltf.setdefault("nodes", [])
    wrapper_index = len(nodes)
    nodes.append({
        "name": f"UBE ground/up axis wrapper ({_ground_axis_label(axis)})",
        "rotation": quat,
        "children": [int(n) for n in scene_nodes],
    })
    scene["nodes"] = [wrapper_index]

    try:
        glb_path.write_bytes(_glb_make_glb_bytes(gltf, bytearray(blob)))
        return True
    except Exception:
        return False


def apply_ground_axis_to_export_result(result: MeshExportResult, axis: str | None) -> MeshExportResult:
    """Apply the same simple ground/up basis used by the preview to an export result.

    For OBJ exports, vertex and normal lines are rewritten.
    For GLB exports, a lightweight root node rotation wraps the scene.
    Texture files, MTL files and metadata are left untouched.
    """
    axis = _normalise_ground_axis(axis)
    if axis == "+Y" or not result or not getattr(result, "ok", False) or not getattr(result, "path", None):
        return result

    try:
        p = Path(result.path)
    except Exception:
        return result

    changed = False
    if p.suffix.lower() == ".obj":
        changed = _transform_obj_file_ground_axis(p, axis)
    elif p.suffix.lower() == ".glb":
        changed = _wrap_glb_scene_ground_axis(p, axis)

    if changed:
        try:
            if result.log_path:
                with Path(result.log_path).open("a", encoding="utf-8") as f:
                    f.write(f"\nGround/up axis applied: {_ground_axis_label(axis)}\n")
        except Exception:
            pass
    return result



def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            try:
                return getattr(obj, name)
            except Exception:
                pass
    return default


def _vec3(v: Any) -> tuple[float, float, float] | None:
    if v is None:
        return None
    if hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z"):
        try:
            return (float(v.x), float(v.y), float(v.z))
        except Exception:
            return None
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        try:
            return (float(v[0]), float(v[1]), float(v[2]))
        except Exception:
            return None
    return None


def _vec2(v: Any) -> tuple[float, float] | None:
    if v is None:
        return None
    if hasattr(v, "x") and hasattr(v, "y"):
        try:
            return (float(v.x), float(v.y))
        except Exception:
            return None
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        try:
            return (float(v[0]), float(v[1]))
        except Exception:
            return None
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    try:
        return list(value)
    except Exception:
        return []


def _normalise_vertices(value: Any) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for item in _as_list(value):
        v = _vec3(item)
        if v is not None:
            out.append(v)
    return out


def _vec4(v: Any) -> tuple[float, float, float, float] | None:
    if v is None:
        return None
    if hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z") and hasattr(v, "w"):
        try:
            return (float(v.x), float(v.y), float(v.z), float(v.w))
        except Exception:
            return None
    if isinstance(v, (list, tuple)) and len(v) >= 4:
        try:
            return (float(v[0]), float(v[1]), float(v[2]), float(v[3]))
        except Exception:
            return None
    return None


def _normalise_tangents(value: Any) -> list[tuple[float, float, float, float]]:
    out: list[tuple[float, float, float, float]] = []
    for item in _as_list(value):
        t = _vec4(item)
        if t is not None:
            out.append(t)
    return out


def _normalise_uvs(value: Any) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for item in _as_list(value):
        uv = _vec2(item)
        if uv is None:
            continue
        u, v = uv
        # Some Unity/UnityPy streamed meshes can expose bogus UV payloads for
        # non-UV channels.  Never let NaN/Inf values escape into atlas maths.
        if not (math.isfinite(u) and math.isfinite(v)):
            continue
        out.append((u, v))
    return out


def _normalise_faces(value: Any) -> list[tuple[int, int, int]]:
    raw = _as_list(value)
    if not raw:
        return []

    first = raw[0]
    if isinstance(first, (list, tuple)) and len(first) >= 3:
        faces = []
        for f in raw:
            try:
                faces.append((int(f[0]), int(f[1]), int(f[2])))
            except Exception:
                pass
        return faces

    faces = []
    for i in range(0, len(raw) - 2, 3):
        try:
            faces.append((int(raw[i]), int(raw[i + 1]), int(raw[i + 2])))
        except Exception:
            pass
    return faces


def _write_basic_obj(name: str, vertices, faces, normals=None, uvs=None) -> str:
    lines = ["# Exported by UBE", f"o {name}"]
    for x, y, z in vertices:
        lines.append(f"v {x:.9g} {y:.9g} {z:.9g}")
    for uv in (uvs or []):
        u, v = uv
        # OBJ's texture V axis often matches viewers better with the source value here;
        # if a specific Unity asset looks flipped, we can make this configurable later.
        lines.append(f"vt {u:.9g} {v:.9g}")
    for n in (normals or []):
        x, y, z = n
        lines.append(f"vn {x:.9g} {y:.9g} {z:.9g}")

    has_uv = bool(uvs) and len(uvs) >= len(vertices)
    has_n = bool(normals) and len(normals) >= len(vertices)
    for a, b, c in faces:
        ia, ib, ic = a + 1, b + 1, c + 1
        if has_uv and has_n:
            lines.append(f"f {ia}/{ia}/{ia} {ib}/{ib}/{ib} {ic}/{ic}/{ic}")
        elif has_uv:
            lines.append(f"f {ia}/{ia} {ib}/{ib} {ic}/{ic}")
        elif has_n:
            lines.append(f"f {ia}//{ia} {ib}//{ib} {ic}//{ic}")
        else:
            lines.append(f"f {ia} {ib} {ic}")
    lines.append("")
    return "\n".join(lines)


def _try_unitypy_export(data: Any) -> str | None:
    exp = getattr(data, "export", None)
    if not callable(exp):
        return None
    try:
        result = exp()
    except TypeError:
        return None
    except Exception:
        return None

    if isinstance(result, bytes):
        try:
            text = result.decode("utf-8", errors="replace")
        except Exception:
            return None
        return text if "\nv " in text or text.startswith("v ") or "\nf " in text else None
    if isinstance(result, str):
        return result if "\nv " in result or result.startswith("v ") or "\nf " in result else None

    for attr in ("obj", "text", "data"):
        value = getattr(result, attr, None)
        if isinstance(value, str) and ("\nv " in value or "\nf " in value):
            return value
    return None


def _try_manual_obj(data: Any, name: str, uv_channel: int = 0) -> tuple[str | None, str]:
    vertices = _normalise_vertices(_get(data, "vertices", "m_Vertices", "vertexes", default=None))
    normals = _normalise_vertices(_get(data, "normals", "m_Normals", default=None))
    uv_sets = mesh_uv_channels_from_data(data)
    uvs = uv_sets.get(int(uv_channel)) or uv_sets.get(0) or []
    faces = _normalise_faces(_get(data, "faces", "triangles", "indices", "m_Indices", default=None))

    if not vertices:
        return None, "No decoded vertex list exposed by UnityPy for this mesh."
    if not faces:
        return None, "No decoded face/index list exposed by UnityPy for this mesh."
    return _write_basic_obj(name, vertices, faces, normals=normals, uvs=uvs), "manual decoded attributes"


# =====================================================
# UV / atlas helpers
# =====================================================

def _bytes_from(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return bytes(value)
    # UnityPy may expose byte arrays as list[int] or array('B').
    try:
        return bytes(value)
    except Exception:
        return None


def _reader_bytes_at(reader: Any, offset: int, size: int) -> bytes | None:
    if reader is None or size <= 0:
        return None
    try:
        data = getattr(reader, "bytes", None)
        if isinstance(data, (bytes, bytearray, memoryview)):
            chunk = bytes(data[offset:offset + size])
            return chunk if chunk else None
    except Exception:
        pass

    old_pos = None
    try:
        tell = getattr(reader, "tell", None)
        if callable(tell):
            old_pos = tell()
    except Exception:
        old_pos = None

    try:
        seek = getattr(reader, "seek", None)
        read = getattr(reader, "read", None)
        if callable(seek) and callable(read):
            seek(offset)
            chunk = read(size)
            if isinstance(chunk, (bytes, bytearray, memoryview)) and chunk:
                return bytes(chunk)
    except Exception:
        pass
    finally:
        if old_pos is not None:
            try:
                reader.seek(old_pos)
            except Exception:
                pass
    return None


def _resource_name_matches(candidate_name: Any, stream_path: str) -> bool:
    if not candidate_name or not stream_path:
        return False
    c = str(candidate_name).replace("\\", "/").split("/")[-1].lower()
    p = str(stream_path).replace("\\", "/")
    if p.startswith("archive:/"):
        p = p[len("archive:/"):]
    p = p.split("/")[-1].lower()
    return c == p


def _read_mesh_stream_bytes_from_record(record: Any, data: Any) -> bytes | None:
    """Read external streamed mesh vertex data, e.g. archive:/...resS.

    Many modern Unity meshes keep m_VertexData.m_DataSize empty and put the
    real vertex stream in m_StreamData.  The Walkabout golf balls are one of
    those cases, so UV1 cannot be decoded unless this stream is read.
    """
    stream = _get(data, "m_StreamData", "stream_data", default=None)
    if stream is None:
        return None
    try:
        offset = int(_get(stream, "offset", "m_Offset", default=0) or 0)
        size = int(_get(stream, "size", "m_Size", default=0) or 0)
    except Exception:
        return None
    path = _get(stream, "path", "m_Path", default="") or ""
    if not path or size <= 0:
        return None

    # Direct or beside-bundle .resS file first.
    candidates: list[Path] = []
    try:
        p = Path(str(path))
        if p.exists():
            candidates.append(p)
    except Exception:
        pass

    try:
        bundle_path = Path(getattr(record.object.assets_file, "path", ""))
        if str(bundle_path):
            clean = str(path)
            if clean.startswith("archive:/"):
                clean = clean[len("archive:/"):]
            clean = clean.replace("\\", "/")
            candidates.append(bundle_path.parent / clean)
            candidates.append(bundle_path.parent / Path(clean).name)
    except Exception:
        pass

    for candidate in candidates:
        try:
            if candidate.exists():
                with candidate.open("rb") as f:
                    f.seek(offset)
                    chunk = f.read(size)
                    if chunk:
                        return chunk
        except Exception:
            continue

    # UnityPy keeps archive:/...resS inside environment.cabs / parent.files.
    try:
        assets_file = getattr(record.object, "assets_file", None)
        env = getattr(assets_file, "environment", None)
        cabs = getattr(env, "cabs", {}) if env is not None else {}
        for name, reader in cabs.items():
            if _resource_name_matches(name, path):
                chunk = _reader_bytes_at(reader, offset, size)
                if chunk:
                    return chunk
    except Exception:
        pass

    try:
        assets_file = getattr(record.object, "assets_file", None)
        parent = getattr(assets_file, "parent", None)
        files = getattr(parent, "files", {}) if parent is not None else {}
        for name, reader in files.items():
            if _resource_name_matches(name, path):
                chunk = _reader_bytes_at(reader, offset, size)
                if chunk:
                    return chunk
    except Exception:
        pass

    return None


def _component_size_for_vertex_format(fmt: Any) -> int | None:
    try:
        f = int(fmt)
    except Exception:
        return None

    # Unity changed / re-labelled VertexAttributeFormat values across eras and
    # UnityPy exposes them slightly differently across versions.  For atlas
    # work we only need to know byte width.  Prefer the modern Unity mapping
    # here, then let _infer_component_size_for_channel() override it from the
    # actual stream offsets when that gives stronger evidence.
    # Modern mapping: 0 Float32, 1 Float16, 2 UNorm8, 3 SNorm8, 4 UNorm16, ...
    if f == 0:
        return 4
    if f == 1:
        return 2
    if f in (2, 3, 6, 7):
        return 1
    if f in (4, 5, 8, 9):
        return 2
    if f in (10, 11):
        return 4

    # Older UnityPy builds have also appeared with 1 meaning Float32 and 2
    # meaning Float16.  If the stream-offset inference cannot help, keep a
    # fallback rather than failing completely.
    if f == 2:
        return 2
    if f in (11, 12):
        return 4
    return None


def _infer_component_size_for_channel(ch: Any, channels: list[Any], stream_index: int, stride: int | None) -> int | None:
    """Infer component byte-size from neighbouring channel offsets.

    This matters for the Walkabout golf balls: the channel table says UV0
    offset 28 and UV1 offset 32.  If those are Float2 values they cannot both
    be 32-bit floats because they would overlap.  The offsets prove they are
    16-bit half-float UVs: 2 components × 2 bytes = 4 bytes.
    """
    try:
        off = int(_get(ch, "offset", "m_Offset", default=0) or 0)
        dim = int(_get(ch, "dimension", "m_Dimension", default=0) or 0)
    except Exception:
        return None
    if dim <= 0:
        return None

    next_offsets: list[int] = []
    for other in channels:
        try:
            if int(_get(other, "stream", "m_Stream", default=0) or 0) != int(stream_index):
                continue
            other_off = int(_get(other, "offset", "m_Offset", default=0) or 0)
            if other_off > off:
                next_offsets.append(other_off)
        except Exception:
            continue

    span: int | None = None
    if next_offsets:
        span = min(next_offsets) - off
    elif stride is not None and stride > off:
        span = int(stride) - off

    if span is None or span <= 0:
        return None
    if span % dim != 0:
        return None
    comp_size = span // dim
    return comp_size if comp_size in (1, 2, 4) else None


def _read_vertex_component(raw: bytes, offset: int, fmt: Any, component_size: int | None = None) -> float | None:
    try:
        f = int(fmt)
    except Exception:
        f = -1
    try:
        # When the channel offsets identify 16-bit/32-bit float data, trust
        # that above the enum value.  This is the key to decoding UV1 on the
        # golf-ball meshes.
        if component_size == 4:
            return float(struct.unpack_from("<f", raw, offset)[0])
        if component_size == 2:
            return float(struct.unpack_from("<e", raw, offset)[0])

        if f == 0:
            return float(struct.unpack_from("<f", raw, offset)[0])
        if f == 1:
            return float(struct.unpack_from("<e", raw, offset)[0])

        # Normalised/integer formats are unusual for UVs but make a readable
        # best effort instead of failing entirely.
        if f in (2, 6):
            return float(struct.unpack_from("<B", raw, offset)[0]) / 255.0
        if f in (3, 7):
            return max(-1.0, float(struct.unpack_from("<b", raw, offset)[0]) / 127.0)
        if f in (4, 8):
            return float(struct.unpack_from("<H", raw, offset)[0]) / 65535.0
        if f in (5, 9):
            return max(-1.0, float(struct.unpack_from("<h", raw, offset)[0]) / 32767.0)
        if f == 10:
            return float(struct.unpack_from("<I", raw, offset)[0])
        if f == 11:
            return float(struct.unpack_from("<i", raw, offset)[0])
    except Exception:
        return None
    return None


def _vertex_stream_stride(stream: Any, channels: list[Any], stream_index: int) -> int | None:
    stride = _get(stream, "stride", "m_Stride", default=None) if stream is not None else None
    try:
        if stride is not None and int(stride) > 0:
            return int(stride)
    except Exception:
        pass

    max_end = 0
    for ch in channels:
        try:
            if int(_get(ch, "stream", "m_Stream", default=0) or 0) != int(stream_index):
                continue
            dim = int(_get(ch, "dimension", "m_Dimension", default=0) or 0)
            if dim <= 0:
                continue
            fmt = _get(ch, "format", "m_Format", default=0)
            size = _component_size_for_vertex_format(fmt)
            off = int(_get(ch, "offset", "m_Offset", default=0) or 0)
            if size:
                max_end = max(max_end, off + dim * size)
        except Exception:
            continue
    return max_end or None


def _infer_planar_stream_layout_when_streams_missing(
    vdata: Any,
    channels: list[Any],
    raw: bytes | None,
    vertex_count: int,
) -> dict[int, tuple[int, int]]:
    """Infer Unity's separate vertex-stream layout when m_Streams is absent.

    Some UnityPy builds expose m_VertexData.m_DataSize as one byte blob but do
    not expose m_Streams.  The blob can still be laid out as separate streams:

        stream0 for every vertex, then stream1 for every vertex, then stream2...

    Important detail: Unity commonly aligns each stream start to a 16-byte
    boundary.  If stream0 ends on an 8-byte boundary, Unity may insert 8 bytes
    before stream1.  Reading UV0 from the unaligned offset shifts the UVs by one
    Float2, which looks like a tiny atlas/texture offset.

    HardHatGeo / HatchlingGeo in the Angry Birds VR sample are examples:
        stream0: position + normal = 24 bytes/vertex
        stream1: UV0               =  8 bytes/vertex
        stream2: weights/indices   = 32 bytes/vertex

    The older v1.8zh logic accepted the extra bytes only as a tail after the
    last stream.  This version tries both layouts and prefers the one that best
    explains the raw byte size, including 16-byte padding *between* streams.
    """
    if not raw or not channels or vertex_count <= 0:
        return {}

    active_streams: list[int] = []
    for ch in channels:
        try:
            dim = int(_get(ch, "dimension", "m_Dimension", default=0) or 0)
            if dim <= 0:
                continue
            s = int(_get(ch, "stream", "m_Stream", default=0) or 0)
        except Exception:
            continue
        if s not in active_streams:
            active_streams.append(s)
    active_streams.sort()
    if len(active_streams) <= 1:
        return {}

    strides: dict[int, int] = {}
    for s in active_streams:
        stride = _vertex_stream_stride(None, channels, s)
        if not stride or stride <= 0:
            return {}
        strides[s] = int(stride)

    raw_len = len(raw)
    max_stride = max(strides.values()) if strides else 0

    def align_up(value: int, align: int) -> int:
        if align <= 1:
            return value
        return ((value + align - 1) // align) * align

    def build_candidate(align_between_streams: int) -> tuple[dict[int, tuple[int, int]], int, int] | None:
        out: dict[int, tuple[int, int]] = {}
        offset = 0
        for idx, s in enumerate(active_streams):
            if idx > 0:
                offset = align_up(offset, align_between_streams)
            if offset > raw_len:
                return None
            out[s] = (offset, strides[s])
            offset += strides[s] * vertex_count
        if offset > raw_len:
            return None
        padding = raw_len - offset
        if padding:
            if padding > max(64, max_stride * 2):
                return None
            if padding % 4 != 0:
                return None
        return out, padding, align_between_streams

    candidates = []
    cand = build_candidate(1)
    if cand is not None:
        candidates.append(cand)
    cand = build_candidate(16)
    if cand is not None:
        candidates.append(cand)

    if not candidates:
        return {}

    candidates.sort(key=lambda x: (x[1], 0 if x[2] == 16 else 1))
    return candidates[0][0]


def _vertex_raw_bytes_from_vdata(vdata: Any) -> bytes | None:
    """Return the raw vertex byte stream from UnityPy's vertex-data object.

    Unity versions / UnityPy builds expose this inconsistently.  In some
    versions ``m_DataSize`` is the *byte array*, while in others it behaves
    like a size/count field and the real bytes sit on ``data``/``m_Data``.
    Build 156 asked _get() for m_DataSize first, so an integer size could
    stop the search before reaching the actual data.  This helper tries all
    candidates and only accepts values that really become non-empty bytes.
    """
    if vdata is None:
        return None

    for name in (
        "m_DataSize",
        "data_size",
        "m_Data",
        "data",
        "raw_data",
        "m_RawData",
        "bytes",
        "buffer",
    ):
        try:
            value = getattr(vdata, name)
        except Exception:
            continue

        # A plain integer here is usually a size/count, not the vertex buffer.
        if isinstance(value, int):
            continue

        raw = _bytes_from(value)
        if raw:
            return raw
    return None


def _extract_uv_channel_from_raw(data: Any, channel_index: int, raw_override: bytes | None = None) -> list[tuple[float, float]]:
    """Decode Unity Mesh UV channels from m_VertexData when UnityPy does not
    expose convenient uv0/uv1 attributes.  This keeps the ball-atlas insight
    useful for modern Unity bundles where UV0/UV1 are packed in vertex streams.
    """
    vdata = _get(data, "m_VertexData", "vertex_data", default=None)
    if vdata is None:
        return []
    raw = raw_override or _vertex_raw_bytes_from_vdata(vdata)
    if not raw:
        return []

    channels = _as_list(_get(vdata, "m_Channels", "channels", default=None))
    if channel_index < 0 or channel_index >= len(channels):
        return []
    ch = channels[channel_index]

    try:
        dim = int(_get(ch, "dimension", "m_Dimension", default=0) or 0)
    except Exception:
        dim = 0
    if dim < 2:
        return []

    fmt = _get(ch, "format", "m_Format", default=0)

    try:
        stream_index = int(_get(ch, "stream", "m_Stream", default=0) or 0)
    except Exception:
        stream_index = 0
    try:
        ch_offset = int(_get(ch, "offset", "m_Offset", default=0) or 0)
    except Exception:
        ch_offset = 0

    streams = _as_list(_get(vdata, "m_Streams", "streams", default=None))
    stream = streams[stream_index] if 0 <= stream_index < len(streams) else None

    vertex_count = _get(vdata, "m_VertexCount", "vertex_count", default=None)
    if vertex_count is None:
        vertex_count = _get(data, "m_VertexCount", "vertex_count", default=None)
    try:
        count = int(vertex_count)
    except Exception:
        count = 0

    planar_layout = {}
    if stream is None and count > 0 and raw:
        planar_layout = _infer_planar_stream_layout_when_streams_missing(vdata, channels, raw, count)

    if planar_layout and stream_index in planar_layout:
        stream_offset, stride = planar_layout[stream_index]
    else:
        try:
            stream_offset = int(_get(stream, "offset", "m_Offset", default=0) or 0) if stream is not None else 0
        except Exception:
            stream_offset = 0
        stride = _vertex_stream_stride(stream, channels, stream_index)

        # When UnityPy exposes no m_Streams and the raw blob is not a clean
        # multi-stream planar layout, keep the older single-interleaved fallback.
        # This still supports the Walkabout golf-ball meshes where raw size /
        # vertex count gives the true per-vertex stride.
        if count > 0 and raw and stream is None:
            guessed = len(raw) // count
            if guessed > 0 and guessed * count <= len(raw):
                stride = guessed
        elif (not stride) and count > 0 and raw:
            guessed = len(raw) // count
            if guessed > 0 and guessed * count <= len(raw):
                stride = guessed
    if not stride:
        return []

    inferred_size = _infer_component_size_for_channel(ch, channels, stream_index, stride)
    comp_size = inferred_size or _component_size_for_vertex_format(fmt)
    if not comp_size:
        return []

    if count <= 0:
        count = max(0, (len(raw) - stream_offset) // stride)

    out: list[tuple[float, float]] = []
    for i in range(count):
        base = stream_offset + i * stride + ch_offset
        if base < 0 or base + comp_size * 2 > len(raw):
            break
        u = _read_vertex_component(raw, base, fmt, comp_size)
        v = _read_vertex_component(raw, base + comp_size, fmt, comp_size)
        if u is None or v is None:
            break
        u = float(u)
        v = float(v)
        if not (math.isfinite(u) and math.isfinite(v)):
            # Treat malformed/guessed raw channels as unavailable.  This avoids
            # crashes on meshes where UnityPy reports strange compact channels.
            continue
        out.append((u, v))
    return out


def mesh_uv_channels_from_data(data: Any, raw_override: bytes | None = None) -> dict[int, list[tuple[float, float]]]:
    """Return available UV channels as {0: [(u,v)...], 1: ...}."""
    out: dict[int, list[tuple[float, float]]] = {}

    attr_candidates = {
        0: ("uv", "uv0", "m_UV0", "m_UV"),
        1: ("uv1", "m_UV1"),
        2: ("uv2", "m_UV2"),
        3: ("uv3", "m_UV3"),
    }
    for idx, names in attr_candidates.items():
        for name in names:
            value = _get(data, name, default=None)
            uvs = _normalise_uvs(value)
            if uvs:
                out[idx] = uvs
                break

    # Unity channel order: Position, Normal, Tangent, Color, UV0, UV1, UV2, UV3.
    for uv_idx, channel_idx in ((0, 4), (1, 5), (2, 6), (3, 7)):
        if uv_idx in out:
            continue
        uvs = _extract_uv_channel_from_raw(data, channel_idx, raw_override=raw_override)
        if uvs:
            out[uv_idx] = uvs

    # Some UnityPy builds expose only the active channels compacted, e.g.
    # Position, Normal, Tangent, UV0, UV1 with no empty Colour channel.
    # If the canonical slots failed, decode any remaining 2D channels after
    # tangent in active order and assign them as UV0/UV1.
    try:
        vdata = _get(data, "m_VertexData", "vertex_data", default=None)
        channels = _as_list(_get(vdata, "m_Channels", "channels", default=None)) if vdata is not None else []
        active_2d = []
        for raw_idx, ch in enumerate(channels):
            try:
                dim = int(_get(ch, "dimension", "m_Dimension", default=0) or 0)
                off = int(_get(ch, "offset", "m_Offset", default=0) or 0)
            except Exception:
                continue
            # Compact active-channel fallback is only for the normal Unity
            # UV range.  Do not treat channels 12/13 (blend weights/indices on
            # skinned meshes) as UV1/UV2 just because they are 4D.
            if dim >= 2 and 3 <= raw_idx <= 7:
                active_2d.append((raw_idx, off))
        active_2d = sorted(set(active_2d), key=lambda item: item[1])
        for uv_idx, (raw_idx, _off) in enumerate(active_2d[:4]):
            if uv_idx in out:
                continue
            uvs = _extract_uv_channel_from_raw(data, raw_idx, raw_override=raw_override)
            if uvs:
                out[uv_idx] = uvs
    except Exception:
        pass
    return out


def mesh_uv_channels_from_record(record: Any) -> dict[int, list[tuple[float, float]]]:
    """Return UV channels, including streamed mesh data when needed."""
    try:
        data = record.object.read()
    except Exception:
        return {}
    raw = _read_mesh_stream_bytes_from_record(record, data)
    return mesh_uv_channels_from_data(data, raw_override=raw)


def uv_bounds(uvs: list[tuple[float, float]]) -> dict[str, float] | None:
    if not uvs:
        return None
    finite_uvs: list[tuple[float, float]] = []
    for u, v in uvs:
        try:
            u = float(u)
            v = float(v)
        except Exception:
            continue
        if math.isfinite(u) and math.isfinite(v):
            finite_uvs.append((u, v))
    if not finite_uvs:
        return None
    us = [u for u, _v in finite_uvs]
    vs = [v for _u, v in finite_uvs]
    u_min, u_max = min(us), max(us)
    v_min, v_max = min(vs), max(vs)
    return {
        "u_min": float(u_min),
        "u_max": float(u_max),
        "v_min": float(v_min),
        "v_max": float(v_max),
        "u_span": float(u_max - u_min),
        "v_span": float(v_max - v_min),
        "count": float(len(finite_uvs)),
    }


def _nearest_tile_size(pixel_span_u: float, pixel_span_v: float) -> int | None:
    candidates = (32, 64, 128, 256, 512)
    try:
        span = max(float(pixel_span_u or 0), float(pixel_span_v or 0))
    except Exception:
        return None
    if not math.isfinite(span) or span <= 0:
        return None
    best = min(candidates, key=lambda x: abs(x - span))
    # Keep this heuristic conservative; it is a hint only.
    return best if abs(best - span) <= max(4.0, best * 0.15) else None


def atlas_region_from_uv_bounds(bounds: dict[str, float] | None, width: int, height: int) -> dict[str, Any] | None:
    if not bounds or width <= 0 or height <= 0:
        return None

    try:
        u_min = float(bounds.get("u_min", 0.0))
        u_max = float(bounds.get("u_max", 0.0))
        v_min = float(bounds.get("v_min", 0.0))
        v_max = float(bounds.get("v_max", 0.0))
    except Exception:
        return None

    # Streamed/packed meshes can sometimes produce a bogus guessed UV channel
    # with NaN/Inf bounds.  Skip atlas text rather than crashing the inspector.
    if not all(math.isfinite(v) for v in (u_min, u_max, v_min, v_max)):
        return None

    # Pixel origin here is top-left image space.  OBJ/Unity V conventions vary,
    # so show both the raw UV box and this easy-to-understand image region.
    try:
        x0 = int(round(u_min * width))
        x1 = int(round(u_max * width))
        y0 = int(round((1.0 - v_max) * height))
        y1 = int(round((1.0 - v_min) * height))
    except (OverflowError, ValueError):
        return None

    w = max(0, x1 - x0)
    h = max(0, y1 - y0)
    tile = _nearest_tile_size(w, h)
    result: dict[str, Any] = {"x": x0, "y": y0, "w": w, "h": h}
    if tile:
        result["likely_tile"] = tile
        result["tile_x"] = int(round(x0 / tile)) if tile else None
        result["tile_y"] = int(round(y0 / tile)) if tile else None
    return result


def obj_uv_list(obj_text: str) -> list[tuple[float, float]]:
    """Return texture coordinates currently present in a UnityPy-exported OBJ."""
    uvs: list[tuple[float, float]] = []
    for line in obj_text.splitlines():
        if not line.startswith("vt "):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            uvs.append((float(parts[1]), float(parts[2])))
        except Exception:
            pass
    return uvs


def obj_uv_bounds(obj_text: str) -> dict[str, float] | None:
    return uv_bounds(obj_uv_list(obj_text))


def _transform_obj_texture_coordinates(obj_text: str, scale: tuple[float, float], offset: tuple[float, float]) -> tuple[str, bool]:
    """Apply a Unity texture scale/offset to OBJ vt coordinates already present.

    This is the fallback for skinned/UnityPy OBJ exports where UBE cannot replace
    the vt list one-for-one with decoded vertex-channel UVs.  It fixes avatar /
    putter meshes that are authored in a -1..+1 UV domain by baking the inferred
    shader transform into the existing vt values.
    """
    sx, sy = scale
    ox, oy = offset
    lines = obj_text.splitlines()
    changed = False
    for i, line in enumerate(lines):
        if not line.startswith("vt "):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            u = float(parts[1]) * float(sx) + float(ox)
            v = float(parts[2]) * float(sy) + float(oy)
            if len(parts) > 3:
                lines[i] = " ".join(["vt", f"{u:.9g}", f"{v:.9g}", *parts[3:]])
            else:
                lines[i] = f"vt {u:.9g} {v:.9g}"
            changed = True
        except Exception:
            pass
    return "\n".join(lines) + "\n", changed


def _replace_obj_texture_coordinates(obj_text: str, uvs: list[tuple[float, float]]) -> tuple[str, bool]:
    """Replace existing vt lines with another UV channel when counts match.
    Faces keep the same texture-coordinate indices, which is how UnityPy exports
    simple per-vertex UV meshes such as the Walkabout golf balls.
    """
    if not uvs:
        return obj_text, False
    lines = obj_text.splitlines()
    vt_indices = [i for i, line in enumerate(lines) if line.startswith("vt ")]
    if not vt_indices:
        return obj_text, False
    if len(vt_indices) != len(uvs):
        return obj_text, False
    for line_index, (u, v) in zip(vt_indices, uvs):
        lines[line_index] = f"vt {u:.9g} {v:.9g}"
    return "\n".join(lines) + "\n", True


def _rebuild_obj_texture_coordinates_by_vertex(obj_text: str, uvs: list[tuple[float, float]]) -> tuple[str, bool]:
    """Rebuild OBJ texture coordinates so each vertex uses the matching Unity UV.

    UnityPy can legitimately emit fewer ``vt`` rows than Unity vertex rows by
    deduplicating texture coordinates.  UBE's older channel replacement only
    worked when the counts happened to match, so a requested palette UV0 could
    silently remain UnityPy's ordinary unwrap UV1.  The result is the entire
    colour swatch/atlas painted across a model.

    When the Unity UV count matches the OBJ vertex count, rebuild ``vt`` rows
    one-per-vertex and rewrite face texture indices to the corresponding vertex
    index.  Geometry, normals, groups and material assignments are preserved.
    """
    if not obj_text or not uvs:
        return obj_text, False
    lines = obj_text.splitlines()
    vertex_count = sum(1 for line in lines if line.startswith("v "))
    if vertex_count <= 0 or vertex_count != len(uvs):
        return obj_text, False

    rebuilt: list[str] = []
    inserted = False
    changed_face = False

    def emit_uvs() -> None:
        nonlocal inserted
        if inserted:
            return
        rebuilt.extend(f"vt {float(u):.9g} {float(v):.9g}" for u, v in uvs)
        inserted = True

    for line in lines:
        if line.startswith("vt "):
            # Existing UnityPy UV rows are replaced as one coherent block.
            continue
        if line.startswith("f "):
            emit_uvs()
            parts = line.split()
            new_tokens: list[str] = []
            for token in parts[1:]:
                fields = token.split("/")
                try:
                    vi_raw = int(fields[0])
                except Exception:
                    new_tokens.append(token)
                    continue
                vi = vi_raw if vi_raw > 0 else vertex_count + vi_raw + 1
                if vi <= 0 or vi > vertex_count:
                    new_tokens.append(token)
                    continue
                normal = fields[2] if len(fields) >= 3 else ""
                if normal:
                    new_tokens.append(f"{fields[0]}/{vi}/{normal}")
                else:
                    new_tokens.append(f"{fields[0]}/{vi}")
                changed_face = True
            rebuilt.append("f " + " ".join(new_tokens))
            continue
        rebuilt.append(line)

    if not inserted:
        emit_uvs()
    if not changed_face:
        return obj_text, False
    return "\n".join(rebuilt) + "\n", True


def _uv_unique_count(uvs: list[tuple[float, float]], digits: int = 6) -> int:
    values: set[tuple[float, float]] = set()
    for u, v in uvs or []:
        try:
            fu, fv = float(u), float(v)
            if math.isfinite(fu) and math.isfinite(fv):
                values.add((round(fu, digits), round(fv, digits)))
        except Exception:
            continue
    return len(values)


def _palette_lookup_uv_info(
    uv_sets: dict[int, list[tuple[float, float]]],
    *,
    allow_constant_uv0: bool = False,
) -> dict[str, Any] | None:
    """Identify the common Unity colour-swatch UV layout.

    Block-colour assets frequently store a handful of repeated UV0 points into a
    palette texture, while UV1 is a conventional almost-unique unwrap. Treating
    UV1 as diffuse coordinates paints the whole palette image over the model.

    A single repeated UV0 point is normally too ambiguous to call a palette. It
    becomes valid only when a separate material-recovery path has already proven
    that the renderer uses a named palette/swatch material shell. This covers
    rigid secondary parts that intentionally select one flat authored swatch.
    """
    uv0 = list((uv_sets or {}).get(0) or [])
    if len(uv0) < 3:
        return None
    unique0 = _uv_unique_count(uv0)
    if unique0 == 1:
        if not allow_constant_uv0:
            return None
        bounds = uv_bounds(uv0)
        if not bounds:
            return None
        try:
            u = float(bounds.get("u_min", 0.0))
            v = float(bounds.get("v_min", 0.0))
        except Exception:
            return None
        if not (math.isfinite(u) and math.isfinite(v) and -0.05 <= u <= 1.05 and -0.05 <= v <= 1.05):
            return None
        return {
            "kind": "constant_uv0_palette_lookup",
            "channel": 0,
            "vertex_count": len(uv0),
            "unique_points": 1,
            "bounds": bounds,
            "alternate_channel": None,
            "alternate_unique_points": None,
            "reason": "single authored UV0 swatch point on a proven palette material shell",
        }

    limit = max(8, min(96, int(len(uv0) * 0.15) + 1))
    if unique0 <= 0 or unique0 > limit or (unique0 / max(1, len(uv0))) > 0.25:
        return None

    best_alt = None
    for channel, values in sorted((uv_sets or {}).items()):
        if int(channel) == 0 or not values:
            continue
        unique = _uv_unique_count(values)
        bounds = uv_bounds(values)
        span = max(float((bounds or {}).get("u_span", 0.0)), float((bounds or {}).get("v_span", 0.0)))
        score = unique + (span * len(values))
        if best_alt is None or score > best_alt[0]:
            best_alt = (score, int(channel), unique, bounds)

    # A second full unwrap strengthens confidence but is not mandatory: some
    # palette-only assets genuinely contain only UV0.
    if best_alt is not None and best_alt[2] < max(unique0 * 2, int(len(uv0) * 0.35)):
        best_alt = None
    return {
        "kind": "repeated_uv0_palette_lookup",
        "channel": 0,
        "vertex_count": len(uv0),
        "unique_points": unique0,
        "bounds": uv_bounds(uv0),
        "alternate_channel": best_alt[1] if best_alt else None,
        "alternate_unique_points": best_alt[2] if best_alt else None,
        "reason": "repeated UV0 palette/swatch lookup points",
    }



def _triangle_surface_area(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> float:
    """Return the 3D area of one triangle without requiring NumPy."""
    ab = (float(b[0]) - float(a[0]), float(b[1]) - float(a[1]), float(b[2]) - float(a[2]))
    ac = (float(c[0]) - float(a[0]), float(c[1]) - float(a[1]), float(c[2]) - float(a[2]))
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return 0.5 * math.sqrt(max(0.0, cross[0] * cross[0] + cross[1] * cross[1] + cross[2] * cross[2]))


def _mixed_point_sampled_base_uv_recovery(
    record: Any,
    material_bundle: list[dict[str, Any]],
    uv_sets: dict[int, list[tuple[float, float]]],
    positions: list[tuple[float, float, float]],
    indices: list[int],
    source_vertex_indices: list[int] | None = None,
) -> tuple[dict[int, list[tuple[float, float]]], dict[str, Any] | None]:
    """Recover an old mixed swatch/auxiliary UV convention.

    Some older Amplify-shader meshes combine two very different purposes in
    UV0.  Small bolts/details use one repeated palette point, while the large
    metal panels carry an out-of-range auxiliary mapping that the original
    custom shader does *not* sample as an ordinary diffuse atlas.  A generic
    preview that applies ``_BaseMap`` directly paints large pieces of the whole
    atlas over those panels.

    Recovery is intentionally strict.  It requires:

    * a real base texture and a PS-style material-family mesh name;
    * one dominant in-range UV0 swatch point;
    * a broad, almost-unique alternate UV channel;
    * completely separate swatch and auxiliary triangles (no mixed faces);
    * out-of-range auxiliary faces whose surface area dominates the swatch
      details by a large margin.

    Only vertices belonging to the proven auxiliary faces are redirected to
    the dominant authored swatch.  The original material, texture and geometry
    stay authoritative.  Pressing U to request another UV channel bypasses this
    recovery in the export callers.
    """
    if not material_bundle or not _material_bundle_has_base_texture(material_bundle):
        return uv_sets, None

    mesh_name = str(getattr(record, "name", "") or "").lower()
    compact_name = "".join(ch for ch in mesh_name if ch.isalnum())
    ps_markers = ("metalps", "woodps", "glassps", "colorps", "colourps")
    if not any(marker in compact_name for marker in ps_markers):
        return uv_sets, None

    uv0 = list((uv_sets or {}).get(0) or [])
    if len(uv0) < 12 or not positions or len(indices or []) < 6:
        return uv_sets, None

    finite_uv0: list[tuple[float, float]] = []
    counts: dict[tuple[float, float], int] = {}
    first_value: dict[tuple[float, float], tuple[float, float]] = {}
    for value in uv0:
        try:
            u, v = float(value[0]), float(value[1])
        except Exception:
            return uv_sets, None
        if not (math.isfinite(u) and math.isfinite(v)):
            return uv_sets, None
        finite_uv0.append((u, v))
        key = (round(u, 6), round(v, 6))
        counts[key] = counts.get(key, 0) + 1
        first_value.setdefault(key, (u, v))

    if not counts:
        return uv_sets, None
    dominant_key, dominant_count = max(counts.items(), key=lambda row: row[1])
    unique0 = len(counts)
    dominant_ratio = dominant_count / max(1, len(finite_uv0))
    unique_limit = max(32, int(len(finite_uv0) * 0.30))
    if dominant_count < 8 or dominant_ratio < 0.45 or unique0 < 4 or unique0 > unique_limit:
        return uv_sets, None

    dominant_uv = first_value[dominant_key]
    if not (-0.05 <= dominant_uv[0] <= 1.05 and -0.05 <= dominant_uv[1] <= 1.05):
        return uv_sets, None

    # A broad alternate unwrap is strong evidence that UV0 is carrying custom
    # shader/palette data rather than being the only ordinary diffuse unwrap.
    alternate_channel = None
    alternate_unique = 0
    alternate_bounds = None
    for channel, values in sorted((uv_sets or {}).items()):
        if int(channel) == 0 or len(values or []) < len(finite_uv0):
            continue
        unique = _uv_unique_count(values)
        bounds = uv_bounds(values)
        span_u = float((bounds or {}).get("u_span", 0.0))
        span_v = float((bounds or {}).get("v_span", 0.0))
        if unique >= int(len(finite_uv0) * 0.65) and span_u >= 0.70 and span_v >= 0.70:
            alternate_channel = int(channel)
            alternate_unique = int(unique)
            alternate_bounds = bounds
            break
    if alternate_channel is None:
        return uv_sets, None

    output_count = len(positions)
    source_map = list(source_vertex_indices or [])
    if len(source_map) != output_count:
        if len(finite_uv0) == output_count:
            source_map = list(range(output_count))
        else:
            return uv_sets, None

    mapped_uvs: list[tuple[float, float]] = []
    try:
        for src_index in source_map:
            src_index = int(src_index)
            if src_index < 0 or src_index >= len(finite_uv0):
                return uv_sets, None
            mapped_uvs.append(finite_uv0[src_index])
    except Exception:
        return uv_sets, None

    swatch_faces = 0
    auxiliary_faces = 0
    auxiliary_outside_faces = 0
    mixed_faces = 0
    swatch_area = 0.0
    auxiliary_area = 0.0
    auxiliary_source_vertices: set[int] = set()

    for cursor in range(0, len(indices) - 2, 3):
        try:
            tri = (int(indices[cursor]), int(indices[cursor + 1]), int(indices[cursor + 2]))
        except Exception:
            continue
        if any(index < 0 or index >= output_count for index in tri):
            continue
        flags = [
            (round(mapped_uvs[index][0], 6), round(mapped_uvs[index][1], 6)) == dominant_key
            for index in tri
        ]
        area = _triangle_surface_area(positions[tri[0]], positions[tri[1]], positions[tri[2]])
        if all(flags):
            swatch_faces += 1
            swatch_area += area
            continue
        if any(flags):
            mixed_faces += 1
            continue

        auxiliary_faces += 1
        auxiliary_area += area
        tri_uvs = [mapped_uvs[index] for index in tri]
        if any(u < -0.001 or u > 1.001 or v < -0.001 or v > 1.001 for u, v in tri_uvs):
            auxiliary_outside_faces += 1
        for index in tri:
            auxiliary_source_vertices.add(int(source_map[index]))

    if mixed_faces:
        return uv_sets, None
    if swatch_faces < 2 or auxiliary_faces < 2:
        return uv_sets, None
    if auxiliary_outside_faces < max(2, int(math.ceil(auxiliary_faces * 0.50))):
        return uv_sets, None
    if swatch_area <= 1e-10 or auxiliary_area < max(0.05, swatch_area * 4.0):
        return uv_sets, None
    if not auxiliary_source_vertices:
        return uv_sets, None

    recovered = {int(channel): list(values or []) for channel, values in (uv_sets or {}).items()}
    recovered_uv0 = list(finite_uv0)
    for source_index in auxiliary_source_vertices:
        if 0 <= source_index < len(recovered_uv0):
            recovered_uv0[source_index] = dominant_uv
    recovered[0] = recovered_uv0

    area_ratio = auxiliary_area / max(swatch_area, 1e-12)
    info = {
        "kind": "mixed_point_sampled_auxiliary_uv",
        "channel": 0,
        "vertex_count": len(finite_uv0),
        "unique_points_before": unique0,
        "unique_points_after": _uv_unique_count(recovered_uv0),
        "dominant_point": [float(dominant_uv[0]), float(dominant_uv[1])],
        "dominant_vertices": int(dominant_count),
        "dominant_ratio": float(dominant_ratio),
        "flattened_vertices": len(auxiliary_source_vertices),
        "swatch_faces": int(swatch_faces),
        "auxiliary_faces": int(auxiliary_faces),
        "auxiliary_outside_faces": int(auxiliary_outside_faces),
        "swatch_surface_area": float(swatch_area),
        "auxiliary_surface_area": float(auxiliary_area),
        "auxiliary_to_swatch_area_ratio": float(area_ratio),
        "alternate_channel": alternate_channel,
        "alternate_unique_points": alternate_unique,
        "alternate_bounds": alternate_bounds,
        "bounds_before": uv_bounds(finite_uv0),
        "bounds_after": uv_bounds(recovered_uv0),
        "reason": (
            "dominant authored UV0 swatch plus separate large out-of-range auxiliary faces; "
            "large PS-style metal/wood panels redirected to the proven base-colour swatch"
        ),
    }
    return recovered, info


def _material_bundle_has_base_texture(material_bundle: list[dict[str, Any]]) -> bool:
    _mat, row = _first_base_texture_row(material_bundle)
    return row is not None


def _material_names_support_palette_fallback(material_bundle: list[dict[str, Any]]) -> bool:
    markers = ("palette", "swatch", "block", "colour", "color", "dynamic", "character")
    for mat in material_bundle or []:
        name = str(getattr(mat.get("record"), "name", "") or "").lower()
        if any(marker in name for marker in markers):
            return True
    return False


def _palette_material_context_tokens(material_bundle: list[dict[str, Any]]) -> set[str]:
    """Return meaningful lower-case words from the material names.

    Runtime-created Unity materials can serialize with no texture properties at
    all.  Their names are still useful context: ``...Green`` should be allowed
    to choose a specialised green swatch, while ``...Dynamic_Characters`` must
    prefer the normal course swatch rather than whichever specialised swatch
    happens to sort first alphabetically.
    """
    import re

    ignored = {
        "material", "mat", "texture", "tex", "map", "atlas", "palette",
        "swatch", "color", "colour", "base", "easy", "hard", "dynamic",
        "character", "characters", "block", "blokhaven",
    }
    out: set[str] = set()
    for mat in material_bundle or []:
        rec = mat.get("record") if isinstance(mat, dict) else None
        name = str(getattr(rec, "name", "") or "").lower()
        for token in re.findall(r"[a-z0-9]+", name):
            if len(token) >= 3 and token not in ignored:
                out.add(token)
    return out


def _palette_texture_candidates(
    bundle_index: Any | None,
    material_bundle: list[dict[str, Any]] | None = None,
) -> list[Any]:
    """Rank likely palette textures without letting a specialised sheet win by name order.

    v2.3p correctly recognised palette-style UV0 data, but Blokhaven contains
    both ``Blokhaven_Swatch_Texture`` and ``Blokhaven_GreenSwatch_Texture``.
    Both received the same score and the green sheet sorted first, washing out
    runtime character materials.  Prefer an unqualified/generic swatch unless a
    qualifier such as ``green`` is also present in the material name.
    """
    if bundle_index is None:
        return []
    rows: list[Any] = []
    rows.extend((getattr(bundle_index, "objects_by_type", {}) or {}).get("Texture2D", []) or [])
    rows.extend((getattr(bundle_index, "external_records_by_type", {}) or {}).get("Texture2D", []) or [])

    context_tokens = _palette_material_context_tokens(material_bundle or [])
    specialised_tokens = {
        "green", "red", "blue", "yellow", "orange", "purple", "pink",
        "metal", "metallic", "wood", "terrain", "sand", "grass", "ocean",
        "water", "gfx", "character", "characters", "seagull", "seagulls",
    }
    generic_words = {
        "texture", "tex", "map", "atlas", "palette", "swatch", "color",
        "colour", "base", "main", "blokhaven",
    }

    seen: set[tuple[str, int]] = set()
    scored: list[tuple[int, int, str, Any]] = []
    import re

    for rec in rows:
        key = _record_identity_key(rec)
        if key in seen:
            continue
        seen.add(key)
        name = str(getattr(rec, "name", "") or "")
        lower = name.lower()
        score = 0
        if "swatch" in lower:
            score += 100
        if "palette" in lower:
            score += 90
        if "coloratlas" in lower or "colouratlas" in lower or "color_atlas" in lower or "colour_atlas" in lower:
            score += 80
        if "color_map" in lower or "colour_map" in lower:
            score += 30
        if not score:
            continue

        tokens = {
            token for token in re.findall(r"[a-z0-9]+", lower)
            if len(token) >= 3 and token not in generic_words
        }
        # Unity asset names commonly use CamelCase (``GreenSwatch``), which is
        # already lower-cased to ``greenswatch`` here.  Substring matching is
        # intentional for the small, controlled qualifier vocabulary.
        qualifiers = {token for token in specialised_tokens if token in lower}
        matches = qualifiers & context_tokens
        if matches:
            # A specifically named material may deliberately use a specialised
            # swatch (for example a green terrain lookup).
            score += 70 + 10 * len(matches)
        elif qualifiers:
            # Do not let GreenSwatch/MetalSwatch/etc. become the global fallback
            # merely because they sort before the generic sheet.
            score -= 55 + 5 * len(qualifiers)
        else:
            # Unqualified ``Course_Swatch_Texture`` is the safe default for
            # stripped runtime character/dynamic materials.
            score += 35

        # Prefer fewer unmatched qualifiers when scores are otherwise equal.
        scored.append((-score, len(qualifiers - context_tokens), lower, rec))

    scored.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in scored]



def _material_family_core_name(value: Any) -> str:
    """Return a conservative family key for stripped runtime material variants."""
    import re

    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    tokens = [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token]
    variant_suffixes = {
        "character", "characters", "runtime", "instance", "instances",
        "instanced", "clone", "variant", "variants", "shared",
    }
    while len(tokens) >= 2 and tokens[-1] in variant_suffixes:
        tokens.pop()
    while len(tokens) >= 2 and tokens[-1].startswith("lod") and tokens[-1][3:].isdigit():
        tokens.pop()
    return "_".join(tokens)


def _material_family_template_candidates(
    target_mat_rec: Any,
    bundle_index: Any | None,
) -> list[tuple[int, Any, list[dict[str, Any]]]]:
    """Find complete sibling Materials for one stripped runtime Material.

    The match is deliberately strict: the candidate must be a clear base-name
    family of the target and must contain a real base texture slot.
    """
    if target_mat_rec is None or bundle_index is None:
        return []

    target_name = str(getattr(target_mat_rec, "name", "") or "")
    target_lower = target_name.lower()
    target_core = _material_family_core_name(target_name)
    if len(target_core) < 6:
        return []

    records: list[Any] = []
    records.extend((getattr(bundle_index, "objects_by_type", {}) or {}).get("Material", []) or [])
    records.extend((getattr(bundle_index, "external_records_by_type", {}) or {}).get("Material", []) or [])

    target_key = _record_identity_key(target_mat_rec)
    seen: set[tuple[str, int]] = set()
    out: list[tuple[int, Any, list[dict[str, Any]]]] = []
    for candidate in records:
        ckey = _record_identity_key(candidate)
        if ckey == target_key or ckey in seen:
            continue
        seen.add(ckey)

        candidate_name = str(getattr(candidate, "name", "") or "")
        candidate_lower = candidate_name.lower()
        candidate_core = _material_family_core_name(candidate_name)
        if len(candidate_core) < 6:
            continue

        textures = _direct_material_textures(candidate, bundle_index)
        if not any(str(row.get("usage", "")).lower() == "base" for row in textures):
            continue

        if candidate_core == target_core:
            score = 260
        elif target_lower.startswith(candidate_lower + "_") or target_lower.startswith(candidate_lower + "."):
            score = 210
        elif target_core.startswith(candidate_core + "_"):
            score = 170
        else:
            continue

        if _record_source_name(candidate) == _record_source_name(target_mat_rec):
            score += 35
        out.append((score, candidate, textures))

    out.sort(key=lambda row: (-row[0], str(getattr(row[1], "name", "") or "").lower()))
    return out


def _hydrate_stripped_material_family_textures(
    material_bundle: list[dict[str, Any]],
    bundle_index: Any | None,
) -> list[dict[str, Any]]:
    """Recover texture slots from an unambiguous complete sibling Material.

    This is stronger evidence than a global swatch-name fallback.  The selected
    Mesh keeps its own UV0 lookup coordinates, so the donor provides shader/
    texture context without replacing the mesh-authored colour selection.
    """
    if not material_bundle or bundle_index is None:
        return []

    recovered: list[dict[str, Any]] = []
    for mat in material_bundle:
        if mat.get("textures"):
            continue
        target_rec = mat.get("record")
        candidates = _material_family_template_candidates(target_rec, bundle_index)
        if not candidates:
            continue
        best_score, donor, donor_textures = candidates[0]
        if len(candidates) > 1 and candidates[1][0] >= best_score - 10:
            continue

        copied: list[dict[str, Any]] = []
        for source_row in donor_textures:
            row = dict(source_row)
            relation = str(row.get("relation", "") or "Texture")
            row["relation"] = f"{relation} (material family: {getattr(donor, 'name', '-')})"
            row["source"] = "material_family_fallback"
            copied.append(row)
        mat["textures"] = _merge_texture_rows(mat.get("textures") or [], copied)
        if mat.get("base_colour") is None:
            mat["base_colour"] = _material_base_colour(donor)
        recovered.append({
            "material": str(getattr(target_rec, "name", "") or ""),
            "template": str(getattr(donor, "name", "") or ""),
            "template_path_id": getattr(donor, "path_id", None),
            "score": int(best_score),
            "textures": [str(getattr(row.get("record"), "name", "") or "") for row in copied],
            "reason": "stripped material matched a complete sibling material family",
        })
    return recovered


def _hydrate_inferred_palette_texture(
    material_bundle: list[dict[str, Any]],
    bundle_index: Any | None,
    uv_sets: dict[int, list[tuple[float, float]]],
) -> dict[str, Any] | None:
    """Attach a clearly named bundle swatch texture to an empty palette material.

    A small number of Unity runtime materials serialize without their shader or
    texture properties because a script supplies them later.  When the mesh has
    unmistakable repeated palette UV0 points and the material name is palette-
    like, use the bundle's uniquely named swatch/palette texture instead of
    showing neutral fallback grey.
    """
    if not material_bundle or _material_bundle_has_base_texture(material_bundle):
        return None
    lookup = _palette_lookup_uv_info(uv_sets)
    if lookup is None or not _material_names_support_palette_fallback(material_bundle):
        return None
    candidates = _palette_texture_candidates(bundle_index, material_bundle)
    if not candidates:
        return None
    tex_rec = candidates[0]
    row = {
        "record": tex_rec,
        "relation": "inferred palette/swatch texture",
        "usage": "base",
        "source": "palette_uv_fallback",
        "scale": (1.0, 1.0),
        "offset": (0.0, 0.0),
    }
    material_bundle[0].setdefault("textures", []).append(row)
    return {
        "texture": str(getattr(tex_rec, "name", "") or ""),
        "path_id": getattr(tex_rec, "path_id", None),
        "reason": lookup.get("reason"),
    }



def _runtime_palette_name_tokens(value: Any) -> set[str]:
    """Return stable semantic tokens from a runtime palette/material name."""
    import re

    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or ""))
    ignored = {
        "material", "materials", "mat", "texture", "textures", "tex",
        "map", "atlas", "palette", "swatch", "lookup", "lut", "color",
        "colour", "base", "main", "easy", "hard", "default", "shared",
        "runtime", "dynamic", "instance", "instanced", "clone", "lit",
    }
    return {
        token for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 3 and token not in ignored and not token.isdigit()
    }


def _local_textureless_palette_shells(
    record: Any,
    material_bundle: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return local resolved Materials that are clearly named palette shells.

    Some older Unity content keeps the real course texture on a runtime shader or
    MaterialPropertyBlock. The serialized renderer Material is fully resolvable,
    but contains only a neutral colour and a name such as ``*_Swatch_texture``.
    This is different from the external URP/Lit shell handled by the character
    recovery path, so it needs its own evidence gate.
    """
    owner_source = _record_source_name(record)
    shells: list[dict[str, Any]] = []
    for mat in material_bundle or []:
        mat_rec = mat.get("record") if isinstance(mat, dict) else None
        if mat_rec is None:
            continue
        name = str(getattr(mat_rec, "name", "") or "")
        lower = name.lower()
        if not any(marker in lower for marker in ("swatch", "palette")):
            continue
        if any(str(tex.get("usage", "") or "").lower() == "base" for tex in (mat.get("textures") or [])):
            continue
        mat_source = _record_source_name(mat_rec)
        if owner_source and mat_source and owner_source != mat_source:
            continue
        shells.append({
            "bundle_row": mat,
            "record": mat_rec,
            "name": name,
            "path_id": getattr(mat_rec, "path_id", None),
            "source_name": mat_source,
        })
    return shells


def _material_reference_count(mat_rec: Any, bundle_index: Any | None, asset_graph: Any | None) -> int:
    if mat_rec is None or bundle_index is None or asset_graph is None:
        return 0
    try:
        return len(list(asset_graph.used_by(mat_rec, bundle_index) or []))
    except Exception:
        return 0


def _local_palette_colour_template_candidates(
    record: Any,
    target_mat_rec: Any,
    bundle_index: Any | None,
    asset_graph: Any | None,
) -> list[tuple[int, Any, list[dict[str, Any]], dict[str, Any]]]:
    """Rank complete local course-colour Materials for one named palette shell.

    Selection is semantic and deterministic, never alphabetical. A shared course
    token such as ``APark`` is required. Explicit Easy/Hard context wins; without
    it, a generic colour material is preferred, then the most-used local variant.
    This makes ``APark_Easy_Color`` a defensible donor for
    ``B_APark_Swatch_texture`` while keeping unrelated course materials out.
    """
    if target_mat_rec is None or bundle_index is None:
        return []

    import re

    target_name = str(getattr(target_mat_rec, "name", "") or "")
    target_tokens = _runtime_palette_name_tokens(target_name)
    if not target_tokens:
        return []

    context_values = [
        target_name,
        str(getattr(record, "name", "") or ""),
        str(getattr(record, "source_name", "") or ""),
        str(getattr(getattr(record, "source_file", None), "name", "") or ""),
        str(getattr(getattr(bundle_index, "path", None), "name", "") or ""),
    ]
    context = " ".join(context_values).lower()
    explicit_hard = bool(re.search(r"(?:^|[^a-z0-9])hard(?:[^a-z0-9]|$)", context))
    explicit_easy = bool(re.search(r"(?:^|[^a-z0-9])easy(?:[^a-z0-9]|$)", context))
    target_source = _record_source_name(target_mat_rec)

    out: list[tuple[int, Any, list[dict[str, Any]], dict[str, Any]]] = []
    seen: set[tuple[str, int]] = set()
    for candidate in (getattr(bundle_index, "objects_by_type", {}) or {}).get("Material", []) or []:
        key = _record_identity_key(candidate)
        if key in seen or key == _record_identity_key(target_mat_rec):
            continue
        seen.add(key)
        name = str(getattr(candidate, "name", "") or "")
        lower = name.lower()
        if "color" not in lower and "colour" not in lower:
            continue
        textures = _direct_material_textures(candidate, bundle_index)
        if not any(str(row.get("usage", "") or "").lower() == "base" for row in textures):
            continue

        candidate_tokens = _runtime_palette_name_tokens(name)
        overlap = target_tokens & candidate_tokens
        if not overlap:
            continue

        score = 180 * len(overlap)
        score += 120  # explicitly a complete colour material
        if "swatch" in target_name.lower() or "palette" in target_name.lower():
            score += 40
        if target_source and _record_source_name(candidate) == target_source:
            score += 30

        is_easy = bool(re.search(r"(?:^|[^a-z0-9])easy(?:[^a-z0-9]|$)", lower))
        is_hard = bool(re.search(r"(?:^|[^a-z0-9])hard(?:[^a-z0-9]|$)", lower))
        if explicit_hard:
            score += 120 if is_hard else (-80 if is_easy else 25)
        elif explicit_easy:
            score += 120 if is_easy else (-80 if is_hard else 25)
        else:
            # Common/shared animation bundles often contain both variants. A
            # generic donor is strongest; otherwise reference frequency breaks
            # the Easy/Hard tie using actual bundle usage rather than filenames.
            score += 70 if not (is_easy or is_hard) else (35 if is_easy else 0)

        reference_count = _material_reference_count(candidate, bundle_index, asset_graph)
        if reference_count > 0:
            score += min(100, int(round(math.log2(reference_count + 1) * 10.0)))

        out.append((score, candidate, textures, {
            "shared_tokens": sorted(overlap),
            "reference_count": int(reference_count),
            "variant": "hard" if is_hard else ("easy" if is_easy else "generic"),
        }))

    out.sort(key=lambda row: (-row[0], str(getattr(row[1], "name", "") or "").lower()))
    return out


def _hydrate_local_palette_material_shells(
    record: Any,
    material_bundle: list[dict[str, Any]],
    bundle_index: Any | None,
    asset_graph: Any | None,
) -> list[dict[str, Any]]:
    """Hydrate proven local palette shells from one complete course material.

    The original material row/slot remains authoritative. Only its absent saved
    texture properties are supplied by an unambiguous local course-colour donor,
    allowing rigid transform-animated props to preview like the game without
    changing any material that already resolves a usable base texture.
    """
    if not material_bundle or bundle_index is None:
        return []

    recovered: list[dict[str, Any]] = []
    for shell in _local_textureless_palette_shells(record, material_bundle):
        target_rec = shell["record"]
        candidates = _local_palette_colour_template_candidates(
            record, target_rec, bundle_index, asset_graph
        )
        if not candidates:
            continue
        best_score, donor, donor_textures, details = candidates[0]
        second_score = candidates[1][0] if len(candidates) > 1 else -10_000
        if best_score < 330 or second_score >= best_score - 50:
            continue

        copied: list[dict[str, Any]] = []
        for source_row in donor_textures:
            row = dict(source_row)
            relation = str(row.get("relation", "") or "Texture")
            row["relation"] = (
                f"{relation} (local palette material shell recovery: "
                f"{getattr(donor, 'name', '-')})"
            )
            row["source"] = "local_palette_material_shell_fallback"
            copied.append(row)

        bundle_row = shell["bundle_row"]
        bundle_row["textures"] = _merge_texture_rows(bundle_row.get("textures") or [], copied)
        if bundle_row.get("base_colour") is None:
            bundle_row["base_colour"] = _material_base_colour(donor)
        info = {
            "material": str(getattr(target_rec, "name", "") or ""),
            "material_path_id": getattr(target_rec, "path_id", None),
            "template": str(getattr(donor, "name", "") or ""),
            "template_path_id": getattr(donor, "path_id", None),
            "score": int(best_score),
            "second_score": int(second_score),
            "shared_tokens": details.get("shared_tokens", []),
            "template_reference_count": details.get("reference_count", 0),
            "template_variant": details.get("variant", ""),
            "textures": [str(getattr(row.get("record"), "name", "") or "") for row in copied],
            "allow_constant_uv0": True,
            "reason": (
                "resolved local material was a named textureless palette/swatch shell; "
                "one complete same-course colour material won decisively"
            ),
        }
        bundle_row["source"] = "local_palette_material_shell_fallback"
        bundle_row["local_palette_material_recovery"] = info
        recovered.append(info)
    return recovered

def _insert_material_reference(obj_text: str, mtl_filename: str, material_name: str | None) -> str:
    """Add mtllib/usemtl to an OBJ without disturbing UnityPy's vertex data."""
    lines = obj_text.splitlines()
    out: list[str] = []
    inserted_mtllib = False
    inserted_usemtl = False
    for line in lines:
        if not inserted_mtllib and (line.startswith("o ") or line.startswith("v ")):
            out.append(f"mtllib {mtl_filename}")
            inserted_mtllib = True
        if material_name and not inserted_usemtl and line.startswith("f "):
            out.append(f"usemtl {material_name}")
            inserted_usemtl = True
        out.append(line)
    if not inserted_mtllib:
        out.insert(0, f"mtllib {mtl_filename}")
    if material_name and not inserted_usemtl:
        out.append(f"usemtl {material_name}")
    return "\n".join(out) + "\n"


def _texture_usage_kind(relation: str, texture_name: str = "") -> str:
    """Classify a material texture slot into a simple OBJ/MTL-friendly role.

    Unity Shader Graph materials often expose generated slot names such as
    Texture2D_E212F764 rather than friendly names like _BumpMap.  In those
    cases the referenced texture asset name is much more useful, e.g.
    BallNormalMap_Temp or BallsTexture_Emission.
    """
    r = f"{relation or ''} {texture_name or ''}".lower()

    if "normal" in r or "bump" in r or "nrm" in r:
        return "normal"
    if "emiss" in r or "emission" in r or "glow" in r or "illum" in r:
        return "emission"
    if "metal" in r or "rough" in r or "smooth" in r or "mask" in r or "spec" in r:
        return "mask"
    if (
        "base" in r
        or "main" in r
        or "albedo" in r
        or "diffuse" in r
        or "color" in r
        or "colour" in r
        or r.strip() in ("_color",)
    ):
        return "base"
    return "other"


def _pair_key_value(item: Any) -> tuple[Any, Any]:
    if item is None:
        return None, None
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return item[0], item[1]
    for a, b in (("key", "value"), ("first", "second"), ("Key", "Value"), ("m_Key", "m_Value")):
        if hasattr(item, a) and hasattr(item, b):
            try:
                return getattr(item, a), getattr(item, b)
            except Exception:
                pass
    if isinstance(item, dict):
        for a, b in (("key", "value"), ("first", "second"), ("Key", "Value"), ("m_Key", "m_Value")):
            if a in item and b in item:
                return item[a], item[b]
    return None, None


def _material_float(mat_rec: Any, *keys: str) -> float | None:
    """Read a material float property such as _TextureIndex."""
    try:
        data = mat_rec.object.read()
    except Exception:
        return None

    props = _get(data, "m_SavedProperties", "saved_properties", default=None)
    floats = _get(props, "m_Floats", "floats", default=None) if props is not None else None
    wanted = {str(k) for k in keys}
    for item in _as_list(floats):
        key, value = _pair_key_value(item)
        if str(key).strip().strip("\'\"") not in wanted:
            continue
        try:
            return float(value)
        except Exception:
            v = _get(value, "value", "m_Value", "x", "X", default=None)
            try:
                return float(v)
            except Exception:
                return None
    return None


def _material_texture_array_slice_index(mat_rec: Any) -> int:
    """Pick the slice selector used by simple Texture2DArray colour shaders."""
    value = _material_float(
        mat_rec,
        "_TextureIndex",
        "_BaseMapIndex",
        "_MainTexIndex",
        "_ColorIndex",
        "_ColourIndex",
    )
    if value is None:
        return 0
    try:
        return max(0, int(round(float(value))))
    except Exception:
        return 0


def _clean_prop_name(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().strip("'").strip('"')


def _is_empty_texture_pptr(pptr: Any) -> bool:
    pid = _pptr_path_id(pptr)
    return pid is None or int(pid) == 0


def _material_base_colour(mat_rec: Any) -> tuple[float, float, float] | None:
    """Read _BaseColor/_Color for MTL Kd and preview tint fallback."""
    data = _read_record_data(mat_rec)
    if data is None:
        return None
    props = _get(data, "m_SavedProperties", "saved_properties", default=None)
    colours = _get(props, "m_Colors", "colors", default=None) if props is not None else None
    wanted = ("_BaseColor", "_Color", "_Tint")
    found: dict[str, Any] = {}
    for item in _as_list(colours):
        key, value = _pair_key_value(item)
        name = _clean_prop_name(key)
        if name:
            found[name] = value
    for name in wanted:
        value = found.get(name)
        if value is None:
            continue
        r = _get(value, "r", "R", "x", "X", default=None)
        g = _get(value, "g", "G", "y", "Y", default=None)
        b = _get(value, "b", "B", "z", "Z", default=None)
        if r is None and isinstance(value, (list, tuple)) and len(value) >= 3:
            r, g, b = value[0], value[1], value[2]
        try:
            return (max(0.0, min(1.0, float(r))), max(0.0, min(1.0, float(g))), max(0.0, min(1.0, float(b))))
        except Exception:
            continue
    return None


def _vec2_or_default(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    uv = _vec2(value)
    if uv is None:
        return default
    return (float(uv[0]), float(uv[1]))


def _texture_env_transform(env_value: Any) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return Unity Material texture tiling/offset from a TexEnv value."""
    scale = _vec2_or_default(_get(env_value, "m_Scale", "scale", "Scale", default=None), (1.0, 1.0))
    offset = _vec2_or_default(_get(env_value, "m_Offset", "offset", "Offset", default=None), (0.0, 0.0))
    return scale, offset


def _is_identity_uv_transform(scale: tuple[float, float] | None, offset: tuple[float, float] | None) -> bool:
    sx, sy = scale or (1.0, 1.0)
    ox, oy = offset or (0.0, 0.0)
    return abs(float(sx) - 1.0) < 1e-6 and abs(float(sy) - 1.0) < 1e-6 and abs(float(ox)) < 1e-6 and abs(float(oy)) < 1e-6


def _apply_uv_transform(uvs: list[tuple[float, float]], scale: tuple[float, float], offset: tuple[float, float]) -> list[tuple[float, float]]:
    sx, sy = scale
    ox, oy = offset
    out: list[tuple[float, float]] = []
    for u, v in uvs or []:
        try:
            out.append((float(u) * float(sx) + float(ox), float(v) * float(sy) + float(oy)))
        except Exception:
            out.append((u, v))
    return out


def _first_base_texture_row(material_bundle: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for mat in material_bundle or []:
        textures = mat.get("textures") or []
        base = next((t for t in textures if t.get("usage") == "base"), None)
        if base is None and textures:
            base = textures[0]
        if base is not None:
            return mat, base
    return None, None


def _first_texture_row_by_usage(material_bundle: list[dict[str, Any]], usage: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    wanted = str(usage or "").lower()
    for mat in material_bundle or []:
        textures = mat.get("textures") or []
        tex = next((t for t in textures if str(t.get("usage", "")).lower() == wanted), None)
        if tex is not None:
            return mat, tex

    # Defensive fallback for Shader Graph / Amplify materials where the relation
    # name is more reliable than UBE's simple usage classifier.
    if wanted == "normal":
        markers = ("_bumpmap", "_normalmap", "_normal", "bump", "normal", "nrm")
    elif wanted == "base":
        markers = ("_basemap", "_colormap", "_colourmap", "_basecolormap", "_maintex", "_maintexture", "albedo", "diffuse", "base", "color", "colour")
    else:
        markers = (wanted,)

    for mat in material_bundle or []:
        for tex in mat.get("textures") or []:
            rel = str(tex.get("relation", "") or "").lower()
            nm = str(getattr(tex.get("record"), "name", "") or "").lower()
            if any(m in rel or m in nm for m in markers):
                return mat, tex
    return None, None


def _export_uv_transform_for_texture_row(tex_row: dict[str, Any] | None, usage: str) -> dict[str, Any] | None:
    if tex_row is None:
        return None
    scale = tuple(tex_row.get("scale") or (1.0, 1.0))
    offset = tuple(tex_row.get("offset") or (0.0, 0.0))
    if _is_identity_uv_transform(scale, offset):
        return None
    return {
        "scale": (float(scale[0]), float(scale[1])),
        "offset": (float(offset[0]), float(offset[1])),
        "source": "material_texenv",
        "usage": str(usage or ""),
        "texture": str(getattr(tex_row.get("record"), "name", "") or ""),
        "relation": str(tex_row.get("relation", "") or ""),
    }


def _material_name_lower(mat: dict[str, Any] | None) -> str:
    rec = (mat or {}).get("record") if isinstance(mat, dict) else None
    return str(getattr(rec, "name", "") or "").lower()


def _export_uv_transform_for_base(material_bundle: list[dict[str, Any]], uvs: list[tuple[float, float]]) -> dict[str, Any] | None:
    """Return the base-texture UV transform to bake into OBJ vt coordinates.

    Unity applies TexEnv scale/offset in the shader.  OBJ/MTL cannot express this
    reliably, so UBE bakes it into the exported UVs for the base texture.
    """
    mat, base = _first_base_texture_row(material_bundle)
    if base is None or not uvs:
        return None
    scale = tuple(base.get("scale") or (1.0, 1.0))
    offset = tuple(base.get("offset") or (0.0, 0.0))
    source = "material_texenv"

    if _is_identity_uv_transform(scale, offset):
        b = uv_bounds(uvs)
        tex_name = str(getattr(base.get("record"), "name", "") or "").lower()
        mat_name = _material_name_lower(mat)
        looks_avatar_putter = "avatar_texture" in tex_name or "putter" in mat_name or "avatar" in mat_name
        if b and looks_avatar_putter:
            u_min, u_max = float(b.get("u_min", 0.0)), float(b.get("u_max", 0.0))
            v_min, v_max = float(b.get("v_min", 0.0)), float(b.get("v_max", 0.0))
            # Some avatar/putter meshes are authored in -1..+1 UV space and the
            # Amplify shader remaps that to 0..1 before sampling the atlas.
            if u_min < -0.05 and v_min < -0.05 and u_max <= 1.10 and v_max <= 1.10 and (u_max - u_min) > 1.25 and (v_max - v_min) > 1.25:
                scale = (0.5, 0.5)
                offset = (0.5, 0.5)
                source = "inferred_minus1_to_plus1"

    if _is_identity_uv_transform(scale, offset):
        return None
    return {
        "scale": (float(scale[0]), float(scale[1])),
        "offset": (float(offset[0]), float(offset[1])),
        "source": source,
        "texture": str(getattr(base.get("record"), "name", "") or ""),
        "relation": str(base.get("relation", "") or ""),
    }


def _direct_material_textures(mat_rec: Any, bundle_index: Any | None) -> list[dict[str, Any]]:
    """Read texture slots directly from a Material's saved properties.

    The relationship graph is useful for local Mesh -> Material links, but scene
    objects often use external Materials.  In that case the Material inspector can
    see _BaseMap/_ColorMap/_EmisMap directly, so export should use the same data instead of
    depending on a precomputed graph edge.
    """
    data = _read_record_data(mat_rec)
    if data is None:
        return []
    props = _get(data, "m_SavedProperties", "saved_properties", default=None)
    tex_envs = _get(props, "m_TexEnvs", "tex_envs", default=None) if props is not None else None
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, str]] = set()
    for item in _as_list(tex_envs):
        key, value = _pair_key_value(item)
        relation = _clean_prop_name(key) or "Texture"
        texture_pptr = _get(value, "m_Texture", "texture", default=value)
        if _is_empty_texture_pptr(texture_pptr):
            continue
        tex_rec = _resolve_pptr(bundle_index, texture_pptr)
        if tex_rec is None:
            continue
        if getattr(tex_rec, "type_name", "") not in ("Texture2D", "Texture2DArray"):
            continue
        identity = (int(getattr(tex_rec, "path_id", 0)), relation)
        if identity in seen:
            continue
        seen.add(identity)
        scale, offset = _texture_env_transform(value)
        out.append({
            "record": tex_rec,
            "relation": relation,
            "usage": _texture_usage_kind(relation, getattr(tex_rec, "name", "")),
            "source": "material_saved_properties",
            "scale": scale,
            "offset": offset,
        })
    return out


def _merge_texture_rows(existing: list[dict[str, Any]], extra: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    for row in list(existing or []) + list(extra or []):
        rec = row.get("record")
        if rec is None:
            continue
        key = (_record_source_name(rec), int(getattr(rec, "path_id", 0)), str(row.get("relation", "")))
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged


def _record_lookup_by_relationship(bundle_index: Any | None, target_path_id: int | None, target_source_name: str | None = "") -> Any | None:
    if bundle_index is None or target_path_id is None:
        return None
    src = str(target_source_name or "")
    if src:
        rec = getattr(bundle_index, "record_by_source_path_id", {}).get((src, int(target_path_id)))
        if rec is not None:
            return rec
    rec = getattr(bundle_index, "record_by_path_id", {}).get(int(target_path_id))
    if rec is not None:
        return rec
    return getattr(bundle_index, "external_record_by_path_id", {}).get(int(target_path_id))


def _record_identity_key(rec: Any) -> tuple[str, int]:
    return (_record_source_name(rec), int(getattr(rec, "path_id", 0) or 0))


def _texture_row_identity(row: dict[str, Any]) -> tuple[str, int, str]:
    rec = row.get("record")
    return (_record_source_name(rec), int(getattr(rec, "path_id", 0) or 0), str(row.get("relation", "")))



def _material_recovery_context_tokens(record: Any, bundle_index: Any | None) -> set[str]:
    """Return conservative course/source tokens for external material recovery."""
    import re

    values = [
        str(getattr(record, "name", "") or ""),
        str(getattr(record, "source_name", "") or ""),
        str(getattr(getattr(record, "source_file", None), "name", "") or ""),
        str(getattr(getattr(bundle_index, "path", None), "name", "") or ""),
    ]
    ignored = {
        "assets", "asset", "bundle", "common", "shared", "resources",
        "resource", "cab", "mesh", "lod", "level", "scene", "scenes",
        "easy", "hard", "data", "unity3d",
    }
    out: set[str] = set()
    suffixes = ("common", "assets", "asset", "bundle", "shared", "resources")
    for value in values:
        value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
        for token in re.findall(r"[a-z0-9]+", value.lower()):
            if len(token) < 4 or token in ignored or token.isdigit():
                continue
            reduced = token
            changed = True
            while changed:
                changed = False
                for suffix in suffixes:
                    if reduced.endswith(suffix) and len(reduced) > len(suffix) + 3:
                        reduced = reduced[:-len(suffix)]
                        changed = True
                        break
            if len(reduced) >= 4 and reduced not in ignored:
                out.add(reduced)
    return out


def _external_textureless_material_shells(
    record: Any,
    material_bundle: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return resolved-looking external Materials that contain no usable texture.

    Unity projects sometimes resolve a renderer PPtr to a generic material asset
    in a shared package (for example URP's ``Lit`` material), while the actual
    course appearance is supplied at runtime or represented by a complete local
    sibling material.  Such a record is technically resolved, but it is not an
    appearance success for isolated preview/export.

    This helper deliberately requires a different owning source and no base
    texture.  A genuine external material that resolves with a texture remains
    authoritative and never reaches the recovery fallback.
    """
    owner_source = _record_source_name(record)
    owner_file = str(getattr(record, "source_file", "") or "")
    shells: list[dict[str, Any]] = []
    for row in material_bundle or []:
        mat_rec = row.get("record")
        if mat_rec is None:
            continue
        textures = list(row.get("textures") or [])
        if any(str(tex.get("usage", "") or "").lower() == "base" for tex in textures):
            continue
        mat_source = _record_source_name(mat_rec)
        mat_file = str(getattr(mat_rec, "source_file", "") or "")
        different_source = bool(owner_source and mat_source and owner_source != mat_source)
        different_file = bool(owner_file and mat_file and owner_file != mat_file)
        if not (different_source or different_file):
            continue
        shells.append({
            "record": mat_rec,
            "name": str(getattr(mat_rec, "name", "") or ""),
            "path_id": getattr(mat_rec, "path_id", None),
            "source_name": mat_source,
            "source_file": mat_file,
        })
    return shells


def _character_texture_uv_evidence_from_sets(
    uv_sets: dict[int, list[tuple[float, float]]] | None,
) -> dict[str, Any] | None:
    """Return the most convincing Unity UV channel for recovered character colour.

    Most Labyrinth characters use Unity UV0 either as a broad atlas unwrap or as
    a compact repeated palette lookup.  A smaller historical export family uses
    a different convention: UV0 is one constant material/swatch coordinate while
    UV1 contains the complete detailed character unwrap.  MiscGoblin01 is the
    first confirmed example (3,383 vertices, one UV0 point, 3,242 UV1 points).

    We therefore evaluate UV0 first and preserve it whenever it contains useful
    evidence.  Only when UV0 is absent or effectively constant do we consider an
    alternate channel, and that alternate must be a detailed, broad 0..1-domain
    unwrap.  This keeps lightmap/secondary UV guesses conservative while allowing
    textureless external character shells to recover their actual visible map.
    """
    uv_sets = uv_sets or {}

    def analyse(channel: int, uvs: list[tuple[float, float]], *, alternate: bool) -> dict[str, Any] | None:
        try:
            bounds = uv_bounds(uvs) if uvs else None
        except Exception:
            return None
        if len(uvs) < 3 or not bounds:
            return None

        finite: list[tuple[float, float]] = []
        for u, v in uvs:
            try:
                u = float(u)
                v = float(v)
            except Exception:
                continue
            if math.isfinite(u) and math.isfinite(v):
                finite.append((u, v))
        if len(finite) < 3:
            return None

        u_span = float(bounds.get("u_span", 0.0) or 0.0)
        v_span = float(bounds.get("v_span", 0.0) or 0.0)
        area = max(0.0, u_span) * max(0.0, v_span)
        max_span = max(u_span, v_span)
        unique_points = len({(round(u, 6), round(v, 6)) for u, v in finite})
        in_texture_domain = all(-0.05 <= u <= 1.05 and -0.05 <= v <= 1.05 for u, v in finite)
        repeated_ratio = unique_points / max(1, len(finite))

        # Detailed/broad atlas unwrap.  Alternate channels require stronger
        # evidence: many distinct coordinates and substantial coverage in both
        # axes.  This is the MiscGoblin01 UV1 path.
        broad = max_span >= 0.25 and area >= 0.01
        if broad:
            if alternate and not (
                in_texture_domain
                and unique_points >= 128
                and repeated_ratio >= 0.10
                and u_span >= 0.20
                and v_span >= 0.20
            ):
                return None
            return {
                "kind": "alternate_atlas_unwrap" if alternate else "atlas_unwrap",
                "channel": int(channel),
                "vertex_count": len(finite),
                "unique_points": unique_points,
                "bounds": bounds,
                "reason": (
                    f"broad detailed UV{channel} atlas unwrap used because UV0 is absent/constant"
                    if alternate
                    else "broad UV0 atlas unwrap"
                ),
            }

        # Compact multi-swatch palette lookup is accepted only on UV0.  An
        # alternate compact channel is too ambiguous to override the normal
        # material UV convention automatically.
        compact_palette = (
            not alternate
            and in_texture_domain
            and 2 <= unique_points <= 64
            and repeated_ratio <= 0.20
            and u_span >= 0.01
            and v_span >= 0.01
            and max_span >= 0.04
            and area >= 0.0004
        )
        if compact_palette:
            return {
                "kind": "compact_palette_lookup",
                "channel": int(channel),
                "vertex_count": len(finite),
                "unique_points": unique_points,
                "bounds": bounds,
                "reason": "repeated UV0 character palette/swatch lookup points",
            }
        return None

    uv0 = list(uv_sets.get(0) or [])
    primary = analyse(0, uv0, alternate=False)
    if primary is not None:
        return primary

    # Alternate colour UVs are considered only when UV0 is absent or effectively
    # constant.  A useful but merely smaller UV0 must remain authoritative.
    uv0_unique = len({(round(float(u), 6), round(float(v), 6)) for u, v in uv0}) if uv0 else 0
    if uv0 and uv0_unique > 1:
        return None

    for channel in sorted(k for k in uv_sets.keys() if int(k) > 0):
        evidence = analyse(int(channel), list(uv_sets.get(channel) or []), alternate=True)
        if evidence is not None:
            return evidence
    return None


def _mesh_textured_uv_evidence(record: Any) -> dict[str, Any] | None:
    """Describe convincing texture UV evidence for recovered character colour.

    The detector supports three confirmed Unity export layouts:

    * broad UV0 atlas unwraps (Hoggle);
    * compact repeated UV0 palette/swatch points (Labyrinth chickens); and
    * constant UV0 plus a detailed UV1 colour unwrap (MiscGoblin01).

    It is consulted only after a renderer is proven to be a skinned mesh using a
    textureless external material shell and one complete local character material
    wins decisively, so the alternate-channel path is deliberately strict.
    """
    try:
        uv_sets = mesh_uv_channels_from_record(record) or {}
    except Exception:
        return None
    return _character_texture_uv_evidence_from_sets(uv_sets)

def _mesh_has_textured_uv_evidence(record: Any) -> bool:
    """Compatibility wrapper for callers that need only a yes/no answer."""
    return _mesh_textured_uv_evidence(record) is not None


def _recover_unresolved_external_material_template(
    record: Any,
    material_bundle: list[dict[str, Any]],
    bundle_index: Any | None,
    asset_graph: Any | None,
) -> dict[str, Any] | None:
    """Recover a missing external renderer Material from local semantic evidence.

    Some Unity common bundles keep character geometry and a complete local
    character material, while their SkinnedMeshRenderers reference either an
    unavailable runtime material in another CAB *or* a resolved but textureless
    generic shared material shell such as URP/Lit.  In both cases the isolated
    common bundle otherwise displays a valid colourful character as neutral flat
    shading.

    Recovery is intentionally narrow: the mesh must be used by a
    SkinnedMeshRenderer; the external material must be unresolved, or be a
    textureless external shell backed by real atlas or compact palette UV evidence; and one
    complete local character/creature material must win by a wide semantic
    margin.  Genuine resolved textured materials, rigid props, and ambiguous
    Easy/Hard variants remain untouched.
    """
    if record is None or bundle_index is None or asset_graph is None:
        return None
    if _material_bundle_has_base_texture(material_bundle):
        return None

    try:
        outgoing = asset_graph.references(record, bundle_index)
    except Exception:
        outgoing = []
    unresolved = [
        rel for rel in outgoing
        if str(getattr(rel, "target_type", "") or "") == "Material"
        and getattr(rel, "target_path_id", None) not in (None, 0)
        and not bool(getattr(rel, "resolved", False))
    ]
    external_shells = _external_textureless_material_shells(record, material_bundle)
    uv_evidence = _mesh_textured_uv_evidence(record) if external_shells else None
    shell_recovery = bool(external_shells) and uv_evidence is not None
    if not unresolved and not shell_recovery:
        return None

    try:
        incoming = asset_graph.used_by(record, bundle_index)
    except Exception:
        incoming = []
    is_skinned = any(
        str(getattr(rel, "source_type", "") or "") == "SkinnedMeshRenderer"
        for rel in incoming
    )
    if not is_skinned:
        return None

    course_tokens = _material_recovery_context_tokens(record, bundle_index)
    character_markers = (
        "character", "characters", "creature", "creatures", "avatar",
        "actor", "actors", "npc", "fairy", "fairies", "skin", "skinned",
    )
    reject_markers = (
        "navmesh", "blocker", "water", "glass", "flame", "particle",
        "doorway", "terrain", "sky", "cup",
    )

    candidates: list[tuple[int, Any, list[dict[str, Any]], set[str]]] = []
    seen: set[tuple[str, int]] = set()
    for candidate in (getattr(bundle_index, "objects_by_type", {}) or {}).get("Material", []) or []:
        key = _record_identity_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        textures = _direct_material_textures(candidate, bundle_index)
        if not any(str(row.get("usage", "")).lower() == "base" for row in textures):
            continue

        name = str(getattr(candidate, "name", "") or "")
        lower = name.lower()
        if any(marker in lower for marker in reject_markers):
            continue
        candidate_tokens = _material_recovery_context_tokens(candidate, bundle_index)
        overlap = course_tokens & candidate_tokens
        score = 0
        matched: set[str] = set()
        for marker in character_markers:
            if marker in lower:
                matched.add(marker)
        if matched:
            score += 320 + (15 * len(matched))
        else:
            # A skinned character should not silently inherit a generic course,
            # environment or Easy/Hard material merely because it has a texture.
            score -= 80
        if overlap:
            score += 75 * len(overlap)
        if _record_source_name(candidate) == _record_source_name(record):
            score += 25
        if "dynamic" in lower:
            score += 35
        if "easy" in lower or "hard" in lower:
            score -= 25
        candidates.append((score, candidate, textures, matched))

    candidates.sort(key=lambda row: (-row[0], str(getattr(row[1], "name", "") or "").lower()))
    if not candidates:
        return None
    best_score, donor, donor_textures, matched = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else -10_000
    if best_score < 300 or second_score >= best_score - 80:
        return None

    recovered_textures: list[dict[str, Any]] = []
    for source_row in donor_textures:
        row = dict(source_row)
        relation = str(row.get("relation", "") or "Texture")
        row["relation"] = f"{relation} (external character material recovery: {getattr(donor, 'name', '-')})"
        row["source"] = "external_character_material_fallback"
        recovered_textures.append(row)

    external_ids = sorted({
        (int(getattr(rel, "file_id", 0) or 0), int(getattr(rel, "target_path_id", 0) or 0))
        for rel in unresolved
    })
    recovery_kind = "unresolved_external_material" if unresolved else "resolved_external_textureless_shell"
    slot_relation = (
        "Unresolved external Material recovered from local character template"
        if unresolved
        else "Textureless external Material shell recovered from local character template"
    )
    recovery_info = {
        "template": str(getattr(donor, "name", "") or ""),
        "template_path_id": getattr(donor, "path_id", None),
        "score": int(best_score),
        "matched_markers": sorted(matched),
        "recovery_kind": recovery_kind,
        "unresolved_materials": [
            {"file_id": file_id, "path_id": path_id}
            for file_id, path_id in external_ids
        ],
        "external_material_shells": [
            {
                "name": shell.get("name", ""),
                "path_id": shell.get("path_id"),
                "source_name": shell.get("source_name", ""),
                "source_file": shell.get("source_file", ""),
            }
            for shell in external_shells
        ],
        "uv_evidence": uv_evidence,
        "reason": (
            "unresolved external material on a skinned mesh matched one complete local character material"
            if unresolved
            else "resolved external material had no base texture; atlas/palette UV evidence matched one complete local character material"
        ),
    }

    if shell_recovery:
        # Keep the exact renderer material slot/name but hydrate it with the
        # donor's appearance rows. OBJ preview assigns the first renderer slot;
        # merely appending the donor would leave the generic URP/Lit shell first
        # and therefore still render grey even though the right texture had been
        # discovered later in the bundle.
        shell_keys = {
            (str(shell.get("source_name", "") or ""), int(shell.get("path_id", 0) or 0))
            for shell in external_shells
        }
        hydrated = False
        for mat in material_bundle:
            mat_rec = mat.get("record")
            key = (_record_source_name(mat_rec), int(getattr(mat_rec, "path_id", 0) or 0))
            if key not in shell_keys:
                continue
            mat["textures"] = _merge_texture_rows(mat.get("textures") or [], recovered_textures)
            if mat.get("base_colour") is None:
                mat["base_colour"] = _material_base_colour(donor)
            mat["source"] = "external_character_material_shell_fallback"
            mat["slot_relation"] = slot_relation
            mat["external_material_recovery"] = recovery_info
            hydrated = True
        if hydrated:
            return recovery_info

    material_bundle.append({
        "record": donor,
        "slot_relation": slot_relation,
        "textures": recovered_textures,
        "base_colour": _material_base_colour(donor),
        "source": "external_character_material_fallback",
        "external_material_recovery": recovery_info,
    })
    return recovery_info



def _recovered_character_base_uv_channel(
    material_bundle: list[dict[str, Any]],
    requested_uv_channel: int,
) -> dict[str, Any] | None:
    """Return an evidence-backed automatic base-colour UV override.

    The user's U-key selection remains authoritative whenever it is non-zero.
    For the normal default UV0 request, a recovered external character material
    may explicitly prove that the visible colour unwrap lives on UV1 because UV0
    is absent or constant.  In that rare case the temporary preview/export must
    use the proven alternate channel or it will hydrate the right texture but
    still sample one flat texel.
    """
    try:
        requested = max(0, int(requested_uv_channel or 0))
    except Exception:
        requested = 0
    if requested != 0:
        return None

    for mat in material_bundle or []:
        info = mat.get("external_material_recovery") or {}
        evidence = info.get("uv_evidence") or {}
        try:
            channel = int(evidence.get("channel", 0) or 0)
        except Exception:
            channel = 0
        if channel <= 0:
            continue
        if str(evidence.get("kind", "") or "") != "alternate_atlas_unwrap":
            continue
        return {
            "requested_channel": requested,
            "effective_channel": channel,
            "kind": str(evidence.get("kind", "") or ""),
            "reason": str(evidence.get("reason", "") or ""),
            "template": str(info.get("template", "") or ""),
        }
    return None


def _runtime_render_family_tokens(value: Any) -> tuple[list[str], list[str]]:
    """Return (semantic family tokens, stripped authoring suffix tokens).

    Old Unity production assets often keep a visible runtime mesh and a static
    authored counterpart with names such as ``*_showMPS`` and ``*_woodPS``.
    Their spelling/case/punctuation varies, but the stable family name remains
    useful when a renderer intentionally serializes a null Material slot.
    """
    import re

    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or ""))
    tokens = re.findall(r"[a-z]+|\d+", raw.lower())
    stripped: list[str] = []
    removable = {
        "show", "mps", "wood", "metal", "sand", "glass", "colour",
        "color", "wet", "transparent", "trans", "ps", "mesh", "geo",
        "geometry", "runtime", "dynamic", "lod",
    }
    while tokens:
        tail = tokens[-1]
        if tail.isdigit() or tail in removable:
            stripped.append(tokens.pop())
            continue
        break
    return tokens, stripped


def _runtime_render_family_key(value: Any) -> str:
    tokens, _stripped = _runtime_render_family_tokens(value)
    return "".join(tokens)


def _renderer_null_material_slots(renderer_rec: Any) -> list[dict[str, Any]]:
    """Return explicit null Material slots from one Renderer.

    This deliberately distinguishes a real Unity null PPtr (FileID 0, PathID 0)
    from an unresolved external material.  The latter has a non-zero PathID and
    is handled by the existing external-material recovery path.
    """
    data = _read_record_data(renderer_rec)
    if data is None:
        return []
    slots = _as_list(_get(data, "m_Materials", "materials", default=None))
    if not slots:
        return []
    rows: list[dict[str, Any]] = []
    for slot, pptr in enumerate(slots):
        pid = _pptr_path_id(pptr)
        fid = _pptr_file_id(pptr)
        if pid not in (None, 0) or fid not in (None, 0):
            return []
        rows.append({"slot": int(slot), "file_id": fid, "path_id": pid})
    return rows


def _null_material_renderer_contexts_for_mesh(
    mesh_record: Any,
    bundle_index: Any | None,
) -> list[dict[str, Any]]:
    """Find exact renderer contexts that use a Mesh with only null slots."""
    if mesh_record is None or bundle_index is None:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    # MeshFilter + MeshRenderer.
    for mesh_filter in (getattr(bundle_index, "objects_by_type", {}) or {}).get("MeshFilter", []) or []:
        data = _read_record_data(mesh_filter)
        if data is None or not _pptr_points_to_record(
            _get(data, "m_Mesh", "mesh", default=None), mesh_record
        ):
            continue
        go_rec = _owning_gameobject(mesh_filter, bundle_index)
        go_pid = getattr(go_rec, "path_id", None) if go_rec is not None else None
        for renderer in _records_with_gameobject("MeshRenderer", go_pid, bundle_index):
            slots = _renderer_null_material_slots(renderer)
            if not slots:
                continue
            key = _record_identity_key(renderer)
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "renderer": renderer,
                "renderer_type": "MeshRenderer",
                "renderer_name": str(getattr(renderer, "name", "") or ""),
                "renderer_path_id": getattr(renderer, "path_id", None),
                "object": go_rec,
                "object_name": str(getattr(go_rec, "name", "") or "") if go_rec is not None else "",
                "slots": slots,
            })

    # SkinnedMeshRenderer owns both Mesh and Material slots.
    for renderer in (getattr(bundle_index, "objects_by_type", {}) or {}).get("SkinnedMeshRenderer", []) or []:
        data = _read_record_data(renderer)
        if data is None or not _pptr_points_to_record(
            _get(data, "m_Mesh", "mesh", default=None), mesh_record
        ):
            continue
        slots = _renderer_null_material_slots(renderer)
        if not slots:
            continue
        key = _record_identity_key(renderer)
        if key in seen:
            continue
        seen.add(key)
        go_rec = _owning_gameobject(renderer, bundle_index)
        rows.append({
            "renderer": renderer,
            "renderer_type": "SkinnedMeshRenderer",
            "renderer_name": str(getattr(renderer, "name", "") or ""),
            "renderer_path_id": getattr(renderer, "path_id", None),
            "object": go_rec,
            "object_name": str(getattr(go_rec, "name", "") or "") if go_rec is not None else "",
            "slots": slots,
        })
    return rows


def _actual_textured_renderer_materials_for_mesh(
    mesh_record: Any,
    bundle_index: Any | None,
) -> list[dict[str, Any]]:
    """Return complete Materials from renderers that genuinely use a Mesh."""
    if mesh_record is None or bundle_index is None:
        return []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    def add_renderer(renderer: Any, go_rec: Any | None, kind: str) -> None:
        for mat_rec in _renderer_materials_from_record(renderer, bundle_index):
            key = _record_identity_key(mat_rec)
            if key in seen:
                continue
            textures = _direct_material_textures(mat_rec, bundle_index)
            base_rows = [
                row for row in textures
                if str(row.get("usage", "") or "").lower() == "base"
            ]
            if not base_rows:
                continue
            seen.add(key)
            rows.append({
                "material": mat_rec,
                "textures": textures,
                "base_rows": base_rows,
                "renderer": renderer,
                "renderer_kind": kind,
                "object": go_rec,
            })

    for mesh_filter in (getattr(bundle_index, "objects_by_type", {}) or {}).get("MeshFilter", []) or []:
        data = _read_record_data(mesh_filter)
        if data is None or not _pptr_points_to_record(
            _get(data, "m_Mesh", "mesh", default=None), mesh_record
        ):
            continue
        go_rec = _owning_gameobject(mesh_filter, bundle_index)
        go_pid = getattr(go_rec, "path_id", None) if go_rec is not None else None
        for renderer in _records_with_gameobject("MeshRenderer", go_pid, bundle_index):
            add_renderer(renderer, go_rec, "MeshRenderer")

    for renderer in (getattr(bundle_index, "objects_by_type", {}) or {}).get("SkinnedMeshRenderer", []) or []:
        data = _read_record_data(renderer)
        if data is None or not _pptr_points_to_record(
            _get(data, "m_Mesh", "mesh", default=None), mesh_record
        ):
            continue
        add_renderer(renderer, _owning_gameobject(renderer, bundle_index), "SkinnedMeshRenderer")
    return rows



def _null_material_course_palette_consensus_candidates(
    record: Any,
    bundle_index: Any | None,
    asset_graph: Any | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Recover a null renderer from a course-wide colour-texture consensus.

    Tokyo supplied an exact runtime/static mesh-family donor.  Alice's Caucus
    Race is different: all sixteen animated character/stump renderers serialize
    literal null Material slots and there is no second copy of those meshes with
    a saved Material.  The bundle nevertheless keeps several complete Alice
    colour Materials, and every defensible candidate points to the same base
    colour texture.

    This fallback deliberately resolves only the *appearance consensus*:

    * the Mesh must already have passed the caller's explicit-null renderer and
      repeated UV0 palette tests;
    * the Mesh name must carry an authored render suffix such as woodPS/metalPS;
    * candidate Materials must be local course ``Color``/``Colour`` Materials
      with a real base texture;
    * specialised environment/effect Materials are excluded;
    * the winning base-texture group must be decisive; and
    * either at least two independent Materials agree, or one exceptionally
      strong generic course-colour Material stands alone.

    The shader variant may remain ambiguous (Easy versus Dynamic, for example),
    but when all close candidates agree on one texture the visible palette result
    is not ambiguous.  Existing genuine Materials and the exact-family recovery
    remain higher priority.
    """
    if record is None or bundle_index is None:
        return [], None

    target_name = str(getattr(record, "name", "") or "")
    _family_tokens, stripped = _runtime_render_family_tokens(target_name)
    authored_markers = {
        "show", "mps", "wood", "metal", "sand", "glass", "colour",
        "color", "wet", "ps", "runtime", "dynamic",
    }
    if not (authored_markers & set(stripped)):
        return [], None

    course_tokens = _material_recovery_context_tokens(record, bundle_index)
    if not course_tokens:
        return [], None

    reject_markers = (
        "checker", "water", "ocean", "glass", "mist", "steam", "particle",
        "flame", "droplet", "puddle", "bottle", "yarn", "paint", "splat",
        "ice", "heat", "light_ray", "lightray", "bubble", "flowing",
        "spray", "villain", "terrain", "sky", "navmesh", "blocker",
        "normal", "metallic", "mask", "emission", "shadow",
    )

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    target_source = _record_source_name(record)
    for candidate in (getattr(bundle_index, "objects_by_type", {}) or {}).get("Material", []) or []:
        key = _record_identity_key(candidate)
        if key in seen:
            continue
        seen.add(key)

        name = str(getattr(candidate, "name", "") or "")
        lower = name.lower()
        if "color" not in lower and "colour" not in lower:
            continue
        import re
        split_name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
        raw_name_tokens = set(re.findall(r"[a-z0-9]+", split_name.lower()))
        if any(
            token == marker or token.startswith(marker)
            for token in raw_name_tokens
            for marker in reject_markers
        ):
            continue

        candidate_tokens = _runtime_palette_name_tokens(name)
        overlap = course_tokens & candidate_tokens
        if not overlap:
            continue

        textures = _direct_material_textures(candidate, bundle_index)
        base_rows = [
            row for row in textures
            if str(row.get("usage", "") or "").lower() == "base"
            and row.get("record") is not None
        ]
        base_keys = sorted({
            (_record_source_name(row.get("record")), int(getattr(row.get("record"), "path_id", 0) or 0))
            for row in base_rows
        })
        if not base_keys:
            continue

        score = 420 + (120 * len(overlap))
        reasons = [
            "local complete course colour Material",
            f"shared course token(s): {', '.join(sorted(overlap))}",
        ]
        if target_source and _record_source_name(candidate) == target_source:
            score += 50
            reasons.append("same serialized source")
        if "dynamic" in lower and "storybook" not in lower:
            score += 70
            reasons.append("generic dynamic colour variant")
        elif "dynamic" in lower:
            score += 40
            reasons.append("dynamic colour variant")
        if "storybook" in lower and "storybook" not in target_name.lower():
            score -= 25
        if "easy" in lower:
            score += 35
        if "hard" in lower:
            score -= 10

        reference_count = _material_reference_count(candidate, bundle_index, asset_graph)
        if reference_count > 0:
            score += min(80, int(round(math.log2(reference_count + 1) * 8.0)))
            reasons.append(f"used by {reference_count} renderer relationship(s)")

        rows.append({
            "score": int(score),
            "mesh": None,
            "mesh_name": "(course colour-texture consensus)",
            "material": candidate,
            "textures": textures,
            "base_keys": base_keys,
            "renderer": None,
            "object": None,
            "reason": "; ".join(reasons),
            "reference_count": int(reference_count),
        })

    if not rows:
        return [], None

    groups: dict[tuple[tuple[str, int], ...], list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(tuple(row["base_keys"]), []).append(row)

    ranked_groups: list[dict[str, Any]] = []
    for base_key, members in groups.items():
        members.sort(key=lambda row: (-int(row["score"]), str(getattr(row["material"], "name", "") or "").lower()))
        group_score = int(members[0]["score"]) + (35 * max(0, len(members) - 1))
        ranked_groups.append({
            "base_key": base_key,
            "members": members,
            "score": group_score,
        })
    ranked_groups.sort(key=lambda group: (-int(group["score"]), str(group["base_key"])))

    winner = ranked_groups[0]
    runner_score = int(ranked_groups[1]["score"]) if len(ranked_groups) > 1 else -10_000
    winner_members = list(winner["members"])
    best_member_score = int(winner_members[0]["score"])
    material_count = len(winner_members)
    decisive = int(winner["score"]) >= runner_score + 100
    independently_supported = material_count >= 2 or best_member_score >= 650
    if not decisive or not independently_supported:
        return [], None

    info = {
        "course_tokens": sorted(course_tokens),
        "base_keys": [list(key) for key in winner["base_key"]],
        "material_count": material_count,
        "materials": [str(getattr(row["material"], "name", "") or "") for row in winner_members],
        "group_score": int(winner["score"]),
        "runner_group_score": runner_score,
        "margin": int(winner["score"]) - runner_score,
        "reason": (
            "no textured mesh-family donor existed; multiple complete same-course "
            "colour Materials agreed on one base texture"
        ),
    }
    return winner_members, info


def _recover_null_renderer_material_family(
    record: Any,
    material_bundle: list[dict[str, Any]],
    bundle_index: Any | None,
    asset_graph: Any | None,
) -> dict[str, Any] | None:
    """Recover a proven material for a Mesh whose renderer slot is explicitly null.

    Some older/runtime-authored common bundles keep moving pieces with a literal
    ``Material PPtr(0, 0)``.  UBE first looks for the strongest case: a matching
    static/runtime mesh family with one complete saved material.  When no such
    duplicate mesh exists, it can now recover only the visible colour texture
    from a decisive same-course material consensus.

    This path is intentionally strict:

    * the selected Mesh must have an exact renderer context with only null slots;
    * UV0 must be a convincing repeated palette/swatch lookup;
    * exact mesh-family donors remain first priority;
    * the consensus fallback requires authored PS/runtime suffix evidence;
    * specialised environment/effect materials are excluded; and
    * every close winning candidate must lead to the same base texture.

    Genuine, unresolved-external, or already textured materials are untouched.
    """
    if record is None or bundle_index is None or material_bundle:
        return None
    null_contexts = _null_material_renderer_contexts_for_mesh(record, bundle_index)
    if not null_contexts:
        return None

    try:
        uv_sets = mesh_uv_channels_from_record(record) or {}
    except Exception:
        return None
    uv_evidence = _palette_lookup_uv_info(uv_sets)
    if uv_evidence is None:
        return None

    target_name = str(getattr(record, "name", "") or "")
    family_key = _runtime_render_family_key(target_name)
    _target_tokens, target_stripped = _runtime_render_family_tokens(target_name)
    if len(family_key) < 6 or not target_stripped:
        return None

    candidates: list[dict[str, Any]] = []
    recovery_mode = "exact_mesh_family"
    consensus_info: dict[str, Any] | None = None
    target_source = _record_source_name(record)
    for donor_mesh in (getattr(bundle_index, "objects_by_type", {}) or {}).get("Mesh", []) or []:
        if _record_identity_key(donor_mesh) == _record_identity_key(record):
            continue
        donor_name = str(getattr(donor_mesh, "name", "") or "")
        if _runtime_render_family_key(donor_name) != family_key:
            continue
        _donor_tokens, donor_stripped = _runtime_render_family_tokens(donor_name)
        if not donor_stripped:
            continue
        # At least one side must carry a known runtime/static authoring marker;
        # mere punctuation or a numeric suffix is not enough evidence.
        meaningful = {
            "show", "mps", "wood", "metal", "sand", "glass", "colour",
            "color", "wet", "ps", "runtime", "dynamic",
        }
        if not (meaningful & (set(target_stripped) | set(donor_stripped))):
            continue

        for donor_row in _actual_textured_renderer_materials_for_mesh(donor_mesh, bundle_index):
            mat_rec = donor_row["material"]
            textures = donor_row["textures"]
            base_rows = donor_row["base_rows"]
            base_keys = sorted({
                (_record_source_name(row.get("record")), int(getattr(row.get("record"), "path_id", 0) or 0))
                for row in base_rows if row.get("record") is not None
            })
            if not base_keys:
                continue
            score = 700
            reasons = ["exact normalized runtime/static mesh-family match"]
            if target_source and _record_source_name(donor_mesh) == target_source:
                score += 80
                reasons.append("same serialized source")
            if {"wood", "metal", "sand", "glass", "colour", "color", "ps"} & set(donor_stripped):
                score += 45
                reasons.append("donor has authored static/PS suffix")
            if str(donor_row.get("renderer_kind", "")) == "MeshRenderer":
                score += 20
            score += min(40, 5 * len(base_rows))
            candidates.append({
                "score": int(score),
                "mesh": donor_mesh,
                "mesh_name": donor_name,
                "material": mat_rec,
                "textures": textures,
                "base_keys": base_keys,
                "renderer": donor_row.get("renderer"),
                "object": donor_row.get("object"),
                "reason": "; ".join(reasons),
            })

    if not candidates:
        candidates, consensus_info = _null_material_course_palette_consensus_candidates(
            record, bundle_index, asset_graph
        )
        recovery_mode = "course_palette_consensus"
    if not candidates:
        return None

    candidates.sort(key=lambda row: (-int(row["score"]), str(row["mesh_name"]).lower(), str(getattr(row["material"], "name", "")).lower()))
    best = candidates[0]
    best_score = int(best["score"])
    close = [row for row in candidates if int(row["score"]) >= best_score - 50]
    close_base_sets = {tuple(row["base_keys"]) for row in close}
    minimum_score = 740 if recovery_mode == "exact_mesh_family" else 600
    if best_score < minimum_score or len(close_base_sets) > 1:
        return None

    mat_rec = best["material"]
    copied: list[dict[str, Any]] = []
    for source_row in best["textures"]:
        row = dict(source_row)
        relation = str(row.get("relation", "") or "Texture")
        if recovery_mode == "course_palette_consensus":
            row["relation"] = (
                f"{relation} (null renderer course palette consensus: "
                f"{getattr(best['material'], 'name', '-')})"
            )
            row["source"] = "null_renderer_course_palette_consensus"
        else:
            row["relation"] = (
                f"{relation} (null renderer family recovery: {best['mesh_name']})"
            )
            row["source"] = "null_renderer_mesh_family_fallback"
        copied.append(row)

    info = {
        "target_mesh": target_name,
        "target_path_id": getattr(record, "path_id", None),
        "family_key": family_key,
        "null_renderers": [
            {
                "object": row.get("object_name", ""),
                "renderer": row.get("renderer_name", ""),
                "renderer_type": row.get("renderer_type", ""),
                "renderer_path_id": row.get("renderer_path_id"),
                "slots": row.get("slots", []),
            }
            for row in null_contexts
        ],
        "recovery_mode": recovery_mode,
        "template_mesh": best["mesh_name"],
        "template_mesh_path_id": getattr(best.get("mesh"), "path_id", None),
        "template_material": str(getattr(mat_rec, "name", "") or ""),
        "template_material_path_id": getattr(mat_rec, "path_id", None),
        "base_textures": [
            str(getattr(row.get("record"), "name", "") or "")
            for row in copied
            if str(row.get("usage", "") or "").lower() == "base"
        ],
        "score": best_score,
        "candidate_count": len(candidates),
        "close_candidates_same_base_texture": len(close_base_sets) == 1,
        "course_palette_consensus": consensus_info,
        "uv_evidence": uv_evidence,
        "reason": (
            "renderer serialized an explicit null Material slot; multiple complete "
            "same-course colour Materials agreed on one base texture"
            if recovery_mode == "course_palette_consensus"
            else "renderer serialized an explicit null Material slot; matching static "
                 "mesh family supplied one unambiguous complete palette material"
        ),
    }
    material_bundle.append({
        "record": mat_rec,
        "slot_relation": (
            "Material Slot 0 (null renderer course palette consensus)"
            if recovery_mode == "course_palette_consensus"
            else "Material Slot 0 (null renderer mesh-family recovery)"
        ),
        "textures": copied,
        "base_colour": _material_base_colour(mat_rec),
        "source": (
            "null_renderer_course_palette_consensus"
            if recovery_mode == "course_palette_consensus"
            else "null_renderer_mesh_family_fallback"
        ),
        "null_renderer_material_recovery": info,
    })
    return info


def _gather_material_bundle(record, bundle_index, asset_graph) -> list[dict[str, Any]]:
    """Return material records and texture relationships for a mesh export.

    v1.8zf: resolve relationship targets by (source_name, PathID). UnityFS bundles
    can contain multiple internal SerializedFiles with the same PathID. GLB export
    must not turn sharedassets0.assets/Material PathID 2 into level0/InputManager_2.
    """
    if not bundle_index or not asset_graph:
        return []
    out: list[dict[str, Any]] = []
    try:
        mat_rels = asset_graph.references(record, bundle_index)
    except Exception:
        mat_rels = []
    seen_mats: set[tuple[str, int]] = set()
    for rel in mat_rels:
        if rel.target_type != "Material" or rel.target_path_id is None:
            continue
        mat_rec = _record_lookup_by_relationship(bundle_index, rel.target_path_id, getattr(rel, "target_source_name", ""))
        if mat_rec is None or getattr(mat_rec, "type_name", "") != "Material":
            continue
        mkey = _record_identity_key(mat_rec)
        if mkey in seen_mats:
            continue
        seen_mats.add(mkey)
        textures: list[dict[str, Any]] = []
        seen_tex: set[tuple[str, int, str]] = set()

        try:
            tex_rels = asset_graph.references(mat_rec, bundle_index)
        except Exception:
            tex_rels = []
        for tr in tex_rels:
            if tr.target_type not in ("Texture2D", "Texture2DArray") or tr.target_path_id is None:
                continue
            tex_rec = _record_lookup_by_relationship(bundle_index, tr.target_path_id, getattr(tr, "target_source_name", ""))
            if tex_rec is None or getattr(tex_rec, "type_name", "") not in ("Texture2D", "Texture2DArray"):
                continue
            row = {"record": tex_rec, "relation": tr.relationship, "usage": _texture_usage_kind(tr.relationship, getattr(tex_rec, "name", "")), "source": "asset_graph", "scale": (1.0, 1.0), "offset": (0.0, 0.0)}
            tkey = _texture_row_identity(row)
            if tkey in seen_tex:
                continue
            seen_tex.add(tkey)
            textures.append(row)

        # Also read the Material's own saved texture slots directly. This uses
        # source-aware PPtr.deref and is the safest path for object export.
        for row in _direct_material_textures(mat_rec, bundle_index):
            tkey = _texture_row_identity(row)
            if tkey in seen_tex:
                continue
            seen_tex.add(tkey)
            textures.append(row)

        out.append({
            "record": mat_rec,
            "slot_relation": rel.relationship,
            "textures": textures,
            "base_colour": _material_base_colour(mat_rec),
        })

    # v2.3t: a common bundle can contain the complete local character material
    # while a SkinnedMeshRenderer points to a duplicate runtime Material in an
    # unavailable CAB.  Recover only when one semantic character template wins
    # decisively; never guess generic rigid/environment materials.
    _recover_unresolved_external_material_template(record, out, bundle_index, asset_graph)
    return out


def _pptr_path_id(pptr: Any) -> int | None:
    if pptr is None:
        return None
    for name in ("path_id", "pathID", "m_PathID", "PathID"):
        value = _get(pptr, name, default=None)
        if value is not None:
            try:
                return int(value)
            except Exception:
                return None
    return None


def _pptr_file_id(pptr: Any) -> int | None:
    if pptr is None:
        return None
    for name in ("file_id", "fileID", "m_FileID", "FileID"):
        value = _get(pptr, name, default=None)
        if value is not None:
            try:
                return int(value)
            except Exception:
                return None
    return None


def _record_source_name(record: Any) -> str:
    try:
        return str(getattr(record, "source_name", "") or "")
    except Exception:
        return ""


def _pptr_target_source_path_id(pptr: Any) -> tuple[str, int] | None:
    if pptr is None or isinstance(pptr, int):
        return None
    try:
        target = pptr.deref()
        pid = int(getattr(target, "path_id", None))
        src = str(getattr(getattr(target, "assets_file", None), "name", "") or "")
        if src and pid:
            return src, pid
    except Exception:
        pass
    try:
        pid = _pptr_path_id(pptr)
        af = getattr(pptr, "assetsfile", None) or getattr(pptr, "assets_file", None)
        src = str(getattr(af, "name", "") or "")
        if src and pid is not None:
            return src, int(pid)
    except Exception:
        pass
    return None


def _pptr_points_to_record(pptr: Any, rec: Any) -> bool:
    if rec is None:
        return False
    if _pptr_path_id(pptr) != getattr(rec, "path_id", None):
        # External PPtrs can have the target PathID directly; if that differs,
        # it is definitely not the same object.
        return False
    target_key = _pptr_target_source_path_id(pptr)
    rec_src = _record_source_name(rec)
    if target_key is None or not rec_src:
        return True
    return target_key == (rec_src, int(getattr(rec, "path_id", 0)))


def _resolve_pptr(bundle_index: Any | None, pptr_or_pid: Any) -> Any | None:
    if bundle_index is None:
        return None
    if not isinstance(pptr_or_pid, int):
        target_key = _pptr_target_source_path_id(pptr_or_pid)
        if target_key is not None:
            rec = getattr(bundle_index, "record_by_source_path_id", {}).get(target_key)
            if rec is not None:
                return rec
    pid = pptr_or_pid if isinstance(pptr_or_pid, int) else _pptr_path_id(pptr_or_pid)
    if pid is None:
        return None
    rec = getattr(bundle_index, "record_by_path_id", {}).get(pid)
    if rec is not None:
        return rec
    return getattr(bundle_index, "external_record_by_path_id", {}).get(pid)


def _read_record_data(rec: Any) -> Any | None:
    if rec is None:
        return None
    try:
        return rec.object.read()
    except Exception:
        return None


def _component_records_for_gameobject(go_rec: Any, bundle_index: Any | None) -> list[Any]:
    data = _read_record_data(go_rec)
    if data is None:
        return []
    out: list[Any] = []
    for item in _as_list(_get(data, "m_Components", "m_Component", default=None)):
        pptr = _get(item, "component", "m_Component", default=item)
        rec = _resolve_pptr(bundle_index, pptr)
        if rec is not None:
            out.append(rec)
    return out


def _records_with_gameobject(type_name: str, go_pid: int | None, bundle_index: Any | None) -> list[Any]:
    if bundle_index is None or go_pid is None:
        return []
    # Legacy callers pass only a PathID.  Prefer all GameObject records with
    # that PathID, then match each component's PPtr to the exact source file.
    go_records = [r for r in getattr(bundle_index, "objects_by_type", {}).get("GameObject", []) if getattr(r, "path_id", None) == go_pid]
    out: list[Any] = []
    for rec in getattr(bundle_index, "objects_by_type", {}).get(type_name, []):
        data = _read_record_data(rec)
        if data is None:
            continue
        go_pptr = _get(data, "m_GameObject", "game_object", default=None)
        if go_records:
            if any(_pptr_points_to_record(go_pptr, go) for go in go_records):
                out.append(rec)
        elif _pptr_path_id(go_pptr) == go_pid:
            out.append(rec)
    return out


def _owning_gameobject(rec: Any, bundle_index: Any | None) -> Any | None:
    if rec is None:
        return None
    if getattr(rec, "type_name", "") == "GameObject":
        return rec
    data = _read_record_data(rec)
    if data is None:
        return None
    return _resolve_pptr(bundle_index, _get(data, "m_GameObject", "game_object", default=None))


def _is_combined_scene_mesh(mesh_rec: Any | None) -> bool:
    """Detect Unity/MeshBaker style baked combined scene meshes.

    Walkabout-style bundles often keep a named source mesh such as
    8Track_metalPS, but the GameObject's MeshFilter points at
    "Combined Mesh (root: scene) ...".  For single-object inspection that baked
    scene mesh is often the wrong thing to preview/export.
    """
    if mesh_rec is None:
        return False
    name = str(getattr(mesh_rec, "name", "") or "").lower()
    return (
        name.startswith("combined mesh")
        or "combined mesh (root:" in name
        or "combined mesh root" in name
        or "(root: scene)" in name
    )


def _mesh_collider_mesh_records_for_gameobject(go_rec: Any | None, bundle_index: Any | None) -> list[tuple[Any, Any]]:
    """Return [(MeshCollider record, Mesh record)] for a GameObject."""
    out: list[tuple[Any, Any]] = []
    if go_rec is None or bundle_index is None:
        return out
    go_pid = getattr(go_rec, "path_id", None)
    components = _component_records_for_gameobject(go_rec, bundle_index)
    colliders = [c for c in components if getattr(c, "type_name", "") == "MeshCollider"]
    if not colliders:
        colliders = _records_with_gameobject("MeshCollider", go_pid, bundle_index)
    seen: set[tuple[str, int]] = set()
    for col in colliders or []:
        data = _read_record_data(col)
        if data is None:
            continue
        # Unity MeshCollider commonly stores this as m_Mesh.
        mesh_pptr = _get(data, "m_Mesh", "mesh", "m_SharedMesh", "sharedMesh", default=None)
        mesh_rec = _resolve_pptr(bundle_index, mesh_pptr)
        if mesh_rec is None or getattr(mesh_rec, "type_name", "") != "Mesh":
            continue
        key = (_record_source_name(mesh_rec), int(getattr(mesh_rec, "path_id", 0) or 0))
        if key in seen:
            continue
        seen.add(key)
        out.append((col, mesh_rec))
    return out


def _choose_source_mesh_fallback_for_object(
    go_rec: Any | None,
    mesh_filter_mesh: Any | None,
    bundle_index: Any | None,
) -> tuple[Any | None, dict[str, Any]]:
    """Choose a MeshCollider/source mesh when the MeshFilter is a combined scene mesh.

    This is a pragmatic diagnostic/export fallback.  It does not claim the
    collider mesh is always the exact render mesh.  It is used only when the
    MeshFilter mesh is clearly a combined scene mesh and a non-combined collider
    mesh exists on the same GameObject, preferably matching the object name.
    """
    info: dict[str, Any] = {}
    if go_rec is None or bundle_index is None or not _is_combined_scene_mesh(mesh_filter_mesh):
        return None, info

    go_name = str(getattr(go_rec, "name", "") or "")
    candidates = _mesh_collider_mesh_records_for_gameobject(go_rec, bundle_index)
    if not candidates:
        return None, info

    scored: list[tuple[int, Any, Any, list[str]]] = []
    for col, mesh_rec in candidates:
        if _is_combined_scene_mesh(mesh_rec):
            continue
        mesh_name = str(getattr(mesh_rec, "name", "") or "")
        score = 20
        reasons = ["MeshFilter uses a combined scene mesh"]
        s = _context_name_similarity(go_name, mesh_name)
        if s:
            score += s
            reasons.append(f"collider/source mesh name matches object +{s}")
        # Even if the names do not match, a small collider/source mesh is often
        # more useful than a root scene combined mesh for single-object preview.
        scored.append((score, col, mesh_rec, reasons))

    if not scored:
        return None, info

    scored.sort(key=lambda x: x[0], reverse=True)
    score, col, mesh_rec, reasons = scored[0]
    if score < 35:
        return None, info

    info = {
        "mesh_source": "mesh_collider_visual_fallback",
        "fallback_mesh_path_id": getattr(mesh_rec, "path_id", None),
        "fallback_mesh_name": getattr(mesh_rec, "name", ""),
        "fallback_mesh_source_name": _record_source_name(mesh_rec),
        "fallback_collider_path_id": getattr(col, "path_id", None),
        "fallback_reason": "; ".join(reasons),
    }
    return mesh_rec, info



def _object_mesh_and_materials(record: Any, bundle_index: Any | None) -> tuple[Any | None, list[Any], dict[str, Any]]:
    """Resolve the mesh and renderer material slots for an Object/component.

    This is deliberately object-specific.  A raw Mesh can be reused by many
    GameObjects with different renderer materials, so object export should use
    the selected object's Renderer rather than every material ever seen on the
    mesh.
    """
    info: dict[str, Any] = {
        "object_name": getattr(record, "name", "Object"),
        "object_path_id": getattr(record, "path_id", None),
        "object_type": getattr(record, "type_name", ""),
        "mesh_filter_path_id": None,
        "renderer_path_id": None,
        "skinned_renderer_path_id": None,
        "mesh_source": "mesh_filter_or_skinned",
        "mesh_filter_mesh_name": None,
        "mesh_filter_mesh_path_id": None,
        "mesh_filter_mesh_source_name": None,
        # v2.3u: preserve the selected renderer's Material PPtrs even when the
        # target CAB is unavailable.  Object/Animation preview wraps the graph
        # to enforce exact renderer slots; without these rows that wrapper hid
        # the unresolved external material before recovery could see it.
        "material_references": [],
        "renderer_type": None,
        "renderer_name": None,
        "renderer_source_name": None,
    }
    if record is None or bundle_index is None:
        return None, [], info

    type_name = getattr(record, "type_name", "")
    go_rec = _owning_gameobject(record, bundle_index)
    go_pid = getattr(go_rec, "path_id", None) if go_rec is not None else None
    components = _component_records_for_gameobject(go_rec, bundle_index) if go_rec is not None else []

    mesh_filter = record if type_name == "MeshFilter" else next((c for c in components if getattr(c, "type_name", "") == "MeshFilter"), None)
    mesh_renderer = record if type_name == "MeshRenderer" else next((c for c in components if getattr(c, "type_name", "") == "MeshRenderer"), None)
    skinned = record if type_name == "SkinnedMeshRenderer" else next((c for c in components if getattr(c, "type_name", "") == "SkinnedMeshRenderer"), None)

    if mesh_filter is None:
        hits = _records_with_gameobject("MeshFilter", go_pid, bundle_index)
        mesh_filter = hits[0] if hits else None
    if mesh_renderer is None:
        hits = _records_with_gameobject("MeshRenderer", go_pid, bundle_index)
        mesh_renderer = hits[0] if hits else None
    if skinned is None:
        hits = _records_with_gameobject("SkinnedMeshRenderer", go_pid, bundle_index)
        skinned = hits[0] if hits else None

    mesh_rec = None
    material_pptrs: list[Any] = []

    if skinned is not None:
        info["skinned_renderer_path_id"] = getattr(skinned, "path_id", None)
        info["renderer_type"] = "SkinnedMeshRenderer"
        info["renderer_name"] = getattr(skinned, "name", "SkinnedMeshRenderer")
        info["renderer_source_name"] = _record_source_name(skinned)
        data = _read_record_data(skinned)
        if data is not None:
            mesh_rec = _resolve_pptr(bundle_index, _get(data, "m_Mesh", "mesh", default=None))
            material_pptrs = _as_list(_get(data, "m_Materials", "materials", default=None))
    else:
        if mesh_filter is not None:
            info["mesh_filter_path_id"] = getattr(mesh_filter, "path_id", None)
            data = _read_record_data(mesh_filter)
            if data is not None:
                mesh_rec = _resolve_pptr(bundle_index, _get(data, "m_Mesh", "mesh", default=None))
                if mesh_rec is not None:
                    info["mesh_filter_mesh_name"] = getattr(mesh_rec, "name", "")
                    info["mesh_filter_mesh_path_id"] = getattr(mesh_rec, "path_id", None)
                    info["mesh_filter_mesh_source_name"] = _record_source_name(mesh_rec)
        if mesh_renderer is not None:
            info["renderer_path_id"] = getattr(mesh_renderer, "path_id", None)
            info["renderer_type"] = "MeshRenderer"
            info["renderer_name"] = getattr(mesh_renderer, "name", "MeshRenderer")
            info["renderer_source_name"] = _record_source_name(mesh_renderer)
            data = _read_record_data(mesh_renderer)
            if data is not None:
                material_pptrs = _as_list(_get(data, "m_Materials", "materials", default=None))

    materials: list[Any] = []
    seen: set[int] = set()
    material_reference_rows: list[dict[str, Any]] = []
    for slot, pptr in enumerate(material_pptrs):
        raw_pid = _pptr_path_id(pptr)
        raw_fid = _pptr_file_id(pptr)
        mat_rec = _resolve_pptr(bundle_index, pptr)
        resolved_material = mat_rec is not None and getattr(mat_rec, "type_name", "") == "Material"
        material_reference_rows.append({
            "slot": int(slot),
            "file_id": raw_fid,
            "path_id": raw_pid,
            "resolved": bool(resolved_material),
            "target_name": getattr(mat_rec, "name", "External Material") if resolved_material else "External Material",
            "target_source_name": _record_source_name(mat_rec) if resolved_material else "",
        })
        if not resolved_material:
            continue
        pid = getattr(mat_rec, "path_id", None)
        if pid in seen:
            continue
        seen.add(pid)
        materials.append(mat_rec)
    info["material_references"] = material_reference_rows

    # Walkabout/common Unity optimisation case:
    # Object MeshFilter -> "Combined Mesh (root: scene) ..."
    # Object MeshCollider -> original named source mesh
    # Use the source/collider mesh with the object's renderer materials for
    # single-object preview/export, because the combined scene mesh is not a
    # useful isolated object.
    fallback_mesh, fallback_info = _choose_source_mesh_fallback_for_object(go_rec, mesh_rec, bundle_index)
    if fallback_mesh is not None:
        mesh_rec = fallback_mesh
        info.update(fallback_info)

    return mesh_rec, materials, info


def _context_name_key(value: Any) -> str:
    import re
    s = str(value or "").lower()
    s = s.replace("geometry", "geo")
    s = re.sub(r"[^a-z0-9]+", "", s)
    # Remove common authoring/export suffixes, but leave enough text for matching.
    for suffix in ("fillpixels", "texture", "tex", "material", "mat", "lod0", "lod1", "lod2", "mesh", "geo", "geometry"):
        if s.endswith(suffix) and len(s) > len(suffix) + 3:
            s = s[: -len(suffix)]
    return s


def _context_name_similarity(a: Any, b: Any) -> int:
    ak = _context_name_key(a)
    bk = _context_name_key(b)
    if not ak or not bk:
        return 0
    if ak == bk:
        return 70
    if ak in bk or bk in ak:
        return 38
    # Token-ish partial prefix helps names such as ABVRIOPLogoGeo -> ABVRIOPLogoMat.
    n = min(len(ak), len(bk))
    common = 0
    for i in range(n):
        if ak[i] == bk[i]:
            common += 1
        else:
            break
    if common >= 6:
        return 18
    return 0


def _material_texture_names_for_context(mat_rec: Any, bundle_index: Any | None) -> list[str]:
    names: list[str] = []
    try:
        for row in _direct_material_textures(mat_rec, bundle_index):
            tex = row.get("record")
            if tex is not None:
                names.append(str(getattr(tex, "name", "") or ""))
    except Exception:
        pass
    return names


def _context_is_generic_material_name(name: Any) -> bool:
    key = _context_name_key(name)
    bad = (
        "default", "particle", "tmp", "font", "spritesmask", "mask",
        "standard", "diffuse", "unlit", "material", "mat",
    )
    # "ABVRIOPLogoMat" becomes "abvrioplogo", not generic.  Plain "mat" /
    # "material" / "default-particle" should not create confidence.
    if key in ("", "mat", "material"):
        return True
    return any(tok in key for tok in bad)


def _context_material_name_signal(mesh_name: Any, mat_rec: Any, bundle_index: Any | None) -> tuple[int, list[str], bool, list[str]]:
    """Score a material directly against a raw Mesh name.

    Returns: score, reasons, has_real_signal, texture_names.
    """
    mat_name = str(getattr(mat_rec, "name", "") or "")
    score = 0
    reasons: list[str] = []
    texture_names = _material_texture_names_for_context(mat_rec, bundle_index)
    material_generic = _context_is_generic_material_name(mat_name)

    if not material_generic:
        s = _context_name_similarity(mesh_name, mat_name)
        if s:
            add = max(18, s)
            score += add
            reasons.append(f"material name {mat_name} match +{add}")

    texture_signal = False
    seen_tex_keys: set[str] = set()
    unique_texture_names: list[str] = []
    for tex_name in texture_names:
        key = _context_name_key(tex_name)
        if key in seen_tex_keys:
            continue
        seen_tex_keys.add(key)
        unique_texture_names.append(tex_name)

    for tex_name in unique_texture_names:
        s = _context_name_similarity(mesh_name, tex_name)
        if s:
            add = max(22, s + 10)
            score += add
            texture_signal = True
            reasons.append(f"texture name {tex_name} match +{add}")

    if texture_signal:
        score += 14
        reasons.append("texture-name signal +14")
    elif material_generic:
        score -= 32
        reasons.append("generic material with no texture-name signal -32")
    else:
        # A named material matching the mesh is useful, but not as strong as a
        # material whose texture also matches.
        score += 8
        reasons.append("named material signal +8")

    has_signal = (not material_generic and _context_name_similarity(mesh_name, mat_name) > 0) or texture_signal
    return int(score), reasons, bool(has_signal), texture_names


def _material_shader_name_for_context(mat_rec: Any, bundle_index: Any | None) -> str:
    data = _read_record_data(mat_rec)
    if data is None:
        return "-"
    shader_pptr = _get(data, "m_Shader", "shader", default=None)
    pid = _pptr_path_id(shader_pptr)
    shader_rec = _resolve_pptr(bundle_index, shader_pptr)
    if shader_rec is not None:
        name = str(getattr(shader_rec, "name", "") or f"PathID {getattr(shader_rec, 'path_id', '-')}")
        typ = str(getattr(shader_rec, "type_name", "") or "")
        if typ == "Shader":
            return name
        if typ:
            return f"PathID {pid if pid is not None else getattr(shader_rec, 'path_id', '-')} resolved as {typ} '{name}' (not Shader)"
        return f"PathID {pid if pid is not None else getattr(shader_rec, 'path_id', '-')} resolved as '{name}' (type unknown)"
    if pid is not None:
        return f"PathID {pid} (unresolved Shader ref)"
    return "-"


def _material_scalar_text(value: Any) -> str:
    try:
        if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
            parts = [float(getattr(value, k, 0.0)) for k in ("x", "y", "z", "w") if hasattr(value, k)]
            return ", ".join(f"{v:.3f}" for v in parts)
        if isinstance(value, (list, tuple)):
            vals = [float(x) for x in value[:4]]
            return ", ".join(f"{v:.3f}" for v in vals)
        if isinstance(value, float):
            return f"{value:.3f}"
    except Exception:
        pass
    return str(value)


def _material_colour_summary_for_context(mat_rec: Any) -> list[str]:
    data = _read_record_data(mat_rec)
    if data is None:
        return []
    out: list[str] = []
    wanted = {"_Color", "_TintColor", "_EmissionColor", "_MainColor", "_RimColor", "_OutlineColor"}
    try:
        saved = _get(data, "m_SavedProperties", "savedProperties", default=None)
        colors = _get(saved, "m_Colors", "colors", default=None)
        for item in _as_list(colors):
            name = str(_get(item, "first", "name", default="") or "")
            value = _get(item, "second", "value", default=None)
            if not name:
                continue
            if name in wanted or len(out) < 3:
                out.append(f"{name}: {_material_scalar_text(value)}")
            if len(out) >= 6:
                break
    except Exception:
        pass
    return out


def _material_float_summary_for_context(mat_rec: Any) -> list[str]:
    data = _read_record_data(mat_rec)
    if data is None:
        return []
    out: list[str] = []
    wanted = {"_SrcBlend", "_DstBlend", "_ZWrite", "_Cutoff", "_Mode", "_Glossiness", "_EmissionAdd", "_RimPower", "_InvFade"}
    try:
        saved = _get(data, "m_SavedProperties", "savedProperties", default=None)
        floats = _get(saved, "m_Floats", "floats", default=None)
        for item in _as_list(floats):
            name = str(_get(item, "first", "name", default="") or "")
            if name not in wanted:
                continue
            value = _get(item, "second", "value", default=None)
            out.append(f"{name}: {_material_scalar_text(value)}")
    except Exception:
        pass
    return out


def _material_context_debug(mat_rec: Any, bundle_index: Any | None) -> dict[str, Any]:
    return {
        "shader_name": _material_shader_name_for_context(mat_rec, bundle_index),
        "colour_summary": _material_colour_summary_for_context(mat_rec),
        "float_summary": _material_float_summary_for_context(mat_rec),
    }


def _material_texture_rows_for_context(mat_rec: Any, bundle_index: Any | None) -> list[dict[str, Any]]:
    try:
        return list(_direct_material_textures(mat_rec, bundle_index) or [])
    except Exception:
        return []


def _is_candidate_logo_texture_for_mesh(mesh_name: Any, tex_name: Any) -> bool:
    """Tolerant texture-vs-mesh match for names like ABVRIOPLogoGeo -> ABVRIOPLogo_fillpixelsGeo."""
    mk = _context_name_key(mesh_name)
    tk = _context_name_key(tex_name)
    if not mk or not tk:
        return False
    if mk == tk or mk in tk or tk in mk:
        return True
    if len(mk) >= 6 and len(tk) >= 6:
        return mk[:6] == tk[:6]
    return False


def mesh_texture_intersection_candidates(
    mesh_record: Any,
    bundle_index: Any | None,
    asset_graph: Any | None = None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Exact intersection of renderers using this Mesh and their material textures."""
    if mesh_record is None or bundle_index is None:
        return []
    mesh_pid = getattr(mesh_record, "path_id", None)
    if mesh_pid is None:
        return []
    mesh_name = str(getattr(mesh_record, "name", "") or "")

    rows: list[dict[str, Any]] = []

    def add_rows(go_rec: Any | None, renderer_rec: Any, materials: list[Any], kind: str) -> None:
        obj_name = str(getattr(go_rec, "name", "") if go_rec is not None else getattr(renderer_rec, "name", "") or "")
        renderer_name = str(getattr(renderer_rec, "name", "") or "")
        for slot, mat in enumerate(materials):
            mat_name = str(getattr(mat, "name", "") or "")
            tex_rows = _material_texture_rows_for_context(mat, bundle_index)
            if not tex_rows:
                dbg = _material_context_debug(mat, bundle_index)
                rows.append({
                    "score": 4,
                    "kind": "mesh_texture_intersection",
                    "context_record": go_rec if go_rec is not None else renderer_rec,
                    "object_record": go_rec,
                    "renderer_record": renderer_rec,
                    "materials": [mat],
                    "material_names": [mat_name],
                    "texture_names": [],
                    "texture_records": [],
                    "texture_path_ids": [],
                    "shader_names": [dbg.get("shader_name", "-")],
                    "colour_summaries": [dbg.get("colour_summary", [])],
                    "float_summaries": [dbg.get("float_summary", [])],
                    "slot": slot,
                    "property": "-",
                    "reason": "renderer uses this mesh but material texture rows were not resolved",
                    "material_signal": False,
                    "generic_material": _context_is_generic_material_name(mat_name),
                })
                continue

            for row in tex_rows:
                tex = row.get("record")
                if tex is None:
                    continue
                tex_name = str(getattr(tex, "name", "") or "")
                tex_pid = getattr(tex, "path_id", None)
                prop = str(row.get("property") or row.get("relation") or row.get("slot") or row.get("role") or "")
                score = 20
                reasons = ["exact renderer uses this Mesh", f"material slot uses texture PathID {tex_pid}"]
                tex_match = _is_candidate_logo_texture_for_mesh(mesh_name, tex_name)
                mat_match = _context_name_similarity(mesh_name, mat_name)

                if tex_match:
                    score += 85
                    reasons.append(f"texture name {tex_name} matches mesh name")
                if mat_match:
                    add = max(18, mat_match)
                    score += add
                    reasons.append(f"material name {mat_name} matches mesh +{add}")
                if _context_is_generic_material_name(mat_name):
                    if tex_match:
                        score += 8
                        reasons.append("generic material accepted because exact texture matches")
                    else:
                        score -= 20
                        reasons.append("generic material penalty")
                if _context_name_similarity(mesh_name, obj_name):
                    score += 12
                    reasons.append("object name match +12")
                if _context_name_similarity(mesh_name, renderer_name):
                    score += 6
                    reasons.append("renderer name match +6")

                texture_usage = str(row.get("usage", "") or "").lower()
                authoritative_base_texture = texture_usage == "base"
                if authoritative_base_texture:
                    # v2.4h: the renderer's own base-colour slot is structural
                    # evidence, not a name guess.  A raw Mesh may contain words
                    # such as "sand" even though its exact MeshRenderer assigns a
                    # wind/foliage material.  Make that real assignment outrank
                    # global material-name candidates.  Auxiliary noise/normal/
                    # mask textures do not receive this authority boost.
                    score += 70
                    reasons.append(f"renderer base-colour property {prop or '-'} +70")

                dbg = _material_context_debug(mat, bundle_index)
                rows.append({
                    "score": int(score),
                    "kind": "mesh_texture_intersection",
                    "context_record": go_rec if go_rec is not None else renderer_rec,
                    "object_record": go_rec,
                    "renderer_record": renderer_rec,
                    "materials": [mat],
                    "material_names": [mat_name],
                    "texture_names": [tex_name],
                    "texture_records": [tex],
                    "texture_path_ids": [tex_pid],
                    "texture_scales": [row.get("scale", (1.0, 1.0))],
                    "texture_offsets": [row.get("offset", (0.0, 0.0))],
                    "shader_names": [dbg.get("shader_name", "-")],
                    "colour_summaries": [dbg.get("colour_summary", [])],
                    "float_summaries": [dbg.get("float_summary", [])],
                    "slot": slot,
                    "property": prop,
                    "texture_usage": texture_usage,
                    "authoritative_base_texture": bool(authoritative_base_texture),
                    "reason": "; ".join(reasons),
                    "material_signal": bool(tex_match or mat_match),
                    "generic_material": _context_is_generic_material_name(mat_name),
                })

    for mf in getattr(bundle_index, "objects_by_type", {}).get("MeshFilter", []) or []:
        data = _read_record_data(mf)
        if data is None:
            continue
        if not _pptr_points_to_record(_get(data, "m_Mesh", "mesh", default=None), mesh_record):
            continue
        go_rec = _owning_gameobject(mf, bundle_index)
        go_pid = getattr(go_rec, "path_id", None) if go_rec is not None else None
        for renderer in _records_with_gameobject("MeshRenderer", go_pid, bundle_index) or []:
            add_rows(go_rec, renderer, _renderer_materials_from_record(renderer, bundle_index), "mesh_renderer")

    for sr in getattr(bundle_index, "objects_by_type", {}).get("SkinnedMeshRenderer", []) or []:
        data = _read_record_data(sr)
        if data is None:
            continue
        if not _pptr_points_to_record(_get(data, "m_Mesh", "mesh", default=None), mesh_record):
            continue
        go_rec = _owning_gameobject(sr, bundle_index)
        add_rows(go_rec, sr, _renderer_materials_from_record(sr, bundle_index), "skinned")

    def _ctx_sort_key(r: dict[str, Any]) -> tuple[int, int, int]:
        kind = r.get("kind", "")
        priority = 0
        if kind == "mesh_texture_intersection":
            priority = 30
        elif kind == "collider_renderer":
            priority = 25
        elif kind in ("mesh_renderer", "skinned"):
            priority = 20
        elif kind == "semantic_material":
            priority = -10
        authority = 1 if r.get("authoritative_base_texture") else 0
        return (authority, int(r.get("score", 0)), priority)

    rows.sort(key=_ctx_sort_key, reverse=True)
    return rows[:max(1, int(limit or 24))]



def _semantic_material_candidates_for_mesh(
    mesh_record: Any,
    bundle_index: Any | None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Find materials/textures whose names semantically match a raw Mesh.

    This fixes cases where the actual scene renderer has a generic/default
    material, but the project also contains the obvious named material/texture:
      ABVRIOPLogoGeo -> ABVRIOPLogoMat -> ABVRIOPLogo_fillpixelsGeo
    """
    if mesh_record is None or bundle_index is None:
        return []
    mesh_name = str(getattr(mesh_record, "name", "") or "")
    if not _context_name_key(mesh_name):
        return []

    out: list[dict[str, Any]] = []
    for mat in getattr(bundle_index, "objects_by_type", {}).get("Material", []) or []:
        score, reasons, has_signal, tex_names = _context_material_name_signal(mesh_name, mat, bundle_index)
        if not has_signal or score < 38:
            continue
        unique_tex_names: list[str] = []
        seen_tex_keys: set[str] = set()
        for tex_name in tex_names:
            key = _context_name_key(tex_name)
            if key in seen_tex_keys:
                continue
            seen_tex_keys.add(key)
            unique_tex_names.append(tex_name)
        dbg = _material_context_debug(mat, bundle_index)
        out.append({
            "score": int(score),
            "kind": "semantic_material",
            "context_record": mesh_record,
            "object_record": None,
            "renderer_record": None,
            "materials": [mat],
            "material_names": [str(getattr(mat, "name", "") or "")],
            "texture_names": unique_tex_names,
            "shader_names": [dbg.get("shader_name", "-")],
            "colour_summaries": [dbg.get("colour_summary", [])],
            "float_summaries": [dbg.get("float_summary", [])],
            "reason": "; ".join(reasons) if reasons else "material/texture name matches raw Mesh",
            "material_signal": True,
            "generic_material": False,
        })
    out.sort(key=lambda r: int(r.get("score", 0)), reverse=True)
    return out[:max(1, int(limit or 12))]



def _renderer_materials_from_record(renderer_rec: Any, bundle_index: Any | None) -> list[Any]:
    data = _read_record_data(renderer_rec)
    if data is None:
        return []
    out: list[Any] = []
    seen: set[int] = set()
    for pptr in _as_list(_get(data, "m_Materials", "materials", default=None)):
        mat = _resolve_pptr(bundle_index, pptr)
        if mat is None or getattr(mat, "type_name", "") != "Material":
            continue
        pid = getattr(mat, "path_id", None)
        if pid in seen:
            continue
        seen.add(pid)
        out.append(mat)
    return out


def mesh_renderer_context_candidates(
    mesh_record: Any,
    bundle_index: Any | None,
    asset_graph: Any | None = None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Find GameObject/Renderer contexts that use this raw Mesh.

    A Unity Mesh asset does not own its final material.  The material normally
    comes from a MeshRenderer or SkinnedMeshRenderer on a GameObject.  This helper
    builds likely contexts so raw Mesh preview/export can avoid picking a random
    material from the global relationship graph.
    """
    if mesh_record is None or bundle_index is None:
        return []
    mesh_pid = getattr(mesh_record, "path_id", None)
    if mesh_pid is None:
        return []

    mesh_name = str(getattr(mesh_record, "name", "") or "")
    mesh_key = _context_name_key(mesh_name)
    rows: list[dict[str, Any]] = []

    def score_candidate(go_rec: Any | None, renderer_rec: Any, materials: list[Any], kind: str) -> dict[str, Any]:
        obj_name = str(getattr(go_rec, "name", "") if go_rec is not None else getattr(renderer_rec, "name", "") or "")
        renderer_name = str(getattr(renderer_rec, "name", "") or "")
        score = 0
        reasons: list[str] = []

        s = _context_name_similarity(mesh_name, obj_name)
        if s:
            score += s
            reasons.append(f"object name match +{s}")

        s = _context_name_similarity(mesh_name, renderer_name)
        if s:
            score += max(0, s - 10)
            reasons.append(f"renderer name match +{max(0, s - 10)}")

        material_summaries: list[str] = []
        texture_summaries: list[str] = []
        penalty = 0
        material_signal = False
        generic_material = False
        for mat in materials:
            mat_name = str(getattr(mat, "name", "") or "")
            material_summaries.append(mat_name)

            m_score, m_reasons, m_signal, tex_names = _context_material_name_signal(mesh_name, mat, bundle_index)
            if m_signal:
                material_signal = True
            if _context_is_generic_material_name(mat_name):
                generic_material = True
            # For renderer contexts, keep material/texture scoring more modest
            # than the direct semantic-material path, but still meaningful.
            if m_score:
                score += int(m_score * 0.65)
                reasons.extend(m_reasons)

            for tex_name in tex_names:
                if tex_name not in texture_summaries:
                    texture_summaries.append(tex_name)

        if materials:
            score += 8
            reasons.append("has renderer material slots +8")
        else:
            penalty += 22

        if kind == "skinned":
            score += 4

        if generic_material and not material_signal:
            penalty += 30
            reasons.append("generic/default renderer material without texture-name match -30")

        if penalty:
            score -= penalty
            reasons.append(f"material confidence penalty -{penalty}")

        shader_names: list[str] = []
        colour_summaries: list[list[str]] = []
        float_summaries: list[list[str]] = []
        for mat in materials:
            dbg = _material_context_debug(mat, bundle_index)
            shader_names.append(str(dbg.get("shader_name", "-")))
            colour_summaries.append(list(dbg.get("colour_summary", []) or []))
            float_summaries.append(list(dbg.get("float_summary", []) or []))
        return {
            "score": int(score),
            "kind": kind,
            "context_record": go_rec if go_rec is not None else renderer_rec,
            "object_record": go_rec,
            "renderer_record": renderer_rec,
            "materials": materials,
            "material_names": material_summaries,
            "texture_names": texture_summaries,
            "shader_names": shader_names,
            "colour_summaries": colour_summaries,
            "float_summaries": float_summaries,
            "reason": "; ".join(reasons) if reasons else "candidate uses this mesh",
            "material_signal": bool(material_signal),
            "generic_material": bool(generic_material),
        }

    # MeshFilter + MeshRenderer pair.
    for mf in getattr(bundle_index, "objects_by_type", {}).get("MeshFilter", []) or []:
        data = _read_record_data(mf)
        if data is None:
            continue
        if not _pptr_points_to_record(_get(data, "m_Mesh", "mesh", default=None), mesh_record):
            continue
        go_rec = _owning_gameobject(mf, bundle_index)
        go_pid = getattr(go_rec, "path_id", None) if go_rec is not None else None
        renderers = _records_with_gameobject("MeshRenderer", go_pid, bundle_index)
        for renderer in renderers or []:
            materials = _renderer_materials_from_record(renderer, bundle_index)
            rows.append(score_candidate(go_rec, renderer, materials, "mesh_renderer"))

    # SkinnedMeshRenderer owns both mesh + materials.
    for sr in getattr(bundle_index, "objects_by_type", {}).get("SkinnedMeshRenderer", []) or []:
        data = _read_record_data(sr)
        if data is None:
            continue
        if not _pptr_points_to_record(_get(data, "m_Mesh", "mesh", default=None), mesh_record):
            continue
        go_rec = _owning_gameobject(sr, bundle_index)
        materials = _renderer_materials_from_record(sr, bundle_index)
        rows.append(score_candidate(go_rec, sr, materials, "skinned"))

    # MeshCollider/source-mesh bridge.
    # Static-batched/MeshBaker scene objects may use a Combined Mesh in the
    # MeshFilter but keep the original small prop mesh on MeshCollider.  The
    # same GameObject's MeshRenderer still supplies the visual material/atlas.
    for col in getattr(bundle_index, "objects_by_type", {}).get("MeshCollider", []) or []:
        data = _read_record_data(col)
        if data is None:
            continue
        if not _pptr_points_to_record(_get(data, "m_Mesh", "mesh", "m_SharedMesh", "sharedMesh", default=None), mesh_record):
            continue
        go_rec = _owning_gameobject(col, bundle_index)
        go_pid = getattr(go_rec, "path_id", None) if go_rec is not None else None
        renderers = _records_with_gameobject("MeshRenderer", go_pid, bundle_index)
        for renderer in renderers or []:
            materials = _renderer_materials_from_record(renderer, bundle_index)
            row = score_candidate(go_rec, renderer, materials, "collider_renderer")
            obj_match = _context_name_similarity(mesh_name, getattr(go_rec, "name", "") if go_rec is not None else "")
            if obj_match and materials:
                row["score"] = int(row.get("score", 0)) + 55
                row["material_signal"] = True
                reason = str(row.get("reason", "") or "")
                extra = "MeshCollider/source mesh on same GameObject supplies geometry; MeshRenderer supplies material"
                row["reason"] = (reason + "; " + extra).strip("; ")
            row["collider_record"] = col
            rows.append(row)

    # Strongest evidence: actual renderers using this Mesh and the real Texture2D
    # records used by their material slots.
    rows.extend(mesh_texture_intersection_candidates(mesh_record, bundle_index, asset_graph, limit=limit))

    # Also include material/texture-name candidates.  These are not renderer
    # contexts, but they are often the best clue for raw shared Mesh assets.
    rows.extend(_semantic_material_candidates_for_mesh(mesh_record, bundle_index, limit=limit))

    def _context_candidate_sort_key(r: dict[str, Any]) -> tuple[int, int, int]:
        kind = r.get("kind", "")
        priority = 0
        if kind == "mesh_texture_intersection":
            priority = 30
        elif kind in ("mesh_renderer", "skinned"):
            priority = 20
        elif kind == "semantic_material":
            priority = -10
        # Structural renderer evidence is the primary ordering axis.  Scores
        # remain useful for choosing among several real renderer uses.
        authority = 1 if r.get("authoritative_base_texture") else 0
        return (authority, int(r.get("score", 0)), priority)

    rows.sort(key=_context_candidate_sort_key, reverse=True)
    return rows[:max(1, int(limit or 24))]


def best_renderer_context_for_mesh(
    mesh_record: Any,
    bundle_index: Any | None,
    asset_graph: Any | None = None,
    min_score: int = 60,
) -> dict[str, Any] | None:
    rows = mesh_renderer_context_candidates(mesh_record, bundle_index, asset_graph, limit=12)
    if not rows:
        return None

    # v2.4h: first trust the highest-scoring exact renderer base-colour
    # assignment.  This structural evidence must outrank every global name
    # guess, even if an unrelated material happens to match the Mesh name more
    # strongly.  Scores still choose among multiple genuine renderer uses.
    authoritative_rows = [
        row for row in rows
        if row.get("kind") == "mesh_texture_intersection"
        and row.get("authoritative_base_texture")
        and int(row.get("score", 0)) >= int(min_score)
        and any(x and str(x) != "-" for x in (row.get("texture_names") or []))
    ]
    if authoritative_rows:
        authoritative_rows.sort(key=lambda row: int(row.get("score", 0)), reverse=True)
        return authoritative_rows[0]

    # If a semantic material row is top, prefer a near-score real renderer using
    # the same material/texture.  This prevents cases such as HatchlingGeo where
    # a loose name match beats the actual SkinnedMeshRenderer by a few points.
    if rows and rows[0].get("kind") == "semantic_material":
        top = rows[0]
        top_mats = set(top.get("material_names") or [])
        top_tex = set(top.get("texture_names") or [])
        for row in rows[1:8]:
            if row.get("kind") == "semantic_material":
                continue
            if int(row.get("score", 0)) < int(top.get("score", 0)) - 25:
                continue
            row_mats = set(row.get("material_names") or [])
            row_tex = set(row.get("texture_names") or [])
            if (top_mats and top_mats & row_mats) or (top_tex and top_tex & row_tex):
                rows = [row] + [r for r in rows if r is not row]
                break

    for cand in rows:
        if int(cand.get("score", 0)) < int(min_score):
            break
        kind = cand.get("kind")
        textures = [x for x in (cand.get("texture_names") or []) if x and str(x) != "-"]

        # A semantic material name by itself is only a clue.  Do not auto-preview
        # or auto-export it unless the material also resolves a Texture2D.
        if kind == "semantic_material":
            if textures:
                return cand
            continue

        # v2.4h: an exact renderer's recognised base-colour property is
        # authoritative even when the Mesh/Material/Texture names differ.  Name
        # matching remains useful for ambiguous auxiliary textures, but it must
        # never override the material that Unity actually assigned to this Mesh.
        if kind == "mesh_texture_intersection":
            if bool(cand.get("authoritative_base_texture", False)) and textures:
                return cand
            if bool(cand.get("material_signal", False)) and textures:
                return cand
            continue

        # Renderer context fallback: require a material/texture signal.
        if bool(cand.get("material_signal", False)):
            return cand

    return None



class _ObjectMaterialGraph:
    """Small graph wrapper used only for object export/preview.

    For the selected object mesh, it returns exactly that object's renderer
    material slots.  For material -> texture lookups it delegates back to the
    normal AssetGraph.
    """
    def __init__(
        self,
        base_graph: Any,
        mesh_rec: Any,
        material_records: list[Any],
        bundle_index: Any | None,
        object_context: dict[str, Any] | None = None,
    ):
        self.base_graph = base_graph
        self.mesh_rec = mesh_rec
        self.material_records = material_records
        self.bundle_index = bundle_index
        self.object_context = dict(object_context or {})

    def references(self, rec: Any, bundle_index: Any | None = None):
        if (
            rec is not None
            and self.mesh_rec is not None
            and getattr(rec, "path_id", None) == getattr(self.mesh_rec, "path_id", None)
            and (_record_source_name(rec) == _record_source_name(self.mesh_rec) or not _record_source_name(rec) or not _record_source_name(self.mesh_rec))
        ):
            rels = []
            resolved_keys: set[tuple[int | None, int | None]] = set()
            for slot, mat in enumerate(self.material_records):
                ext_bundle = None
                pid = getattr(mat, "path_id", None)
                if bundle_index is not None and pid is not None:
                    ext = getattr(bundle_index, "external_bundle_by_path_id", {}).get(pid)
                    ext_bundle = str(ext) if ext is not None else None
                rels.append(AssetRelationship(
                    source_path_id=getattr(self.mesh_rec, "path_id", 0),
                    source_name=getattr(self.mesh_rec, "name", "Mesh"),
                    source_type="Mesh",
                    target_path_id=pid,
                    target_name=getattr(mat, "name", "Material"),
                    target_type=getattr(mat, "type_name", "Material"),
                    relationship=f"Material Slot {slot}",
                    resolved=True,
                    external_bundle=ext_bundle,
                    source_source_name=_record_source_name(self.mesh_rec),
                    target_source_name=_record_source_name(mat),
                ))
                resolved_keys.add((None, int(pid) if pid is not None else None))

            # v2.3u: exact Object/Animation preview previously discarded unresolved
            # renderer PPtrs because only successfully resolved material_records
            # were represented by this graph wrapper.  Preserve the selected
            # renderer's own unresolved slots so the conservative local character
            # template recovery can run for the actual render instance.
            for row in self.object_context.get("material_references", []) or []:
                if bool(row.get("resolved", False)):
                    continue
                pid = row.get("path_id")
                if pid in (None, 0):
                    continue
                fid = row.get("file_id")
                key = (int(fid) if fid is not None else None, int(pid))
                if key in resolved_keys:
                    continue
                slot = int(row.get("slot", len(rels)) or 0)
                ext_bundle = None
                if bundle_index is not None:
                    ext = getattr(bundle_index, "external_bundle_by_path_id", {}).get(int(pid))
                    ext_bundle = str(ext) if ext is not None else None
                rels.append(AssetRelationship(
                    source_path_id=getattr(self.mesh_rec, "path_id", 0),
                    source_name=getattr(self.mesh_rec, "name", "Mesh"),
                    source_type="Mesh",
                    target_path_id=int(pid),
                    target_name=str(row.get("target_name") or "External Material"),
                    target_type="Material",
                    relationship=f"Material Slot {slot}",
                    file_id=int(fid) if fid is not None else None,
                    resolved=False,
                    external_bundle=ext_bundle,
                    source_source_name=_record_source_name(self.mesh_rec),
                    target_source_name=str(row.get("target_source_name") or ""),
                ))
            return rels
        if self.base_graph is not None:
            try:
                return self.base_graph.references(rec, bundle_index)
            except Exception:
                return []
        return []

    def used_by(self, rec: Any, bundle_index: Any | None = None):
        out = []
        if (
            rec is not None
            and self.mesh_rec is not None
            and getattr(rec, "path_id", None) == getattr(self.mesh_rec, "path_id", None)
            and (_record_source_name(rec) == _record_source_name(self.mesh_rec) or not _record_source_name(rec) or not _record_source_name(self.mesh_rec))
        ):
            renderer_type = str(self.object_context.get("renderer_type") or "")
            renderer_pid = self.object_context.get("skinned_renderer_path_id")
            if renderer_pid is None:
                renderer_pid = self.object_context.get("renderer_path_id")
            if renderer_type and renderer_pid is not None:
                out.append(AssetRelationship(
                    source_path_id=int(renderer_pid),
                    source_name=str(self.object_context.get("renderer_name") or renderer_type),
                    source_type=renderer_type,
                    target_path_id=getattr(self.mesh_rec, "path_id", None),
                    target_name=getattr(self.mesh_rec, "name", "Mesh"),
                    target_type="Mesh",
                    relationship="Renderer mesh",
                    resolved=True,
                    source_source_name=str(self.object_context.get("renderer_source_name") or ""),
                    target_source_name=_record_source_name(self.mesh_rec),
                ))
        if self.base_graph is not None:
            try:
                for rel in self.base_graph.used_by(rec, bundle_index) or []:
                    if rel not in out:
                        out.append(rel)
            except Exception:
                pass
        return out


def _write_mtl(mtl_path: Path, materials: list[dict[str, Any]], texture_files: dict[int, Path]) -> None:
    lines = ["# Exported by UBE", ""]
    for mat in materials:
        mat_rec = mat["record"]
        safe_mat = safe_filename(mat_rec.name, f"material_{mat_rec.path_id}")
        lines.append(f"newmtl {safe_mat}")

        # Pick the first useful base/diffuse texture. Normals/emission are optional extras.
        base = next((t for t in mat["textures"] if t["usage"] == "base"), None)
        if base is None and mat["textures"]:
            base = mat["textures"][0]
        normal = next((t for t in mat["textures"] if t["usage"] == "normal"), None)
        emiss = next((t for t in mat["textures"] if t["usage"] == "emission"), None)
        has_base_texture = bool(base and base["record"].path_id in texture_files)

        base_colour = mat.get("base_colour") or _material_base_colour(mat_rec) or (1.0, 1.0, 1.0)
        try:
            r, g, b = base_colour
            if has_base_texture:
                # Classic OBJ/MTL multiplies Kd with map_Kd.  Unity Shader Graph
                # materials often use _BaseColor/_Color for shader logic rather
                # than a simple texture tint, so keep textured exports neutral by
                # default and preserve the Unity colour as a comment.
                lines.append("Kd 1.000000 1.000000 1.000000")
                lines.append(f"# Unity material colour: {float(r):.6f} {float(g):.6f} {float(b):.6f}")
            else:
                lines.append(f"Kd {float(r):.6f} {float(g):.6f} {float(b):.6f}")
        except Exception:
            lines.append("Kd 1.000000 1.000000 1.000000")
        lines.append("Ka 0.000000 0.000000 0.000000")
        lines.append("Ks 0.000000 0.000000 0.000000")

        if has_base_texture:
            rel = os.path.relpath(texture_files[base["record"].path_id], mtl_path.parent)
            lines.append(f"map_Kd {Path(rel).as_posix()}")
            scale = tuple(base.get("scale") or (1.0, 1.0))
            offset = tuple(base.get("offset") or (0.0, 0.0))
            if not _is_identity_uv_transform(scale, offset):
                lines.append(f"# Unity texture transform for {base.get('relation', 'texture')}: scale {float(scale[0]):.6f} {float(scale[1]):.6f}, offset {float(offset[0]):.6f} {float(offset[1]):.6f} (baked into OBJ UVs)")

        # OBJ/MTL normal-map support is viewer dependent.  Write both the
        # common alias (bump) and the newer/clearer form (map_Bump).
        if normal and normal["record"].path_id in texture_files:
            rel = os.path.relpath(texture_files[normal["record"].path_id], mtl_path.parent)
            tex = Path(rel).as_posix()
            lines.append(f"bump {tex}")
            lines.append(f"map_Bump {tex}")

        # Emission also varies by importer.  Ke gives the material an emissive
        # channel and map_Ke points to the Unity emission texture.
        if emiss and emiss["record"].path_id in texture_files:
            rel = os.path.relpath(texture_files[emiss["record"].path_id], mtl_path.parent)
            lines.append("Ke 1.000000 1.000000 1.000000")
            lines.append(f"map_Ke {Path(rel).as_posix()}")

        # Keep metallic/roughness/mask textures as a readable comment because
        # classic MTL has no single reliable Unity/PBR equivalent for them.
        masks = [t for t in mat["textures"] if t["usage"] == "mask" and t["record"].path_id in texture_files]
        for mask in masks:
            rel = os.path.relpath(texture_files[mask["record"].path_id], mtl_path.parent)
            lines.append(f"# Unity mask/metal/smooth texture: {Path(rel).as_posix()}")
        lines.append("")
    mtl_path.write_text("\n".join(lines), encoding="utf-8")


def export_mesh_record(
    record,
    out_dir: str | Path,
    bundle_index: Any | None = None,
    asset_graph: Any | None = None,
    name_override: str | None = None,
    source_record: Any | None = None,
    source_context: dict[str, Any] | None = None,
    uv_channel: int = 0,
) -> MeshExportResult:
    """Export a UnityPy Mesh record as OBJ.

    v1.2 continues the appearance package when relationships are known:
    OBJ + MTL + referenced texture PNGs + JSON metadata. The geometry path remains
    conservative: if UnityPy cannot expose decoded mesh buffers, UBE skips cleanly.
    """
    root = Path(out_dir)
    mesh_dir = root / "Meshes"
    tex_dir = root / "Textures"
    mat_dir = root / "Materials"
    log_dir = root / "Logs"
    meta_dir = root / "Metadata"
    for d in (mesh_dir, tex_dir, mat_dir, log_dir, meta_dir):
        d.mkdir(parents=True, exist_ok=True)

    # v1.8y: raw Mesh assets do not own their final material.  If a confident
    # GameObject/Renderer context exists, export through that object so preview
    # and OBJ output use the same material/texture Unity would use in the scene.
    if source_record is None and getattr(record, "type_name", "") == "Mesh" and bundle_index is not None:
        ctx = best_renderer_context_for_mesh(record, bundle_index, asset_graph, min_score=60)
        if ctx is not None and ctx.get("kind") == "semantic_material" and ctx.get("materials"):
            # Material-only context: keep the selected Mesh geometry, but force
            # the material/texture bundle to the semantic match.
            asset_graph = _ObjectMaterialGraph(asset_graph, record, list(ctx.get("materials") or []), bundle_index)
            source_record = record
            source_context = {
                "mode": "semantic_material",
                "score": ctx.get("score"),
                "reason": ctx.get("reason", ""),
                "materials": ctx.get("material_names", []),
                "textures": ctx.get("texture_names", []),
            }
            name_override = name_override or getattr(record, "name", None)
        elif ctx is not None and ctx.get("context_record") is not None:
            result = export_object_record(ctx["context_record"], out_dir, bundle_index, asset_graph, uv_channel=uv_channel)
            if result and result.ok:
                try:
                    if result.log_path:
                        with Path(result.log_path).open("a", encoding="utf-8") as f:
                            f.write(
                                "\nRaw Mesh auto renderer context\n"
                                f"Mesh: {getattr(record, 'name', '-')} (PathID {getattr(record, 'path_id', '-')})\n"
                                f"Context: {getattr(ctx['context_record'], 'name', '-')} "
                                f"({getattr(ctx['context_record'], 'type_name', '-')}, PathID {getattr(ctx['context_record'], 'path_id', '-')})\n"
                                f"Score: {ctx.get('score')}\n"
                                f"Reason: {ctx.get('reason', '')}\n"
                            )
                except Exception:
                    pass
                result.message = f"{result.message}; auto renderer context: {getattr(ctx['context_record'], 'name', '-')}"
                return result

    safe = safe_filename(name_override or record.name, f"mesh_{record.path_id}")
    obj_path = mesh_dir / f"{safe}.obj"
    if obj_path.exists():
        obj_path = mesh_dir / f"{safe}__path_{record.path_id}.obj"
    mtl_path = mat_dir / f"{obj_path.stem}.mtl"
    log_path = log_dir / f"{safe}__path_{record.path_id}.log"
    json_path = meta_dir / f"{safe}__path_{record.path_id}.json"

    try:
        data = record.object.read()
    except Exception as e:
        msg = f"Could not read mesh object: {e}"
        log_path.write_text(msg, encoding="utf-8")
        return MeshExportResult(None, log_path, False, msg)

    method = "UnityPy export()"
    user_requested_uv_channel = max(0, int(uv_channel or 0))
    requested_uv_channel = user_requested_uv_channel
    uv_sets = mesh_uv_channels_from_record(record)
    material_bundle = _gather_material_bundle(record, bundle_index, asset_graph)
    null_renderer_material_recovery = _recover_null_renderer_material_family(
        record, material_bundle, bundle_index, asset_graph
    )
    inferred_material_family = _hydrate_stripped_material_family_textures(material_bundle, bundle_index)
    local_palette_material_recovery = _hydrate_local_palette_material_shells(
        record, material_bundle, bundle_index, asset_graph
    )
    inferred_palette_texture = _hydrate_inferred_palette_texture(material_bundle, bundle_index, uv_sets)
    auto_base_uv = _recovered_character_base_uv_channel(material_bundle, user_requested_uv_channel)
    if auto_base_uv is not None:
        requested_uv_channel = int(auto_base_uv["effective_channel"])
    palette_uv_info = _palette_lookup_uv_info(
        uv_sets,
        allow_constant_uv0=bool(local_palette_material_recovery),
    )
    obj_text = _try_unitypy_export(data)
    if obj_text is None:
        obj_text, method = _try_manual_obj(data, safe, requested_uv_channel)

    mixed_point_sampled_uv_recovery = None
    if obj_text is not None and requested_uv_channel == 0:
        try:
            recovery_geo, _recovery_method = _glb_parse_obj_geometry(obj_text)
        except Exception:
            recovery_geo = None
        if recovery_geo:
            uv_sets, mixed_point_sampled_uv_recovery = _mixed_point_sampled_base_uv_recovery(
                record,
                material_bundle,
                uv_sets,
                list(recovery_geo.get("positions") or []),
                list(recovery_geo.get("indices") or []),
                list(recovery_geo.get("source_vertex_indices") or []),
            )
            if mixed_point_sampled_uv_recovery:
                palette_uv_info = mixed_point_sampled_uv_recovery

    # Replace OBJ vt coordinates with UBE-decoded UVs and bake the base texture
    # tiling/offset where Unity uses one.  This keeps preview/export aligned and
    # fixes avatar/putter-style meshes authored in a -1..+1 UV domain.
    #
    # For some skinned meshes UnityPy writes an OBJ whose vt count does not match
    # the raw decoded vertex count.  In that case we still inspect the OBJ's own
    # vt range and bake the inferred material transform directly into those vt
    # lines.  That is the important path for many avatar/putter head_00 meshes.
    uv_transform_info: dict[str, Any] | None = None
    uv_rebuild_mode = ""
    if obj_text is not None:
        replacement = uv_sets.get(requested_uv_channel)
        replaced = False
        if replacement:
            uv_transform_info = _export_uv_transform_for_base(material_bundle, replacement)
            replacement_to_write = replacement
            if uv_transform_info:
                replacement_to_write = _apply_uv_transform(replacement, uv_transform_info["scale"], uv_transform_info["offset"])
            obj_text, replaced = _replace_obj_texture_coordinates(obj_text, replacement_to_write or [])
            if replaced:
                uv_rebuild_mode = "exact_vt_replacement"
            else:
                obj_text, replaced = _rebuild_obj_texture_coordinates_by_vertex(obj_text, replacement_to_write or [])
                if replaced:
                    uv_rebuild_mode = "per_vertex_face_rebuild"

        if not replaced:
            # Fallback: transform the OBJ's own existing vt coordinates.
            existing_uvs = obj_uv_list(obj_text)
            fallback_transform = _export_uv_transform_for_base(material_bundle, existing_uvs)
            if fallback_transform:
                obj_text, transformed = _transform_obj_texture_coordinates(
                    obj_text, fallback_transform["scale"], fallback_transform["offset"]
                )
                if transformed:
                    uv_transform_info = fallback_transform
                    replaced = True

        if replaced:
            suffix = f" + UV transform {uv_transform_info['source']}" if uv_transform_info else ""
            rebuild_suffix = " + per-vertex OBJ UV rebuild" if uv_rebuild_mode == "per_vertex_face_rebuild" else ""
            method = f"UnityPy export() + UBE UV{requested_uv_channel}{rebuild_suffix}{suffix}" if method.startswith("UnityPy") else f"{method} + UBE UV{requested_uv_channel}{rebuild_suffix}{suffix}"
        elif requested_uv_channel > 0:
            method = f"UnityPy export() (UV{requested_uv_channel} replacement unavailable)"
    if not obj_text:
        msg = method
        log_path.write_text(
            "Mesh Export\n"
            f"Name: {record.name}\n"
            f"Path ID: {record.path_id}\n"
            f"Status: SKIPPED\n"
            f"Reason: {msg}\n",
            encoding="utf-8",
        )
        return MeshExportResult(None, log_path, False, msg)

    texture_files: dict[int, Path] = {}
    texture_failures: list[str] = []
    texture_array_slices: dict[int, int] = {}
    for mat in material_bundle:
        slice_index = _material_texture_array_slice_index(mat["record"])
        for tex in mat["textures"]:
            tex_rec = tex["record"]
            if tex_rec.path_id in texture_files:
                continue
            try:
                if getattr(tex_rec, "type_name", "") == "Texture2DArray":
                    dst = export_texture_array_slice_record(tex_rec, root, slice_index)
                    if dst:
                        texture_array_slices[tex_rec.path_id] = slice_index
                else:
                    dst = export_texture_record(tex_rec, root)
            except Exception:
                dst = None
            if dst:
                texture_files[tex_rec.path_id] = dst
            else:
                texture_failures.append(f"{tex_rec.name} ({tex['relation']})")

    material_names: list[str] = []
    if material_bundle:
        for mat in material_bundle:
            material_names.append(safe_filename(mat["record"].name, f"material_{mat['record'].path_id}"))
        _write_mtl(mtl_path, material_bundle, texture_files)
        mtl_rel = Path(os.path.relpath(mtl_path, obj_path.parent)).as_posix()
        obj_text = _insert_material_reference(obj_text, mtl_rel, material_names[0] if material_names else None)

    obj_path.write_text(obj_text, encoding="utf-8", errors="replace")
    v_count = obj_text.count("\nv ") + (1 if obj_text.startswith("v ") else 0)
    f_count = obj_text.count("\nf ") + (1 if obj_text.startswith("f ") else 0)

    uv_channel_info: dict[str, Any] = {}
    for channel_index, channel_uvs in sorted(uv_sets.items()):
        b = uv_bounds(channel_uvs)
        if b:
            uv_channel_info[f"UV{channel_index}"] = b
    exported_uv_bounds = obj_uv_bounds(obj_text)

    atlas_info: list[dict[str, Any]] = []
    try:
        from PIL import Image
    except Exception:
        Image = None
    if Image is not None:
        for mat in material_bundle:
            for tex in mat["textures"]:
                if tex["usage"] not in ("base", "emission", "normal"):
                    continue
                tex_path = texture_files.get(tex["record"].path_id)
                if not tex_path or not Path(tex_path).exists():
                    continue
                try:
                    with Image.open(tex_path) as img:
                        width, height = img.size
                except Exception:
                    continue
                channel_rows = []
                for channel_name, b in uv_channel_info.items():
                    region = atlas_region_from_uv_bounds(b, int(width), int(height))
                    channel_rows.append({"channel": channel_name, "uv_bounds": b, "atlas_region": region})
                atlas_info.append({
                    "texture": tex["record"].name,
                    "usage": tex["usage"],
                    "relation": tex["relation"],
                    "file": str(Path(tex_path).relative_to(root)),
                    "width": int(width),
                    "height": int(height),
                    "channels": channel_rows,
                })

    meta = {
        "ube_version": APP_VERSION,
        "ube_build": APP_BUILD,
        "bundle": str(getattr(bundle_index, "path", "")) if bundle_index is not None else "",
        "source_object": {
            "name": getattr(source_record, "name", "") if source_record is not None else "",
            "type": getattr(source_record, "type_name", "") if source_record is not None else "",
            "path_id": getattr(source_record, "path_id", None) if source_record is not None else None,
            "context": source_context or {},
        },
        "mesh": {
            "name": record.name,
            "path_id": record.path_id,
            "vertices_written": v_count,
            "faces_written": f_count,
            "uv_channel_requested": user_requested_uv_channel,
            "uv_channel_exported": requested_uv_channel,
            "uv_channel_auto_selected": auto_base_uv,
            "uv_bounds_exported": exported_uv_bounds,
            "uv_channels": uv_channel_info,
            "uv_texture_transform": uv_transform_info,
            "uv_obj_rebuild_mode": uv_rebuild_mode,
            "palette_lookup_uv": palette_uv_info,
            "mixed_point_sampled_uv_recovery": mixed_point_sampled_uv_recovery,
            "null_renderer_material_recovery": null_renderer_material_recovery,
            "inferred_material_family": inferred_material_family,
            "local_palette_material_recovery": local_palette_material_recovery,
            "inferred_palette_texture": inferred_palette_texture,
        },
        "export": {
            "obj": str(obj_path.relative_to(root)),
            "mtl": str(mtl_path.relative_to(root)) if material_bundle else "",
            "log": str(log_path.relative_to(root)),
        },
        "materials": [
            {
                "slot": i,
                "slot_relation": mat["slot_relation"],
                "name": mat["record"].name,
                "path_id": mat["record"].path_id,
            }
            for i, mat in enumerate(material_bundle)
        ],
        "textures": [
            {
                "material": mat["record"].name,
                "name": tex["record"].name,
                "path_id": tex["record"].path_id,
                "usage": tex["usage"],
                "relation": tex["relation"],
                "file": str(texture_files[tex["record"].path_id].relative_to(root)) if tex["record"].path_id in texture_files else "",
                "texture_array_slice": texture_array_slices.get(tex["record"].path_id, None),
            }
            for mat in material_bundle
            for tex in mat["textures"]
        ],
        "atlas_insight": atlas_info,
        "texture_export_failures": texture_failures,
    }
    json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    log_path.write_text(
        "Mesh Export\n"
        f"Name: {record.name}\n"
        f"Path ID: {record.path_id}\n"
        f"Method: {method}\n"
        f"OBJ: {obj_path}\n"
        f"MTL: {mtl_path if material_bundle else '-'}\n"
        f"Metadata: {json_path}\n"
        f"Vertices written: {v_count:,}\n"
        f"Faces written: {f_count:,}\n"
        f"Materials: {len(material_bundle):,}\n"
        f"Textures exported: {len(texture_files):,}\n"
        f"UV channel requested: UV{user_requested_uv_channel}\n"
        f"UV channel exported: UV{requested_uv_channel}"
        f"{' (automatic recovered character colour UV)' if auto_base_uv else ''}\n"
        f"UV auto-selection reason: {(auto_base_uv or {}).get('reason', '-')}\n"
        f"UV replacement mode: {uv_rebuild_mode or '-'}\n"
        f"Palette lookup UV detected: {'yes' if palette_uv_info else 'no'}\n"
        f"Mixed point-sampled PS UV recovery: {(mixed_point_sampled_uv_recovery or {}).get('reason', '-')}\n"
        f"Recovered null renderer material: {(null_renderer_material_recovery or {}).get('template_material', '-')} "
        f"via {(null_renderer_material_recovery or {}).get('template_mesh', '-')}\n"
        f"Inherited material family: {', '.join(row.get('template', '-') for row in inferred_material_family) if inferred_material_family else '-'}\n"
        f"Recovered local palette shell: {', '.join(row.get('template', '-') for row in local_palette_material_recovery) if local_palette_material_recovery else '-'}\n"
        f"Inferred palette texture: {(inferred_palette_texture or {}).get('texture', '-')}\n"
        f"UV channels found: {", ".join(sorted(uv_channel_info.keys())) if uv_channel_info else "-"}\n"
        f"Texture export failures: {len(texture_failures):,}\n"
        "Status: SUCCESS\n",
        encoding="utf-8",
    )
    suffix = "with MTL/textures" if material_bundle else "geometry only"
    return MeshExportResult(obj_path, log_path, True, f"Exported OBJ using {method} ({suffix})", mtl_path if material_bundle else None, json_path)


def export_object_record(record, out_dir: str | Path, bundle_index: Any | None = None, asset_graph: Any | None = None, uv_channel: int = 0) -> MeshExportResult:
    """Export the mesh attached to a GameObject/component, using that object's renderer material.

    This is different from exporting a raw Mesh: one Mesh may be reused by many
    GameObjects with different MeshRenderer material slots.  Object export follows
    the selected object's chain:

        Object -> MeshFilter/SkinnedMeshRenderer -> Mesh
        Object -> Renderer -> Material(s) -> Texture/Texture2DArray
    """
    root = Path(out_dir)
    log_dir = root / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    safe_obj = safe_filename(getattr(record, "name", "Object"), f"object_{getattr(record, 'path_id', 'unknown')}")
    log_path = log_dir / f"{safe_obj}__object_export.log"

    mesh_rec, material_records, context = _object_mesh_and_materials(record, bundle_index)
    if mesh_rec is None:
        msg = "No MeshFilter/SkinnedMeshRenderer mesh was found for this object/component."
        log_path.write_text(
            "Object Mesh Export\n"
            f"Object: {getattr(record, 'name', '-') }\n"
            f"Type: {getattr(record, 'type_name', '-') }\n"
            f"Path ID: {getattr(record, 'path_id', '-') }\n"
            f"Status: SKIPPED\nReason: {msg}\n",
            encoding="utf-8",
        )
        return MeshExportResult(None, log_path, False, msg)

    graph = _ObjectMaterialGraph(asset_graph, mesh_rec, material_records, bundle_index, object_context=context)
    result = export_mesh_record(
        mesh_rec,
        out_dir,
        bundle_index,
        graph,
        name_override=safe_obj,
        source_record=record,
        source_context=context,
        uv_channel=uv_channel,
    )

    # Add a small object-export log alongside the normal mesh export log.  This is
    # useful when the object and mesh have different names.
    try:
        lines = [
            "Object Mesh Export",
            f"Object: {getattr(record, 'name', '-') } ({getattr(record, 'type_name', '-')})",
            f"Object Path ID: {getattr(record, 'path_id', '-')}",
            f"Mesh: {getattr(mesh_rec, 'name', '-') } (PathID {getattr(mesh_rec, 'path_id', '-')})",
            f"Materials: {len(material_records)}",
        ]
        for i, mat in enumerate(material_records):
            lines.append(f"  Slot {i}: {getattr(mat, 'name', '-')} (PathID {getattr(mat, 'path_id', '-')})")
        lines.append(f"Result: {result.message}")
        if result.path:
            lines.append(f"OBJ: {result.path}")
        if result.mtl_path:
            lines.append(f"MTL: {result.mtl_path}")
        if result.json_path:
            lines.append(f"Metadata: {result.json_path}")
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass

    return result

# =====================================================
# GLB / glTF binary export
# =====================================================
# Conservative first pass:
# - preserves decoded Unity UVs exactly
# - embeds Texture2D PNGs into the GLB
# - maps Unity base texture -> pbrMetallicRoughness.baseColorTexture
# - maps Unity bump/normal texture -> normalTexture
# - carries _BumpScale -> normalTexture.scale
# - carries Unity texture scale/offset via KHR_texture_transform
# - reuses the same texture PathID once, so shared golf-ball bump maps are not duplicated

_GLTF_ARRAY_BUFFER = 34962
_GLTF_ELEMENT_ARRAY_BUFFER = 34963
_GLTF_FLOAT = 5126
_GLTF_UNSIGNED_SHORT = 5123
_GLTF_UNSIGNED_INT = 5125
_GLTF_TRIANGLES = 4

def _glb_align_blob(blob: bytearray, pad: int = 0) -> None:
    while len(blob) % 4:
        blob.append(pad)

def _glb_pack_floats(values) -> bytes:
    out = bytearray()
    for v in values:
        out.extend(struct.pack("<f", float(v)))
    return bytes(out)

def _glb_pack_uints(values) -> bytes:
    out = bytearray()
    for v in values:
        out.extend(struct.pack("<I", int(v)))
    return bytes(out)


def _glb_pack_ushorts(values) -> bytes:
    out = bytearray()
    for v in values:
        out.extend(struct.pack("<H", max(0, min(65535, int(v)))))
    return bytes(out)

def _glb_flatten_vecs(values, width: int) -> list[float]:
    out: list[float] = []
    for item in values or []:
        for i in range(width):
            out.append(float(item[i]))
    return out

def _glb_unity_uvs_to_gltf(uvs: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Convert Unity/UBE UVs to glTF texture coordinates.

    Unity/UBE atlas insight reports image Y using top-left image space:
        y = (1 - v) * height
    but glTF viewers sample PNGs in top-left texture space for TEXCOORD.
    So GLB export must flip V after any Unity TexEnv scale/offset is baked.
    Without this, golf-ball colour tiles export from the vertically opposite
    atlas row, and the almost-full normal map looks only slightly misaligned.
    """
    out: list[tuple[float, float]] = []
    for u, v in uvs or []:
        try:
            out.append((float(u), 1.0 - float(v)))
        except Exception:
            out.append((u, v))
    return out




def _glb_normal_texture_keeps_unity_v(tex_row: dict[str, Any] | None, material_bundle: list[dict[str, Any]] | None) -> bool:
    """Return whether a normal map should keep raw Unity V in GLB.

    v1.5s added B/N preview debugging and showed the golf-ball normal texture
    aligns perfectly when sampled exactly like the UBE preview: Unity UV0 with
    the preview's image/GL convention.  For GLB/PNG viewers that means the same
    Unity->glTF V conversion used by the colour atlas.

    Keep this hook in place for future shader exceptions, but the verified ball
    path now returns False so normalTexture uses the preview-matched V flip.
    """
    return False

def _glb_uv_lists_equal(a: list[tuple[float, float]], b: list[tuple[float, float]], eps: float = 0.000001) -> bool:
    if len(a or []) != len(b or []):
        return False
    for (au, av), (bu, bv) in zip(a or [], b or []):
        try:
            if abs(float(au) - float(bu)) > eps or abs(float(av) - float(bv)) > eps:
                return False
        except Exception:
            return False
    return True

def _glb_bounds(values, width: int):
    if not values:
        return None, None
    mins = [float("inf")] * width
    maxs = [float("-inf")] * width
    for item in values:
        for i in range(width):
            v = float(item[i])
            mins[i] = min(mins[i], v)
            maxs[i] = max(maxs[i], v)
    return mins, maxs

def _glb_add_buffer_view(blob: bytearray, buffer_views: list[dict], payload: bytes, target: int | None = None) -> int:
    _glb_align_blob(blob, 0)
    offset = len(blob)
    blob.extend(payload)
    view = {
        "buffer": 0,
        "byteOffset": offset,
        "byteLength": len(payload),
    }
    if target is not None:
        view["target"] = target
    buffer_views.append(view)
    return len(buffer_views) - 1

def _glb_add_accessor(
    accessors: list[dict],
    buffer_view: int,
    component_type: int,
    count: int,
    type_name: str,
    mins=None,
    maxs=None,
) -> int:
    acc = {
        "bufferView": buffer_view,
        "byteOffset": 0,
        "componentType": component_type,
        "count": int(count),
        "type": type_name,
    }
    if mins is not None and maxs is not None:
        acc["min"] = [float(x) for x in mins]
        acc["max"] = [float(x) for x in maxs]
    accessors.append(acc)
    return len(accessors) - 1

def _glb_make_glb_bytes(gltf: dict, bin_blob: bytearray) -> bytes:
    gltf["buffers"] = [{"byteLength": len(bin_blob)}]

    json_bytes = json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    while len(json_bytes) % 4:
        json_bytes += b" "

    bin_bytes = bytes(bin_blob)
    while len(bin_bytes) % 4:
        bin_bytes += b"\x00"

    total_len = 12 + 8 + len(json_bytes)
    if bin_bytes:
        total_len += 8 + len(bin_bytes)

    out = bytearray()
    out.extend(struct.pack("<III", 0x46546C67, 2, total_len))  # magic 'glTF', version 2
    out.extend(struct.pack("<I4s", len(json_bytes), b"JSON"))
    out.extend(json_bytes)
    if bin_bytes:
        out.extend(struct.pack("<I4s", len(bin_bytes), b"BIN\x00"))
        out.extend(bin_bytes)
    return bytes(out)

def _glb_obj_index(text: str, length: int) -> int | None:
    if not text:
        return None
    try:
        idx = int(text)
    except Exception:
        return None
    if idx > 0:
        return idx - 1
    if idx < 0:
        return length + idx
    return None

def _glb_parse_obj_geometry(obj_text: str) -> tuple[dict[str, Any] | None, str]:
    src_v: list[tuple[float, float, float]] = []
    src_vt: list[tuple[float, float]] = []
    src_vn: list[tuple[float, float, float]] = []

    out_pos: list[tuple[float, float, float]] = []
    out_uv: list[tuple[float, float] | None] = []
    out_n: list[tuple[float, float, float] | None] = []
    out_source_vi: list[int] = []
    out_idx: list[int] = []
    remap: dict[tuple[int, int | None, int | None], int] = {}

    def mapped_index(token: str) -> int | None:
        parts = token.split("/")
        vi = _glb_obj_index(parts[0] if len(parts) > 0 else "", len(src_v))
        ti = _glb_obj_index(parts[1] if len(parts) > 1 else "", len(src_vt))
        ni = _glb_obj_index(parts[2] if len(parts) > 2 else "", len(src_vn))
        if vi is None or vi < 0 or vi >= len(src_v):
            return None
        key = (vi, ti, ni)
        if key in remap:
            return remap[key]
        remap[key] = len(out_pos)
        out_pos.append(src_v[vi])
        out_uv.append(src_vt[ti] if ti is not None and 0 <= ti < len(src_vt) else None)
        out_n.append(src_vn[ni] if ni is not None and 0 <= ni < len(src_vn) else None)
        out_source_vi.append(int(vi))
        return remap[key]

    for raw in obj_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            if parts[0] == "v" and len(parts) >= 4:
                src_v.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == "vt" and len(parts) >= 3:
                src_vt.append((float(parts[1]), float(parts[2])))
            elif parts[0] == "vn" and len(parts) >= 4:
                src_vn.append((float(parts[1]), float(parts[2]), float(parts[3])))
            elif parts[0] == "f" and len(parts) >= 4:
                face = [mapped_index(tok) for tok in parts[1:]]
                face = [x for x in face if x is not None]
                if len(face) >= 3:
                    # fan triangulate n-gons
                    for i in range(1, len(face) - 1):
                        out_idx.extend([face[0], face[i], face[i + 1]])
        except Exception:
            continue

    if not out_pos or not out_idx:
        return None, "OBJ parser found no usable vertices/faces."

    uvs = [x for x in out_uv if x is not None]
    normals = [x for x in out_n if x is not None]

    geo = {
        "positions": out_pos,
        "indices": out_idx,
        "uvs": uvs if len(uvs) == len(out_pos) else [],
        "normals": normals if len(normals) == len(out_pos) else [],
        "source_vertex_indices": out_source_vi if len(out_source_vi) == len(out_pos) else [],
    }
    return geo, "UnityPy OBJ export parsed for GLB"


def _glb_remap_uv_sets_by_source_vertex(
    uv_sets: dict[int, list[tuple[float, float]]],
    source_vertex_indices: list[int],
    out_len: int,
) -> tuple[dict[int, list[tuple[float, float]]], bool]:
    """Map record-level Unity UV arrays into the vertex order produced by OBJ parsing.

    UnityPy's OBJ exporter may split/deduplicate vertices by v/vt/vn.  If GLB then
    blindly indexes the original Unity UV arrays 0..N, the colour tile can look
    close but the normal/atlas relation is subtly wrong.  This remaps UV0/UV1
    through the OBJ source vertex indices so every GLB vertex keeps the same
    source Unity vertex UVs as the preview/export path.
    """
    if not uv_sets or not source_vertex_indices or len(source_vertex_indices) != int(out_len):
        return uv_sets, False

    out: dict[int, list[tuple[float, float]]] = {}
    changed = False
    for channel, values in uv_sets.items():
        if not values:
            continue
        remapped: list[tuple[float, float]] = []
        ok = True
        for src_i in source_vertex_indices:
            if src_i < 0 or src_i >= len(values):
                ok = False
                break
            remapped.append(values[src_i])
        if ok and len(remapped) == out_len:
            out[channel] = remapped
            changed = True
        else:
            out[channel] = values
    return out if out else uv_sets, changed

def _glb_vec_sub(a, b):
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))

def _glb_vec_dot(a, b) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])

def _glb_vec_cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )

def _glb_vec_len(v) -> float:
    return math.sqrt(max(0.0, _glb_vec_dot(v, v)))

def _glb_vec_norm(v, fallback=(1.0, 0.0, 0.0)):
    ln = _glb_vec_len(v)
    if ln <= 1e-12:
        return fallback
    return (float(v[0]) / ln, float(v[1]) / ln, float(v[2]) / ln)

def _glb_fallback_tangent_for_normal(n):
    n = _glb_vec_norm(n, (0.0, 0.0, 1.0))
    axis = (0.0, 1.0, 0.0) if abs(n[1]) < 0.9 else (1.0, 0.0, 0.0)
    t = _glb_vec_cross(axis, n)
    return _glb_vec_norm(t, (1.0, 0.0, 0.0))

def _glb_generate_tangents(
    positions: list[tuple[float, float, float]],
    normals: list[tuple[float, float, float]],
    uvs: list[tuple[float, float]],
    indices: list[int],
) -> list[tuple[float, float, float, float]]:
    """Generate a simple per-vertex tangent basis for glTF normal maps.

    This is not full MikkTSpace, but it is far better than letting each viewer
    invent a tangent basis.  It also works for the ball OBJ-fallback path where
    UnityPy exports positions/normals/faces but does not expose m_Tangents.
    """
    count = len(positions)
    if count <= 0 or len(normals) < count or len(uvs) < count or len(indices) < 3:
        return []

    tan1 = [[0.0, 0.0, 0.0] for _ in range(count)]
    tan2 = [[0.0, 0.0, 0.0] for _ in range(count)]

    for i in range(0, len(indices) - 2, 3):
        i1, i2, i3 = int(indices[i]), int(indices[i + 1]), int(indices[i + 2])
        if not (0 <= i1 < count and 0 <= i2 < count and 0 <= i3 < count):
            continue
        p1, p2, p3 = positions[i1], positions[i2], positions[i3]
        w1, w2, w3 = uvs[i1], uvs[i2], uvs[i3]

        x1, x2 = p2[0] - p1[0], p3[0] - p1[0]
        y1, y2 = p2[1] - p1[1], p3[1] - p1[1]
        z1, z2 = p2[2] - p1[2], p3[2] - p1[2]
        s1, s2 = w2[0] - w1[0], w3[0] - w1[0]
        t1, t2 = w2[1] - w1[1], w3[1] - w1[1]

        denom = s1 * t2 - s2 * t1
        if abs(denom) <= 1e-12:
            continue
        r = 1.0 / denom
        sdir = ((t2 * x1 - t1 * x2) * r, (t2 * y1 - t1 * y2) * r, (t2 * z1 - t1 * z2) * r)
        tdir = ((s1 * x2 - s2 * x1) * r, (s1 * y2 - s2 * y1) * r, (s1 * z2 - s2 * z1) * r)

        for idx in (i1, i2, i3):
            tan1[idx][0] += sdir[0]; tan1[idx][1] += sdir[1]; tan1[idx][2] += sdir[2]
            tan2[idx][0] += tdir[0]; tan2[idx][1] += tdir[1]; tan2[idx][2] += tdir[2]

    out: list[tuple[float, float, float, float]] = []
    for i in range(count):
        n = _glb_vec_norm(normals[i], (0.0, 0.0, 1.0))
        t_raw = (tan1[i][0], tan1[i][1], tan1[i][2])
        # Gram-Schmidt orthogonalize T against N.
        ndott = _glb_vec_dot(n, t_raw)
        t = (t_raw[0] - n[0] * ndott, t_raw[1] - n[1] * ndott, t_raw[2] - n[2] * ndott)
        if _glb_vec_len(t) <= 1e-10:
            t = _glb_fallback_tangent_for_normal(n)
        else:
            t = _glb_vec_norm(t, _glb_fallback_tangent_for_normal(n))
        b = (tan2[i][0], tan2[i][1], tan2[i][2])
        sign = -1.0 if _glb_vec_dot(_glb_vec_cross(n, t), b) < 0.0 else 1.0
        out.append((float(t[0]), float(t[1]), float(t[2]), float(sign)))
    return out

def _glb_geometry_from_mesh_data(
    data: Any,
    uv_channel: int = 0,
    uv_sets: dict[int, list[tuple[float, float]]] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    vertices = _normalise_vertices(_get(data, "vertices", "m_Vertices", "vertexes", default=None))
    normals = _normalise_vertices(_get(data, "normals", "m_Normals", default=None))
    tangents = _normalise_tangents(_get(data, "tangents", "m_Tangents", "m_Tangent", default=None))
    # Important: for modern/streamed Unity meshes, UV1/UV2 may only be available
    # through the record-level streamed vertex data.  OBJ preview/export already
    # uses mesh_uv_channels_from_record(record); GLB must use the same decoded UV
    # map or the export falls back to UV0 and shows the whole atlas on golf balls.
    uv_sets = uv_sets if uv_sets is not None else mesh_uv_channels_from_data(data)
    requested_uv_channel = max(0, int(uv_channel or 0))
    uvs = uv_sets.get(requested_uv_channel) or uv_sets.get(0) or []
    faces = _normalise_faces(_get(data, "faces", "triangles", "indices", "m_Indices", default=None))

    if vertices and faces:
        indices: list[int] = []
        for a, b, c in faces:
            indices.extend([int(a), int(b), int(c)])
        return {
            "positions": vertices,
            "indices": indices,
            "uvs": uvs if len(uvs) >= len(vertices) else [],
            "normals": normals if len(normals) >= len(vertices) else [],
            "tangents": tangents if len(tangents) >= len(vertices) else [],
        }, "decoded UnityPy mesh attributes"

    obj_text = _try_unitypy_export(data)
    if obj_text:
        geo, msg = _glb_parse_obj_geometry(obj_text)
        if geo and tangents and geo.get("source_vertex_indices"):
            src = geo.get("source_vertex_indices") or []
            try:
                remapped_tangents = [tangents[int(i)] for i in src]
            except Exception:
                remapped_tangents = []
            if len(remapped_tangents) == len(geo.get("positions", [])):
                geo["tangents"] = remapped_tangents
                msg += " + remapped Unity tangents"
        return geo, msg

    return None, "No decoded mesh geometry was available for GLB."

def _glb_pair_key_value(item: Any) -> tuple[Any, Any]:
    # Prefer the existing UBE helper when present.
    try:
        return _pair_key_value(item)  # type: ignore[name-defined]
    except Exception:
        pass

    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return item[0], item[1]

    for k_name, v_name in (
        ("first", "second"),
        ("key", "value"),
        ("m_First", "m_Second"),
        ("name", "value"),
    ):
        k = _get(item, k_name, default=None)
        v = _get(item, v_name, default=None)
        if k is not None:
            return k, v
    return None, None

def _glb_clean_prop_name(value: Any) -> str:
    text = str(value) if value is not None else ""
    return text.strip().strip("'").strip('"')

def _glb_float_value(value: Any) -> float | None:
    for attr in ("data", "value", "m_Data"):
        v = _get(value, attr, default=None)
        if v is not None:
            value = v
            break
    try:
        return float(value)
    except Exception:
        return None

def _glb_material_float(mat_rec: Any, keys: tuple[str, ...], default: float) -> float:
    data = _read_record_data(mat_rec)
    props = _get(data, "m_SavedProperties", "saved_properties", default=None)
    if props is None:
        return float(default)

    wanted = {k.lower() for k in keys}
    floats = _as_list(_get(props, "m_Floats", "floats", default=None))
    for item in floats:
        k, v = _glb_pair_key_value(item)
        if _glb_clean_prop_name(k).lower() in wanted:
            fv = _glb_float_value(v)
            if fv is not None:
                return fv
    return float(default)

def _glb_pair2(value: Any, default: tuple[float, float]) -> tuple[float, float]:
    if value is None:
        return default
    if hasattr(value, "x") and hasattr(value, "y"):
        try:
            return (float(value.x), float(value.y))
        except Exception:
            return default
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (float(value[0]), float(value[1]))
        except Exception:
            return default
    return default

def _glb_texture_transform(tex_row: dict[str, Any]) -> dict[str, Any] | None:
    scale = _glb_pair2(tex_row.get("scale"), (1.0, 1.0))
    offset = _glb_pair2(tex_row.get("offset"), (0.0, 0.0))

    if (
        abs(scale[0] - 1.0) < 0.000001 and
        abs(scale[1] - 1.0) < 0.000001 and
        abs(offset[0]) < 0.000001 and
        abs(offset[1]) < 0.000001
    ):
        return None

    return {
        "offset": [float(offset[0]), float(offset[1])],
        "scale": [float(scale[0]), float(scale[1])],
    }

def _glb_texture_info(
    tex_index: int,
    tex_row: dict[str, Any],
    extensions_used: set[str],
    tex_coord: int = 0,
    include_transform: bool = True,
) -> dict[str, Any]:
    info = {"index": int(tex_index), "texCoord": int(tex_coord)}
    if include_transform:
        transform = _glb_texture_transform(tex_row)
        if transform:
            info["extensions"] = {"KHR_texture_transform": transform}
            extensions_used.add("KHR_texture_transform")
    return info

def _glb_pick_texture(mat: dict[str, Any], usage: str) -> dict[str, Any] | None:
    textures = mat.get("textures") or []
    exact = next((t for t in textures if t.get("usage") == usage), None)
    if exact is not None:
        return exact

    # Match the OBJ/preview path for base colour exactly.  The 3D preview finds
    # its image through the temporary OBJ/MTL map_Kd line, and _write_mtl() uses
    # the first texture row when no slot is explicitly classified as base.
    # Using the same rule keeps GLB from choosing a different Shader Graph
    # Texture2D_* slot from the one the user just previewed with U.
    if usage == "base":
        return textures[0] if textures else None

    # Slot-name fallback for odd shaders/materials.
    if usage == "normal":
        names = ("_bumpmap", "_normalmap", "_normal", "bump", "normal", "nrm")
    elif usage == "emission":
        names = ("_emissionmap", "emiss", "glow", "illum")
    else:
        names = (usage,)

    for t in textures:
        rel = str(t.get("relation", "")).lower()
        nm = str(getattr(t.get("record"), "name", "")).lower()
        if any(x in rel or x in nm for x in names):
            return t

    return None

def _glb_mime_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "image/png"

def _glb_add_texture_image(
    tex_row: dict[str, Any],
    texture_cache: dict[tuple[str, int], int],
    images: list[dict],
    textures: list[dict],
    buffer_views: list[dict],
    blob: bytearray,
    image_dir: Path,
    texture_export_failures: list[str],
) -> int | None:
    tex_rec = tex_row.get("record")
    if tex_rec is None:
        return None
    try:
        pid = int(getattr(tex_rec, "path_id"))
    except Exception:
        return None

    cache_key = (_record_source_name(tex_rec), int(pid or 0))
    if cache_key in texture_cache:
        return texture_cache[cache_key]

    type_name = getattr(tex_rec, "type_name", "")
    if type_name != "Texture2D":
        texture_export_failures.append(f"{getattr(tex_rec, 'name', pid)}: GLB embeds Texture2D only for now")
        return None

    try:
        png_path = export_texture_record(tex_rec, image_dir)
        if not png_path:
            texture_export_failures.append(f"{getattr(tex_rec, 'name', pid)}: texture decoder returned no file")
            return None
        png_path = Path(png_path)
        data = png_path.read_bytes()
    except Exception as exc:
        texture_export_failures.append(f"{getattr(tex_rec, 'name', pid)}: {exc}")
        return None

    view_idx = _glb_add_buffer_view(blob, buffer_views, data, None)
    image_idx = len(images)
    images.append({
        "name": safe_filename(getattr(tex_rec, "name", ""), f"texture_{pid}"),
        "bufferView": view_idx,
        "mimeType": _glb_mime_for_path(png_path),
    })

    texture_idx = len(textures)
    textures.append({
        "name": safe_filename(getattr(tex_rec, "name", ""), f"texture_{pid}"),
        "sampler": 0,
        "source": image_idx,
    })
    texture_cache[cache_key] = texture_idx
    return texture_idx

def export_mesh_glb_record(
    record,
    out_dir: str | Path,
    bundle_index: Any | None = None,
    asset_graph: Any | None = None,
    name_override: str | None = None,
    source_record: Any | None = None,
    source_context: dict[str, Any] | None = None,
    uv_channel: int = 0,
) -> MeshExportResult:
    """Export a Unity Mesh record as GLB with base + normal texture support."""
    root = Path(out_dir)
    glb_dir = root / "GLB"
    log_dir = root / "Logs"
    meta_dir = root / "Metadata"
    # Keep exported PNGs as a debug trail, but GLB embeds them too.
    image_dir = root / "Textures" / "_glb_embedded_source"
    for d in (glb_dir, log_dir, meta_dir, image_dir):
        d.mkdir(parents=True, exist_ok=True)

    # v1.8y: raw Mesh assets do not own their final material.  If a confident
    # GameObject/Renderer context exists, export through that object so GLB uses
    # the material/texture from the selected scene/object use of the mesh.
    if source_record is None and getattr(record, "type_name", "") == "Mesh" and bundle_index is not None:
        ctx = best_renderer_context_for_mesh(record, bundle_index, asset_graph, min_score=60)
        if ctx is not None and ctx.get("kind") == "semantic_material" and ctx.get("materials"):
            asset_graph = _ObjectMaterialGraph(asset_graph, record, list(ctx.get("materials") or []), bundle_index)
            source_record = record
            source_context = {
                "mode": "semantic_material",
                "score": ctx.get("score"),
                "reason": ctx.get("reason", ""),
                "materials": ctx.get("material_names", []),
                "textures": ctx.get("texture_names", []),
            }
            name_override = name_override or getattr(record, "name", None)
        elif ctx is not None and ctx.get("context_record") is not None:
            result = export_object_glb_record(ctx["context_record"], out_dir, bundle_index, asset_graph, uv_channel=uv_channel)
            if result and result.ok:
                try:
                    if result.log_path:
                        with Path(result.log_path).open("a", encoding="utf-8") as f:
                            f.write(
                                "\nRaw Mesh auto renderer context\n"
                                f"Mesh: {getattr(record, 'name', '-')} (PathID {getattr(record, 'path_id', '-')})\n"
                                f"Context: {getattr(ctx['context_record'], 'name', '-')} "
                                f"({getattr(ctx['context_record'], 'type_name', '-')}, PathID {getattr(ctx['context_record'], 'path_id', '-')})\n"
                                f"Score: {ctx.get('score')}\n"
                                f"Reason: {ctx.get('reason', '')}\n"
                            )
                except Exception:
                    pass
                result.message = f"{result.message}; auto renderer context: {getattr(ctx['context_record'], 'name', '-')}"
                return result

    safe = safe_filename(name_override or getattr(record, "name", ""), f"mesh_{getattr(record, 'path_id', 'unknown')}")
    glb_path = glb_dir / f"{safe}.glb"
    if glb_path.exists():
        glb_path = glb_dir / f"{safe}__path_{getattr(record, 'path_id', 'unknown')}.glb"
    log_path = log_dir / f"{safe}__glb_export.log"
    json_path = meta_dir / f"{safe}__glb_export.json"

    try:
        data = record.object.read()
    except Exception as exc:
        msg = f"Could not read mesh object: {exc}"
        log_path.write_text(msg, encoding="utf-8")
        return MeshExportResult(None, log_path, False, msg)

    user_requested_uv_channel = max(0, int(uv_channel or 0))
    requested_uv_channel = user_requested_uv_channel
    uv_sets = mesh_uv_channels_from_record(record)
    uv_channel_info = {f"UV{idx}": uv_bounds(vals) for idx, vals in sorted(uv_sets.items()) if vals}
    material_bundle = _gather_material_bundle(record, bundle_index, asset_graph) if bundle_index and asset_graph else []
    null_renderer_material_recovery = _recover_null_renderer_material_family(
        record, material_bundle, bundle_index, asset_graph
    )
    inferred_material_family = _hydrate_stripped_material_family_textures(material_bundle, bundle_index)
    local_palette_material_recovery = _hydrate_local_palette_material_shells(
        record, material_bundle, bundle_index, asset_graph
    )
    inferred_palette_texture = _hydrate_inferred_palette_texture(material_bundle, bundle_index, uv_sets)
    auto_base_uv = _recovered_character_base_uv_channel(material_bundle, user_requested_uv_channel)
    if auto_base_uv is not None:
        requested_uv_channel = int(auto_base_uv["effective_channel"])
    palette_uv_info = _palette_lookup_uv_info(
        uv_sets,
        allow_constant_uv0=bool(local_palette_material_recovery),
    )

    geo, method = _glb_geometry_from_mesh_data(data, uv_channel=requested_uv_channel, uv_sets=uv_sets)
    if not geo:
        log_path.write_text(
            "GLB Mesh Export\n"
            f"Name: {getattr(record, 'name', '-')}\n"
            f"Path ID: {getattr(record, 'path_id', '-')}\n"
            f"Status: SKIPPED\nReason: {method}\n",
            encoding="utf-8",
        )
        return MeshExportResult(None, log_path, False, method)

    positions = geo["positions"]
    indices = geo["indices"]
    normals = geo.get("normals") or []
    tangents = geo.get("tangents") or []
    mixed_point_sampled_uv_recovery = None
    if requested_uv_channel == 0:
        uv_sets, mixed_point_sampled_uv_recovery = _mixed_point_sampled_base_uv_recovery(
            record,
            material_bundle,
            uv_sets,
            list(positions or []),
            list(indices or []),
            list(geo.get("source_vertex_indices") or []),
        )
        if mixed_point_sampled_uv_recovery:
            palette_uv_info = mixed_point_sampled_uv_recovery
    uv_sets_remapped_from_obj = False
    if geo.get("source_vertex_indices"):
        uv_sets, uv_sets_remapped_from_obj = _glb_remap_uv_sets_by_source_vertex(
            uv_sets,
            geo.get("source_vertex_indices") or [],
            len(positions),
        )
        uv_channel_info = {f"UV{idx}": uv_bounds(vals) for idx, vals in sorted(uv_sets.items()) if vals}
    _normal_mat_for_uv, normal_row_for_uv = _first_texture_row_by_usage(material_bundle, "normal")
    has_normal_texture_for_uv = normal_row_for_uv is not None
    normal_keep_unity_v = _glb_normal_texture_keeps_unity_v(normal_row_for_uv, material_bundle)

    # GLB UV plan
    # ------------
    # The golf balls use two useful UV domains:
    #   - Unity UV0 is the full unwrap and gives the shared dimple normal map.
    #   - The U-selected preview channel, often UV1, selects the colour-atlas tile.
    # Earlier GLB builds wrote only one TEXCOORD_0, so either colour or bump could
    # be right, but not both.  We now keep UV0 as glTF TEXCOORD_0 for normalTexture
    # and write the U-selected channel as TEXCOORD_1 for baseColorTexture when it
    # differs from UV0.
    selected_uvs = geo.get("uvs") or []
    uv0s = uv_sets.get(0) or []
    if len(uv0s) < len(positions):
        uv0s = selected_uvs if requested_uv_channel == 0 else []

    base_uvs = uv_sets.get(requested_uv_channel) or selected_uvs
    if len(base_uvs) < len(positions):
        base_uvs = selected_uvs

    normal_uvs = uv0s if len(uv0s) >= len(positions) else base_uvs
    if len(normal_uvs) < len(positions):
        normal_uvs = []
    if len(base_uvs) < len(positions):
        base_uvs = normal_uvs

    # Match the OBJ preview/export path: Unity material TexEnv tiling/offset is
    # baked into the colour/base UVs.  Do not rely on KHR_texture_transform for
    # this because Windows 3D Viewer and other lightweight viewers may ignore it,
    # and the user expects GLB to match the UBE preview exactly.
    #
    # The normal/bump map can also have its own TexEnv transform.  Unity applies
    # that shader-side too, which effectively windows the normal map over a
    # smaller part of the 512x512 image.  Bake it into a separate TEXCOORD_0 so
    # the dimple map lines up in simple GLB viewers as well.
    base_uv_transform_info = None
    if material_bundle and base_uvs:
        base_uv_transform_info = _export_uv_transform_for_base(material_bundle, base_uvs)
        if base_uv_transform_info:
            base_uvs = _apply_uv_transform(
                base_uvs,
                base_uv_transform_info["scale"],
                base_uv_transform_info["offset"],
            )

    normal_uv_transform_info = None
    if material_bundle and normal_uvs:
        normal_uv_transform_info = _export_uv_transform_for_texture_row(normal_row_for_uv, "normal")
        if normal_uv_transform_info:
            normal_uvs = _apply_uv_transform(
                normal_uvs,
                normal_uv_transform_info["scale"],
                normal_uv_transform_info["offset"],
            )

    # Use two glTF texcoords whenever the base and normal sampling domains differ.
    # Golf balls are deliberately dual-domain:
    #   TEXCOORD_0 = normal/bump UVs from Unity UV0, using the same Unity->glTF
    #                V conversion as the B/N preview debug display.
    #   TEXCOORD_1 = base/colour atlas UVs, also with Unity->glTF V flip applied.
    #
    # The B hotkey proved the normal texture placement is correct in the preview,
    # so GLB normalTexture now follows that same sampling convention instead of
    # preserving raw Unity V as a special case.
    normal_uvs_gltf = (normal_uvs if normal_keep_unity_v else _glb_unity_uvs_to_gltf(normal_uvs))
    base_uvs_gltf = _glb_unity_uvs_to_gltf(base_uvs)

    use_dual_texcoords = bool(
        len(normal_uvs_gltf) >= len(positions)
        and len(base_uvs_gltf) >= len(positions)
        and has_normal_texture_for_uv
        and (
            normal_keep_unity_v
            or not _glb_uv_lists_equal(normal_uvs_gltf[:len(positions)], base_uvs_gltf[:len(positions)])
        )
    )
    normal_texcoord_index = 0
    base_texcoord_index = 1 if use_dual_texcoords else 0

    if not has_normal_texture_for_uv and len(base_uvs_gltf) >= len(positions):
        # Base-only materials should still get the correct glTF V-flipped UVs in TEXCOORD_0.
        normal_uvs_gltf = base_uvs_gltf

    tangents_generated = False
    if not tangents and has_normal_texture_for_uv and normals and normal_uvs_gltf:
        tangents = _glb_generate_tangents(positions, normals, normal_uvs_gltf, indices)
        tangents_generated = bool(tangents)

    blob = bytearray()
    buffer_views: list[dict] = []
    accessors: list[dict] = []

    pos_view = _glb_add_buffer_view(
        blob,
        buffer_views,
        _glb_pack_floats(_glb_flatten_vecs(positions, 3)),
        _GLTF_ARRAY_BUFFER,
    )
    pos_min, pos_max = _glb_bounds(positions, 3)
    pos_acc = _glb_add_accessor(accessors, pos_view, _GLTF_FLOAT, len(positions), "VEC3", pos_min, pos_max)

    attributes = {"POSITION": pos_acc}

    if normals and len(normals) >= len(positions):
        n_view = _glb_add_buffer_view(
            blob,
            buffer_views,
            _glb_pack_floats(_glb_flatten_vecs(normals[:len(positions)], 3)),
            _GLTF_ARRAY_BUFFER,
        )
        n_min, n_max = _glb_bounds(normals[:len(positions)], 3)
        attributes["NORMAL"] = _glb_add_accessor(accessors, n_view, _GLTF_FLOAT, len(positions), "VEC3", n_min, n_max)

    if tangents and len(tangents) >= len(positions):
        # glTF normalTexture is tangent-space.  Unity meshes usually carry an
        # authored tangent basis; exporting it avoids lightweight viewers
        # inventing a slightly different basis for the golf-ball dimple map.
        t_view = _glb_add_buffer_view(
            blob,
            buffer_views,
            _glb_pack_floats(_glb_flatten_vecs(tangents[:len(positions)], 4)),
            _GLTF_ARRAY_BUFFER,
        )
        t_min, t_max = _glb_bounds(tangents[:len(positions)], 4)
        attributes["TANGENT"] = _glb_add_accessor(accessors, t_view, _GLTF_FLOAT, len(positions), "VEC4", t_min, t_max)

    if normal_uvs_gltf and len(normal_uvs_gltf) >= len(positions):
        uv_view = _glb_add_buffer_view(
            blob,
            buffer_views,
            _glb_pack_floats(_glb_flatten_vecs(normal_uvs_gltf[:len(positions)], 2)),
            _GLTF_ARRAY_BUFFER,
        )
        uv_min, uv_max = _glb_bounds(normal_uvs_gltf[:len(positions)], 2)
        attributes["TEXCOORD_0"] = _glb_add_accessor(accessors, uv_view, _GLTF_FLOAT, len(positions), "VEC2", uv_min, uv_max)

    if use_dual_texcoords:
        uv1_view = _glb_add_buffer_view(
            blob,
            buffer_views,
            _glb_pack_floats(_glb_flatten_vecs(base_uvs_gltf[:len(positions)], 2)),
            _GLTF_ARRAY_BUFFER,
        )
        uv1_min, uv1_max = _glb_bounds(base_uvs_gltf[:len(positions)], 2)
        attributes["TEXCOORD_1"] = _glb_add_accessor(accessors, uv1_view, _GLTF_FLOAT, len(positions), "VEC2", uv1_min, uv1_max)

    idx_view = _glb_add_buffer_view(blob, buffer_views, _glb_pack_uints(indices), _GLTF_ELEMENT_ARRAY_BUFFER)
    idx_acc = _glb_add_accessor(
        accessors,
        idx_view,
        _GLTF_UNSIGNED_INT,
        len(indices),
        "SCALAR",
        [min(indices) if indices else 0],
        [max(indices) if indices else 0],
    )

    images: list[dict] = []
    textures: list[dict] = []
    palette_sampler_nearest = bool(palette_uv_info)
    samplers = [{
        "magFilter": 9728 if palette_sampler_nearest else 9729,  # NEAREST for palette, otherwise LINEAR
        "minFilter": 9728 if palette_sampler_nearest else 9729,
        "wrapS": 33071 if palette_sampler_nearest else 10497,   # CLAMP palette cells; REPEAT general UVs
        "wrapT": 33071 if palette_sampler_nearest else 10497,
    }]
    texture_cache: dict[tuple[str, int], int] = {}
    texture_export_failures: list[str] = []
    extensions_used: set[str] = set()

    gltf_materials: list[dict] = []

    if not material_bundle:
        gltf_materials.append({
            "name": "Default",
            "doubleSided": True,
            "pbrMetallicRoughness": {
                "baseColorFactor": [1, 1, 1, 1],
                "metallicFactor": 0,
                "roughnessFactor": 0.6,
            },
        })
    else:
        for mat in material_bundle:
            mat_rec = mat["record"]
            base_tex = _glb_pick_texture(mat, "base")
            normal_tex = _glb_pick_texture(mat, "normal")

            base_colour = mat.get("base_colour") or _material_base_colour(mat_rec) or (1.0, 1.0, 1.0)
            try:
                r, g, b = base_colour[:3]
            except Exception:
                r, g, b = (1.0, 1.0, 1.0)

            metallic = _glb_material_float(mat_rec, ("_Metallic",), 0.0)
            smooth = _glb_material_float(mat_rec, ("_Smoothness", "_Glossiness"), 0.5)
            roughness = max(0.0, min(1.0, 1.0 - float(smooth)))

            pbr = {
                "baseColorFactor": [float(r), float(g), float(b), 1.0],
                "metallicFactor": max(0.0, min(1.0, float(metallic))),
                "roughnessFactor": roughness,
            }

            if base_tex is not None:
                tex_idx = _glb_add_texture_image(
                    base_tex,
                    texture_cache,
                    images,
                    textures,
                    buffer_views,
                    blob,
                    image_dir,
                    texture_export_failures,
                )
                if tex_idx is not None:
                    # Keep textured materials neutral, like the OBJ/MTL exporter.
                    pbr["baseColorFactor"] = [1.0, 1.0, 1.0, 1.0]
                    pbr["baseColorTexture"] = _glb_texture_info(
                        tex_idx,
                        base_tex,
                        extensions_used,
                        tex_coord=base_texcoord_index,
                        include_transform=False,
                    )

            gltf_mat = {
                "name": safe_filename(getattr(mat_rec, "name", ""), f"material_{getattr(mat_rec, 'path_id', 'unknown')}"),
                "doubleSided": True,
                "pbrMetallicRoughness": pbr,
                "extras": {
                    "unityMaterialName": getattr(mat_rec, "name", ""),
                    "unityMaterialPathID": getattr(mat_rec, "path_id", None),
                    "unityBaseColor": [float(r), float(g), float(b)],
                    "glbBaseColorTexCoord": base_texcoord_index,
                    "glbBaseColorUnityUVChannel": requested_uv_channel,
                    "glbNormalTexCoord": normal_texcoord_index,
                    "glbNormalUnityUVChannel": 0,
                    "glbNormalKeepUnityV": bool(normal_keep_unity_v),
                },
            }

            if normal_tex is not None:
                tex_idx = _glb_add_texture_image(
                    normal_tex,
                    texture_cache,
                    images,
                    textures,
                    buffer_views,
                    blob,
                    image_dir,
                    texture_export_failures,
                )
                if tex_idx is not None:
                    bump_scale = _glb_material_float(mat_rec, ("_BumpScale", "_NormalScale"), 1.0)
                    normal_info = _glb_texture_info(
                        tex_idx,
                        normal_tex,
                        extensions_used,
                        tex_coord=normal_texcoord_index,
                        include_transform=False,
                    )
                    normal_info["scale"] = float(bump_scale)
                    gltf_mat["normalTexture"] = normal_info
                    gltf_mat["extras"]["unityNormalTexture"] = {
                        "name": getattr(normal_tex.get("record"), "name", ""),
                        "pathID": getattr(normal_tex.get("record"), "path_id", None),
                        "slot": normal_tex.get("relation", ""),
                        "scale": float(bump_scale),
                        "uvTransformBaked": normal_uv_transform_info,
                    }

            gltf_materials.append(gltf_mat)

    primitive = {
        "attributes": attributes,
        "indices": idx_acc,
        "mode": _GLTF_TRIANGLES,
        "material": 0,
    }

    gltf = {
        "asset": {
            "version": "2.0",
            "generator": f"UBE {APP_VERSION} build {APP_BUILD}",
        },
        "scenes": [{"nodes": [0]}],
        "scene": 0,
        "nodes": [{
            "name": safe,
            "mesh": 0,
            "extras": {
                "unityMeshName": getattr(record, "name", ""),
                "unityMeshPathID": getattr(record, "path_id", None),
                "sourceObjectName": getattr(source_record, "name", "") if source_record is not None else "",
                "sourceObjectPathID": getattr(source_record, "path_id", None) if source_record is not None else None,
            },
        }],
        "meshes": [{
            "name": safe,
            "primitives": [primitive],
        }],
        "materials": gltf_materials,
        "samplers": samplers,
        "textures": textures,
        "images": images,
        "bufferViews": buffer_views,
        "accessors": accessors,
    }

    if extensions_used:
        gltf["extensionsUsed"] = sorted(extensions_used)

    glb_path.write_bytes(_glb_make_glb_bytes(gltf, blob))

    meta = {
        "ube_version": APP_VERSION,
        "ube_build": APP_BUILD,
        "format": "glb",
        "bundle": str(getattr(bundle_index, "path", "")) if bundle_index is not None else "",
        "source_object": {
            "name": getattr(source_record, "name", "") if source_record is not None else "",
            "type": getattr(source_record, "type_name", "") if source_record is not None else "",
            "path_id": getattr(source_record, "path_id", None) if source_record is not None else None,
            "context": source_context or {},
        },
        "mesh": {
            "name": getattr(record, "name", ""),
            "path_id": getattr(record, "path_id", None),
            "method": method,
            "vertices_written": len(positions),
            "indices_written": len(indices),
            "triangles_written": len(indices) // 3,
            "uv_channel_requested": user_requested_uv_channel,
            "uv_channel_exported": requested_uv_channel,
            "uv_channel_auto_selected": auto_base_uv,
            "uv_channels": uv_channel_info,
            "palette_lookup_uv": palette_uv_info,
            "mixed_point_sampled_uv_recovery": mixed_point_sampled_uv_recovery,
            "null_renderer_material_recovery": null_renderer_material_recovery,
            "inferred_material_family": inferred_material_family,
            "local_palette_material_recovery": local_palette_material_recovery,
            "inferred_palette_texture": inferred_palette_texture,
            "base_texture_unity_uv_channel": requested_uv_channel,
            "base_texture_gltf_texcoord": base_texcoord_index,
            "normal_texture_unity_uv_channel": 0,
            "normal_texture_gltf_texcoord": normal_texcoord_index,
            "dual_texcoord_export": use_dual_texcoords,
            "gltf_v_flipped": True,
            "base_uv_bounds_unity": uv_bounds(base_uvs),
            "base_uv_bounds_gltf": uv_bounds(base_uvs_gltf),
            "normal_uv_bounds_unity": uv_bounds(normal_uvs),
            "normal_uv_bounds_gltf": uv_bounds(normal_uvs_gltf),
            "base_uv_transform_baked": base_uv_transform_info,
            "normal_uv_transform_baked": normal_uv_transform_info,
            "obj_source_vertex_uv_remap": uv_sets_remapped_from_obj,
            "has_normals": bool(normals),
            "has_tangents": bool(tangents),
            "tangents_generated": tangents_generated,
            "has_uv0": bool(normal_uvs),
            "has_selected_uv": bool(base_uvs),
        },
        "export": {
            "glb": str(glb_path.relative_to(root)),
            "log": str(log_path.relative_to(root)),
        },
        "materials": [
            {
                "slot": i,
                "slot_relation": mat.get("slot_relation", ""),
                "name": getattr(mat.get("record"), "name", ""),
                "path_id": getattr(mat.get("record"), "path_id", None),
                "source_name": _record_source_name(mat.get("record")),
            }
            for i, mat in enumerate(material_bundle)
        ],
        "textures": [
            {
                "material": getattr(mat.get("record"), "name", ""),
                "name": getattr(tex.get("record"), "name", ""),
                "path_id": getattr(tex.get("record"), "path_id", None),
                "source_name": _record_source_name(tex.get("record")),
                "usage": tex.get("usage", ""),
                "relation": tex.get("relation", ""),
                "scale": list(_glb_pair2(tex.get("scale"), (1.0, 1.0))),
                "offset": list(_glb_pair2(tex.get("offset"), (0.0, 0.0))),
            }
            for mat in material_bundle
            for tex in mat.get("textures", [])
        ],
        "texture_export_failures": texture_export_failures,
    }
    json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    log_path.write_text(
        "GLB Mesh Export\n"
        f"Name: {getattr(record, 'name', '-')}\n"
        f"Path ID: {getattr(record, 'path_id', '-')}\n"
        f"Method: {method}\n"
        f"GLB: {glb_path}\n"
        f"Metadata: {json_path}\n"
        f"Vertices written: {len(positions):,}\n"
        f"Triangles written: {len(indices) // 3:,}\n"
        f"Materials: {len(gltf_materials):,}\n"
        f"Images embedded: {len(images):,}\n"
        f"Textures reused by PathID: {len(texture_cache):,}\n"
        f"UV channel requested by U key: UV{user_requested_uv_channel}\n"
        f"UV channel used for base colour: UV{requested_uv_channel}"
        f"{' (automatic recovered character colour UV)' if auto_base_uv else ''}\n"
        f"UV auto-selection reason: {(auto_base_uv or {}).get('reason', '-')}\n"
        f"Base texture uses: TEXCOORD_{base_texcoord_index} from Unity UV{requested_uv_channel}\n"
        f"Normal texture uses: TEXCOORD_{normal_texcoord_index} from Unity UV0\n"
        f"Tangents exported: {'yes' if bool(tangents) else 'no'}{' (generated)' if tangents_generated else ''}\n"
        f"OBJ source-vertex UV remap: {'yes' if uv_sets_remapped_from_obj else 'no'}\n"
        f"Normal texture V flip applied: {'no - preserving Unity normal-map V' if normal_keep_unity_v else 'yes - Unity V -> glTF 1-V'}\n"
        f"Dual texcoord export: {'yes' if use_dual_texcoords else 'no'}\n"
        f"Recovered local palette shell: {', '.join(row.get('template', '-') for row in local_palette_material_recovery) if local_palette_material_recovery else '-'}\n"
        f"Recovered null renderer material: {(null_renderer_material_recovery or {}).get('template_material', '-')} "
        f"via {(null_renderer_material_recovery or {}).get('template_mesh', '-')}\n"
        f"Mixed point-sampled PS UV recovery: {(mixed_point_sampled_uv_recovery or {}).get('reason', '-')}\n"
        f"Base texture V flip applied: yes (Unity V -> glTF 1-V)\n"
        f"Base UV transform baked: {base_uv_transform_info['source'] if base_uv_transform_info else 'no'}\n"
        f"Normal UV transform baked: {normal_uv_transform_info['source'] if normal_uv_transform_info else 'no'}\n"
        f"UV channels found: {', '.join(sorted(uv_channel_info.keys())) if uv_channel_info else '-'}\n"
        f"KHR_texture_transform: {'yes' if 'KHR_texture_transform' in extensions_used else 'no'}\n"
        f"Texture export failures: {len(texture_export_failures):,}\n"
        "Status: SUCCESS\n",
        encoding="utf-8",
    )

    suffix = "with embedded textures" if images else "geometry only"
    return MeshExportResult(glb_path, log_path, True, f"Exported GLB using {method} ({suffix})", None, json_path)

def export_object_glb_record(
    record,
    out_dir: str | Path,
    bundle_index: Any | None = None,
    asset_graph: Any | None = None,
    uv_channel: int = 0,
) -> MeshExportResult:
    """Export the mesh attached to a GameObject/component as GLB."""
    root = Path(out_dir)
    log_dir = root / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    safe_obj = safe_filename(getattr(record, "name", "Object"), f"object_{getattr(record, 'path_id', 'unknown')}")
    log_path = log_dir / f"{safe_obj}__object_glb_export.log"

    mesh_rec, material_records, context = _object_mesh_and_materials(record, bundle_index)
    if mesh_rec is None:
        msg = "No MeshFilter/SkinnedMeshRenderer mesh was found for this object/component."
        log_path.write_text(
            "Object GLB Export\n"
            f"Object: {getattr(record, 'name', '-')}\n"
            f"Type: {getattr(record, 'type_name', '-')}\n"
            f"Path ID: {getattr(record, 'path_id', '-')}\n"
            f"Status: SKIPPED\nReason: {msg}\n",
            encoding="utf-8",
        )
        return MeshExportResult(None, log_path, False, msg)

    graph = _ObjectMaterialGraph(asset_graph, mesh_rec, material_records, bundle_index, object_context=context)
    result = export_mesh_glb_record(
        mesh_rec,
        out_dir,
        bundle_index,
        graph,
        name_override=safe_obj,
        source_record=record,
        source_context=context,
        uv_channel=uv_channel,
    )

    try:
        lines = [
            "Object GLB Export",
            f"Object: {getattr(record, 'name', '-')} ({getattr(record, 'type_name', '-')})",
            f"Object Path ID: {getattr(record, 'path_id', '-')}",
            f"Mesh: {getattr(mesh_rec, 'name', '-')} (PathID {getattr(mesh_rec, 'path_id', '-')})",
            f"Materials: {len(material_records)}",
        ]
        for i, mat in enumerate(material_records):
            lines.append(f"  Slot {i}: {getattr(mat, 'name', '-')} (PathID {getattr(mat, 'path_id', '-')})")
        lines.append(f"Result: {result.message}")
        if result.path:
            lines.append(f"GLB: {result.path}")
        if result.json_path:
            lines.append(f"Metadata: {result.json_path}")
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass

    return result

# =====================================================
# Multi-object assembled export
# =====================================================

def _multi_export_safe_name(records: list[Any], fallback: str = "multi_selection") -> str:
    names = [str(getattr(r, "name", "") or "").strip() for r in records or []]
    names = [n for n in names if n]
    if not names:
        return safe_filename(fallback, fallback)
    if len(names) == 1:
        label = names[0]
    elif len(names) == 2:
        label = f"{names[0]}__plus__{names[1]}"
    else:
        label = f"{names[0]}__plus__{names[1]}__plus_{len(names)-2}_more"
    return safe_filename(label, fallback)[:140]


def _obj_count_lines(obj_text: str) -> tuple[int, int, int]:
    v = vt = vn = 0
    for raw in obj_text.splitlines():
        line = raw.lstrip()
        if line.startswith("v "):
            v += 1
        elif line.startswith("vt "):
            vt += 1
        elif line.startswith("vn "):
            vn += 1
    return v, vt, vn


def _obj_remap_index(value: str, base: int, current_count: int) -> str:
    if value == "":
        return ""
    try:
        n = int(value)
    except Exception:
        return value
    if n > 0:
        return str(n + base)
    if n < 0:
        # Convert negative relative OBJ index to absolute merged index.
        return str(base + current_count + n + 1)
    return value


def _obj_remap_face_token(token: str, v_base: int, vt_base: int, vn_base: int, v_count: int, vt_count: int, vn_count: int) -> str:
    parts = token.split("/")
    if len(parts) == 1:
        return _obj_remap_index(parts[0], v_base, v_count)
    if len(parts) == 2:
        return "/".join([
            _obj_remap_index(parts[0], v_base, v_count),
            _obj_remap_index(parts[1], vt_base, vt_count),
        ])
    return "/".join([
        _obj_remap_index(parts[0], v_base, v_count),
        _obj_remap_index(parts[1], vt_base, vt_count),
        _obj_remap_index(parts[2], vn_base, vn_count),
    ])


def _unique_copy_path(dest_dir: Path, src_name: str, prefix: str) -> Path:
    base = safe_filename(Path(src_name).stem, "texture")
    suffix = Path(src_name).suffix or ".png"
    candidate = dest_dir / f"{base}{suffix}"
    if not candidate.exists():
        return candidate
    candidate = dest_dir / f"{safe_filename(prefix, 'part')}__{base}{suffix}"
    if not candidate.exists():
        return candidate
    i = 2
    while True:
        c = dest_dir / f"{safe_filename(prefix, 'part')}__{base}_{i}{suffix}"
        if not c.exists():
            return c
        i += 1


def _copy_mtl_prefixed(mtl_path: Path, final_mtl_path: Path, final_tex_dir: Path, prefix: str) -> tuple[list[str], dict[str, str]]:
    """Copy one MTL into the combined MTL, prefixing material names and texture files."""
    if not mtl_path or not mtl_path.exists():
        return [], {}
    lines_out: list[str] = []
    mat_map: dict[str, str] = {}
    final_tex_dir.mkdir(parents=True, exist_ok=True)
    mtl_dir = final_mtl_path.parent
    current_prefix = safe_filename(prefix, "part")

    texture_keywords = {"map_kd", "map_ka", "map_ks", "map_ke", "bump", "map_bump", "disp", "decal", "refl"}

    for raw in mtl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.strip()
        if not stripped:
            lines_out.append("")
            continue
        parts = stripped.split(maxsplit=1)
        key = parts[0]
        low = key.lower()
        rest = parts[1] if len(parts) > 1 else ""
        if low == "newmtl" and rest:
            new_name = f"{current_prefix}__{safe_filename(rest, 'material')}"
            mat_map[rest] = new_name
            lines_out.append(f"newmtl {new_name}")
            continue
        if low in texture_keywords and rest:
            # Existing UBE MTL writes simple map lines without option flags.  If a
            # future exporter adds options, this still keeps the final path token.
            tokens = rest.split()
            src_token = tokens[-1]
            src_path = (mtl_path.parent / src_token).resolve()
            if src_path.exists() and src_path.is_file():
                dst_path = _unique_copy_path(final_tex_dir, src_path.name, current_prefix)
                try:
                    shutil.copy2(src_path, dst_path)
                    tokens[-1] = Path(os.path.relpath(dst_path, mtl_dir)).as_posix()
                    lines_out.append(f"{key} {' '.join(tokens)}")
                    continue
                except Exception:
                    pass
        lines_out.append(raw)
    return lines_out, mat_map


def _coerce_matrix4(value: Any | None) -> list[list[float]] | None:
    """Return a row-major 4x4 matrix, or None when no useful transform exists."""
    if value is None:
        return None
    try:
        if isinstance(value, (list, tuple)) and len(value) == 16:
            vals = [float(v) for v in value]
            return [vals[i:i + 4] for i in range(0, 16, 4)]
        if isinstance(value, (list, tuple)) and len(value) >= 4:
            rows = []
            for row in value[:4]:
                if not isinstance(row, (list, tuple)) or len(row) < 4:
                    return None
                rows.append([float(v) for v in row[:4]])
            return rows
    except Exception:
        return None
    return None


def _matrix_is_identity(value: Any | None, eps: float = 1e-9) -> bool:
    matrix = _coerce_matrix4(value)
    if matrix is None:
        return True
    for r in range(4):
        for c in range(4):
            wanted = 1.0 if r == c else 0.0
            if abs(float(matrix[r][c]) - wanted) > eps:
                return False
    return True


def _matrix_transform_point(matrix: Any | None, xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    m = _coerce_matrix4(matrix)
    if m is None:
        return xyz
    x, y, z = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
    )


def _matrix_det3(matrix: Any | None) -> float:
    m = _coerce_matrix4(matrix)
    if m is None:
        return 1.0
    a, b, c = m[0][0], m[0][1], m[0][2]
    d, e, f = m[1][0], m[1][1], m[1][2]
    g, h, i = m[2][0], m[2][1], m[2][2]
    return a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)


def _matrix_transform_normal(matrix: Any | None, xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    """Apply inverse-transpose of the upper 3x3, then normalise."""
    m = _coerce_matrix4(matrix)
    if m is None:
        return xyz
    a, b, c = m[0][0], m[0][1], m[0][2]
    d, e, f = m[1][0], m[1][1], m[1][2]
    g, h, i = m[2][0], m[2][1], m[2][2]
    det = _matrix_det3(m)
    x, y, z = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
    if abs(det) < 1e-12:
        # Degenerate scale: the linear part is still a more useful fallback than
        # discarding the normal entirely.
        nx = a * x + b * y + c * z
        ny = d * x + e * y + f * z
        nz = g * x + h * y + i * z
    else:
        inv_det = 1.0 / det
        # inverse-transpose(A) multiplied by the source normal
        nx = ((e * i - f * h) * x + (f * g - d * i) * y + (d * h - e * g) * z) * inv_det
        ny = ((c * h - b * i) * x + (a * i - c * g) * y + (b * g - a * h) * z) * inv_det
        nz = ((b * f - c * e) * x + (c * d - a * f) * y + (a * e - b * d) * z) * inv_det
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length > 1e-12:
        return (nx / length, ny / length, nz / length)
    return (0.0, 0.0, 1.0)


def _matrix_to_gltf_column_major(value: Any | None) -> list[float] | None:
    """Convert UBE's row-major, column-vector matrix to glTF's column-major list."""
    m = _coerce_matrix4(value)
    if m is None or _matrix_is_identity(m):
        return None
    return [float(m[r][c]) for c in range(4) for r in range(4)]


def _matrix_to_gltf_column_major_full(value: Any | None) -> list[float]:
    """Column-major MAT4 values, retaining identity matrices for accessors."""
    m = _coerce_matrix4(value) or [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return [float(m[r][c]) for c in range(4) for r in range(4)]


def _skin_weight_vectors(weights: list, vertex_count: int) -> tuple[list[tuple[int, int, int, int]], list[tuple[float, float, float, float]]]:
    joints = []
    values = []
    for vertex_index in range(vertex_count):
        row = list(weights[vertex_index] or []) if vertex_index < len(weights) else []
        cleaned = []
        for bone_index, weight in row[:4]:
            try:
                bi = int(bone_index)
                wf = max(0.0, float(weight))
            except Exception:
                continue
            if bi >= 0 and wf > 1e-10:
                cleaned.append((bi, wf))
        total = sum(weight for _index, weight in cleaned)
        if total <= 1e-10:
            cleaned = [(0, 1.0)]
            total = 1.0
        cleaned = [(index, weight / total) for index, weight in cleaned]
        while len(cleaned) < 4:
            cleaned.append((0, 0.0))
        joints.append(tuple(int(cleaned[i][0]) for i in range(4)))
        values.append(tuple(float(cleaned[i][1]) for i in range(4)))
    return joints, values


def _glb_float32(value: Any) -> float:
    """Return the exact IEEE-754 float32 value written to a glTF FLOAT accessor."""
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def _glb_strict_time_indices(values: list[Any]) -> tuple[list[float], list[int]]:
    """Round animation times to float32 and discard non-increasing duplicates."""
    times: list[float] = []
    indices: list[int] = []
    for index, value in enumerate(values or []):
        try:
            current = _glb_float32(value)
        except Exception:
            continue
        if times and current <= times[-1]:
            continue
        times.append(current)
        indices.append(index)
    return times, indices


def _skin_source_vertex_indices(mesh_record: Any, uv_channel: int) -> tuple[list[int], str]:
    """Reproduce the single-mesh GLB vertex map used by the temporary part export."""
    if mesh_record is None:
        return [], "no mesh record supplied"
    try:
        mesh_data = mesh_record.object.read()
        uv_sets = mesh_uv_channels_from_record(mesh_record)
        geo, method = _glb_geometry_from_mesh_data(
            mesh_data,
            uv_channel=max(0, int(uv_channel or 0)),
            uv_sets=uv_sets,
        )
    except Exception as exc:
        return [], f"could not rebuild GLB vertex map: {exc}"
    if not geo:
        return [], str(method or "no GLB geometry")
    positions = list(geo.get("positions") or [])
    source = list(geo.get("source_vertex_indices") or [])
    if source and len(source) == len(positions):
        try:
            return [int(value) for value in source], str(method or "OBJ source vertex map")
        except Exception:
            return [], "GLB source vertex map contained invalid indices"
    return list(range(len(positions))), str(method or "native vertex order")


def _skin_remap_weights_for_gltf(
    weights: list,
    source_vertex_indices: list[int],
    vertex_count: int,
) -> list:
    """Map Unity weight rows into the final GLB vertex order."""
    expected = max(0, int(vertex_count or 0))
    if expected <= 0:
        raise ValueError("Skinned GLB geometry has no vertices")
    source = list(source_vertex_indices or [])
    if len(source) != expected:
        if len(weights or []) == expected:
            source = list(range(expected))
        else:
            raise ValueError(
                f"Skin vertex map has {len(source):,} entries for {expected:,} exported vertices "
                f"and {len(weights or []):,} Unity weight rows"
            )
    remapped = []
    for output_index, source_index in enumerate(source):
        try:
            source_index = int(source_index)
        except Exception as exc:
            raise ValueError(f"Invalid source vertex index at output vertex {output_index}") from exc
        if source_index < 0 or source_index >= len(weights or []):
            raise ValueError(
                f"Source vertex index {source_index} at output vertex {output_index} "
                f"is outside {len(weights or []):,} Unity weight rows"
            )
        remapped.append(weights[source_index])
    return remapped


def _unity_matrix_to_unitypy_obj_basis(value: Any | None) -> list[list[float]] | None:
    """Convert a Unity-space matrix for UnityPy's mirrored-X OBJ geometry.

    UnityPy's OBJ exporter writes positions/normals as (-x, y, z).  If
    p_obj = C p_unity, the matching transform is M_obj = C M_unity C,
    where C = diag(-1, 1, 1, 1) and C is its own inverse.
    """
    m = _coerce_matrix4(value)
    if m is None:
        return None
    signs = (-1.0, 1.0, 1.0, 1.0)
    return [
        [signs[r] * float(m[r][c]) * signs[c] for c in range(4)]
        for r in range(4)
    ]


def _result_uses_unitypy_obj_basis(result: Any) -> bool:
    """Return True when exported geometry is in UnityPy's mirrored-X OBJ basis."""
    message = str(getattr(result, "message", "") or "").lower()
    return "unitypy export" in message or "unitypy obj export parsed" in message


def _record_transform_lookup(record_matrices: dict[Any, Any] | None, rec: Any) -> list[list[float]] | None:
    if not record_matrices or rec is None:
        return None
    source = str(getattr(rec, "source_name", "") or "")
    type_name = str(getattr(rec, "type_name", "") or "")
    pid = getattr(rec, "path_id", None)
    candidates = (
        (source, type_name, pid),
        (type_name, pid),
        (source, pid),
        pid,
    )
    for key in candidates:
        try:
            if key in record_matrices:
                return _coerce_matrix4(record_matrices[key])
        except Exception:
            continue
    return None


def _record_payload_lookup(mapping: dict[Any, Any] | None, rec: Any) -> Any | None:
    """Look up an arbitrary per-record payload using UBE's common keys."""
    if not mapping or rec is None:
        return None
    source = str(getattr(rec, "source_name", "") or "")
    type_name = str(getattr(rec, "type_name", "") or "")
    pid = getattr(rec, "path_id", None)
    for key in ((source, type_name, pid), (type_name, pid), (source, pid), pid):
        try:
            if key in mapping:
                return mapping[key]
        except Exception:
            continue
    return None


def _matrix_det3_rows(m: list[list[float]]) -> float:
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _matrix_gltf_trs_shear(value: Any | None) -> float:
    """Return the maximum normalized basis-column dot product.

    A glTF animated node can express translation, quaternion rotation and scale,
    including non-uniform and mirrored scale.  It cannot express affine shear.
    Orthogonal 3x3 basis columns therefore mean the matrix is representable as
    TRS; non-zero column dot products measure actual shear.  Degenerate axes are
    returned as infinity because UBE's animated TRS writer cannot preserve them
    safely.
    """
    m = _coerce_matrix4(value)
    if m is None:
        return float("inf")
    columns = [
        [float(m[row][column]) for row in range(3)]
        for column in range(3)
    ]
    lengths = [math.sqrt(sum(component * component for component in column)) for column in columns]
    if any(length <= 1e-10 or not math.isfinite(length) for length in lengths):
        return float("inf")
    normalized = [
        [component / lengths[index] for component in columns[index]]
        for index in range(3)
    ]
    return max(
        abs(sum(normalized[a][axis] * normalized[b][axis] for axis in range(3)))
        for a, b in ((0, 1), (0, 2), (1, 2))
    )


def _rotation_matrix_to_quaternion(m: list[list[float]]) -> tuple[float, float, float, float]:
    """Return a normalized glTF quaternion (x, y, z, w)."""
    trace = float(m[0][0] + m[1][1] + m[2][2])
    try:
        if trace > 0.0:
            scale = math.sqrt(max(0.0, trace + 1.0)) * 2.0
            q = (
                (m[2][1] - m[1][2]) / scale,
                (m[0][2] - m[2][0]) / scale,
                (m[1][0] - m[0][1]) / scale,
                0.25 * scale,
            )
        elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
            scale = math.sqrt(max(0.0, 1.0 + m[0][0] - m[1][1] - m[2][2])) * 2.0
            q = (
                0.25 * scale,
                (m[0][1] + m[1][0]) / scale,
                (m[0][2] + m[2][0]) / scale,
                (m[2][1] - m[1][2]) / scale,
            )
        elif m[1][1] > m[2][2]:
            scale = math.sqrt(max(0.0, 1.0 + m[1][1] - m[0][0] - m[2][2])) * 2.0
            q = (
                (m[0][1] + m[1][0]) / scale,
                0.25 * scale,
                (m[1][2] + m[2][1]) / scale,
                (m[0][2] - m[2][0]) / scale,
            )
        else:
            scale = math.sqrt(max(0.0, 1.0 + m[2][2] - m[0][0] - m[1][1])) * 2.0
            q = (
                (m[0][2] + m[2][0]) / scale,
                (m[1][2] + m[2][1]) / scale,
                0.25 * scale,
                (m[1][0] - m[0][1]) / scale,
            )
    except Exception:
        return (0.0, 0.0, 0.0, 1.0)
    length = math.sqrt(sum(float(v) * float(v) for v in q))
    if length <= 1e-12:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(float(v) / length for v in q)


def _matrix_to_gltf_trs(value: Any | None) -> tuple[tuple[float, float, float], tuple[float, float, float, float], tuple[float, float, float]]:
    """Decompose UBE's row-major affine matrix into glTF node TRS.

    A negative determinant is retained as a negative X scale so mirrored Unity
    instances remain representable without putting a matrix on an animated node.
    """
    m = _coerce_matrix4(value) or [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    translation = (float(m[0][3]), float(m[1][3]), float(m[2][3]))
    sx = math.sqrt(sum(float(m[r][0]) ** 2 for r in range(3)))
    sy = math.sqrt(sum(float(m[r][1]) ** 2 for r in range(3)))
    sz = math.sqrt(sum(float(m[r][2]) ** 2 for r in range(3)))
    sx = sx if sx > 1e-12 else 1.0
    sy = sy if sy > 1e-12 else 1.0
    sz = sz if sz > 1e-12 else 1.0
    if _matrix_det3_rows(m) < 0.0:
        sx = -sx
    rotation_rows = [
        [float(m[r][0]) / sx, float(m[r][1]) / sy, float(m[r][2]) / sz]
        for r in range(3)
    ]
    rotation = _rotation_matrix_to_quaternion(rotation_rows)
    return translation, rotation, (float(sx), float(sy), float(sz))


def _quaternion_sequence_continuous(values: list[tuple[float, float, float, float]]) -> list[tuple[float, float, float, float]]:
    out: list[tuple[float, float, float, float]] = []
    for value in values or []:
        q = tuple(float(v) for v in value)
        if out and sum(out[-1][i] * q[i] for i in range(4)) < 0.0:
            q = tuple(-v for v in q)
        out.append(q)
    return out


def _animation_values_change(values: list[tuple], epsilon: float = 1e-6) -> bool:
    if len(values or []) < 2:
        return False
    first = values[0]
    for value in values[1:]:
        if len(value) != len(first):
            return True
        if any(abs(float(value[i]) - float(first[i])) > epsilon for i in range(len(first))):
            return True
    return False


def _merge_obj_part(
    obj_path: Path,
    part_name: str,
    mat_map: dict[str, str],
    v_base: int,
    vt_base: int,
    vn_base: int,
    transform_matrix: Any | None = None,
) -> tuple[list[str], int, int, int, int]:
    text = obj_path.read_text(encoding="utf-8", errors="replace")
    v_count, vt_count, vn_count = _obj_count_lines(text)
    out: list[str] = ["", f"o {safe_filename(part_name, 'part')}", f"# Source OBJ: {obj_path.name}"]
    has_transform = not _matrix_is_identity(transform_matrix)
    if has_transform:
        out.append("# Parent-relative Unity Transform applied by UBE group export")
    face_count = 0
    first_mat = next(iter(mat_map.values()), None)
    inserted_default_mat = False
    reverse_winding = _matrix_det3(transform_matrix) < 0.0

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("mtllib "):
            continue
        if line.startswith("o ") or line.startswith("g "):
            continue
        if line.startswith("v ") and has_transform:
            bits = line.split()
            if len(bits) >= 4:
                try:
                    point = _matrix_transform_point(transform_matrix, (float(bits[1]), float(bits[2]), float(bits[3])))
                    rest = (" " + " ".join(bits[4:])) if len(bits) > 4 else ""
                    out.append(f"v {point[0]:.9g} {point[1]:.9g} {point[2]:.9g}{rest}")
                    continue
                except Exception:
                    pass
        if line.startswith("vn ") and has_transform:
            bits = line.split()
            if len(bits) >= 4:
                try:
                    normal = _matrix_transform_normal(transform_matrix, (float(bits[1]), float(bits[2]), float(bits[3])))
                    out.append(f"vn {normal[0]:.9g} {normal[1]:.9g} {normal[2]:.9g}")
                    continue
                except Exception:
                    pass
        if line.startswith("usemtl "):
            old = line.split(maxsplit=1)[1].strip()
            out.append(f"usemtl {mat_map.get(old, old)}")
            inserted_default_mat = True
            continue
        if line.startswith("f "):
            if first_mat and not inserted_default_mat:
                out.append(f"usemtl {first_mat}")
                inserted_default_mat = True
            toks = line.split()[1:]
            remapped = [_obj_remap_face_token(t, v_base, vt_base, vn_base, v_count, vt_count, vn_count) for t in toks]
            if reverse_winding:
                remapped.reverse()
            out.append("f " + " ".join(remapped))
            # fan-triangulated face count estimate
            face_count += max(1, len(remapped) - 2)
            continue
        out.append(raw)
    return out, v_count, vt_count, vn_count, face_count


def export_multi_object_record(
    records: list[Any],
    out_dir: str | Path,
    bundle_index: Any | None = None,
    asset_graph: Any | None = None,
    uv_channel: int = 0,
    name_override: str | None = None,
    record_matrices: dict[Any, Any] | None = None,
    allow_single: bool = False,
) -> MeshExportResult:
    """Export several selected renderable records as one combined OBJ assembly.

    The parts are not individually re-centred.  If the Unity objects were authored
    in the same coordinate space, the exported assembly lines up like the
    multi-select preview.
    """
    clean_records: list[Any] = []
    seen: set[Any] = set()
    for rec in records or []:
        if rec is None:
            continue
        key = (getattr(rec, "source_name", ""), getattr(rec, "type_name", ""), getattr(rec, "path_id", id(rec)))
        if key in seen:
            continue
        seen.add(key)
        clean_records.append(rec)
    minimum_parts = 1 if allow_single else 2
    if len(clean_records) < minimum_parts:
        root = Path(out_dir)
        log_dir = root / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "multi_object_export.log"
        msg = "Group export needs at least one renderable descendant." if allow_single else "Combined export needs two or more selected renderable objects."
        log_path.write_text(msg, encoding="utf-8")
        return MeshExportResult(None, log_path, False, msg)

    root = Path(out_dir)
    mesh_dir = root / "Meshes"
    mat_dir = root / "Materials"
    tex_dir = root / "Textures"
    log_dir = root / "Logs"
    meta_dir = root / "Metadata"
    for d in (mesh_dir, mat_dir, tex_dir, log_dir, meta_dir):
        d.mkdir(parents=True, exist_ok=True)

    safe = safe_filename(name_override or _multi_export_safe_name(clean_records), "multi_selection")
    obj_path = mesh_dir / f"{safe}__combined.obj"
    mtl_path = mat_dir / f"{safe}__combined.mtl"
    log_path = log_dir / f"{safe}__combined_obj_export.log"
    json_path = meta_dir / f"{safe}__combined_obj_export.json"

    exported_parts: list[dict[str, Any]] = []
    skipped: list[str] = []
    pending_animations: list[dict[str, Any]] = []
    obj_lines: list[str] = [
        "# Exported by UBE",
        "# Combined multi-selection OBJ assembly",
        f"mtllib {Path(os.path.relpath(mtl_path, obj_path.parent)).as_posix()}",
    ]
    mtl_lines: list[str] = ["# Exported by UBE", "# Combined multi-selection MTL", ""]
    v_base = vt_base = vn_base = 0
    total_faces = 0

    with tempfile.TemporaryDirectory(prefix="ube_multi_obj_export_") as tmp:
        tmp_root = Path(tmp)
        for idx, rec in enumerate(clean_records):
            name = str(getattr(rec, "name", f"part_{idx}"))
            part_prefix = f"part_{idx:02d}_{safe_filename(name, 'part')}"
            part_dir = tmp_root / part_prefix
            part_dir.mkdir(parents=True, exist_ok=True)
            try:
                if getattr(rec, "type_name", "") == "Mesh":
                    result = export_mesh_record(rec, part_dir, bundle_index, asset_graph, uv_channel=uv_channel)
                else:
                    result = export_object_record(rec, part_dir, bundle_index, asset_graph, uv_channel=uv_channel)
            except Exception as exc:
                skipped.append(f"{name}: {exc}")
                continue
            if not getattr(result, "ok", False) or not getattr(result, "path", None):
                skipped.append(f"{name}: {getattr(result, 'message', 'export skipped')}")
                continue
            part_obj = Path(result.path)
            part_mtl = Path(result.mtl_path) if getattr(result, "mtl_path", None) else None
            try:
                copied_mtl_lines, mat_map = _copy_mtl_prefixed(part_mtl, mtl_path, tex_dir, part_prefix) if part_mtl else ([], {})
                if copied_mtl_lines:
                    mtl_lines.extend([f"# ---- {name} ----"])
                    mtl_lines.extend(copied_mtl_lines)
                    mtl_lines.append("")
                transform_matrix = _record_transform_lookup(record_matrices, rec)
                if transform_matrix is not None and _result_uses_unitypy_obj_basis(result):
                    transform_matrix = _unity_matrix_to_unitypy_obj_basis(transform_matrix)
                part_lines, vc, vtc, vnc, fc = _merge_obj_part(
                    part_obj,
                    name,
                    mat_map,
                    v_base,
                    vt_base,
                    vn_base,
                    transform_matrix=transform_matrix,
                )
                obj_lines.extend(part_lines)
                v_base += vc
                vt_base += vtc
                vn_base += vnc
                total_faces += fc
                exported_parts.append({
                    "name": name,
                    "type": getattr(rec, "type_name", ""),
                    "path_id": getattr(rec, "path_id", None),
                    "source_obj": str(part_obj),
                    "vertices": vc,
                    "uvs": vtc,
                    "normals": vnc,
                    "triangles_estimate": fc,
                    "parent_relative_transform": transform_matrix,
                })
            except Exception as exc:
                skipped.append(f"{name}: merge failed: {exc}")

    if len(exported_parts) < minimum_parts:
        msg = "No renderable descendant exported usable geometry." if allow_single else "Fewer than two selected records exported usable geometry."
        log_path.write_text(
            "Combined OBJ Export\n"
            f"Status: SKIPPED\nReason: {msg}\n"
            f"Skipped: {'; '.join(skipped)}\n",
            encoding="utf-8",
        )
        return MeshExportResult(None, log_path, False, msg)

    obj_path.write_text("\n".join(obj_lines) + "\n", encoding="utf-8", errors="replace")
    if len(mtl_lines) > 3:
        mtl_path.write_text("\n".join(mtl_lines) + "\n", encoding="utf-8", errors="replace")
    else:
        mtl_path.write_text("# Combined export had no material records.\n", encoding="utf-8")

    meta = {
        "ube_version": APP_VERSION,
        "ube_build": APP_BUILD,
        "format": "combined_obj",
        "bundle": str(getattr(bundle_index, "path", "")) if bundle_index is not None else "",
        "uv_channel_exported": int(uv_channel or 0),
        "export": {
            "obj": str(obj_path.relative_to(root)),
            "mtl": str(mtl_path.relative_to(root)),
            "log": str(log_path.relative_to(root)),
        },
        "parts": exported_parts,
        "skipped": skipped,
        "totals": {
            "parts_exported": len(exported_parts),
            "vertices": v_base,
            "triangles_estimate": total_faces,
        },
        "note": (
            "Basis-aware parent-relative transforms were applied to descendant parts; no per-part recentering was applied."
            if record_matrices else
            "Parts are exported in their authored coordinate space; no per-part recentering is applied."
        ),
    }
    json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    log_path.write_text(
        "Combined OBJ Export\n"
        f"Name: {safe}\n"
        f"OBJ: {obj_path}\n"
        f"MTL: {mtl_path}\n"
        f"Metadata: {json_path}\n"
        f"Parts exported: {len(exported_parts):,}\n"
        f"Vertices written: {v_base:,}\n"
        f"Triangles estimate: {total_faces:,}\n"
        f"Skipped: {len(skipped):,}\n"
        + ("Coordinate handling: basis-aware parent-relative transforms applied; UnityPy OBJ parts receive mirrored-X matrix conversion; no per-part recentering.\n" if record_matrices else
           "Coordinate handling: authored/shared coordinates preserved; no per-part recentering.\n")
        + "Status: SUCCESS\n",
        encoding="utf-8",
    )
    return MeshExportResult(obj_path, log_path, True, f"Exported combined OBJ assembly with {len(exported_parts)} parts", mtl_path, json_path)


def _read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("GLB too small")
    magic, version, total_length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError("Not a glTF 2.0 GLB file")
    pos = 12
    gltf: dict[str, Any] | None = None
    blob = b""
    while pos + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<I4s", data, pos)
        pos += 8
        chunk = data[pos:pos + chunk_len]
        pos += chunk_len
        if chunk_type == b"JSON":
            gltf = json.loads(chunk.decode("utf-8"))
        elif chunk_type == b"BIN\x00":
            blob = bytes(chunk)
    if gltf is None:
        raise ValueError("GLB has no JSON chunk")
    return gltf, blob


def _adjust_material_texture_refs(mat: dict[str, Any], tex_offset: int) -> None:
    def adjust_info(info: Any) -> None:
        if isinstance(info, dict) and "index" in info:
            try:
                info["index"] = int(info["index"]) + tex_offset
            except Exception:
                pass
    pbr = mat.get("pbrMetallicRoughness")
    if isinstance(pbr, dict):
        adjust_info(pbr.get("baseColorTexture"))
        adjust_info(pbr.get("metallicRoughnessTexture"))
    for key in ("normalTexture", "occlusionTexture", "emissiveTexture"):
        adjust_info(mat.get(key))


def export_multi_object_glb_records(
    records: list[Any],
    out_dir: str | Path,
    bundle_index: Any | None = None,
    asset_graph: Any | None = None,
    uv_channel: int = 0,
    name_override: str | None = None,
    record_matrices: dict[Any, Any] | None = None,
    allow_single: bool = False,
    record_animation_matrices: dict[Any, Any] | None = None,
    record_skin_payloads: dict[Any, Any] | None = None,
    animation_name: str | None = None,
) -> MeshExportResult:
    """Export several selected renderable records as one GLB scene.

    This reuses UBE's proven single-object GLB exporter for each part, then merges
    the resulting glTF arrays into one GLB with multiple nodes.  Textures remain
    embedded, so the output is still a single file.
    """
    clean_records: list[Any] = []
    seen: set[Any] = set()
    for rec in records or []:
        if rec is None:
            continue
        key = (getattr(rec, "source_name", ""), getattr(rec, "type_name", ""), getattr(rec, "path_id", id(rec)))
        if key in seen:
            continue
        seen.add(key)
        clean_records.append(rec)
    minimum_parts = 1 if allow_single else 2
    if len(clean_records) < minimum_parts:
        root = Path(out_dir)
        log_dir = root / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "multi_object_glb_export.log"
        msg = "Group GLB export needs at least one renderable descendant." if allow_single else "Combined GLB export needs two or more selected renderable objects."
        log_path.write_text(msg, encoding="utf-8")
        return MeshExportResult(None, log_path, False, msg)

    root = Path(out_dir)
    glb_dir = root / "GLB"
    log_dir = root / "Logs"
    meta_dir = root / "Metadata"
    for d in (glb_dir, log_dir, meta_dir):
        d.mkdir(parents=True, exist_ok=True)

    safe = safe_filename(name_override or _multi_export_safe_name(clean_records), "multi_selection")
    animated_export = bool(record_animation_matrices or record_skin_payloads)
    file_suffix = "animated" if animated_export else "combined"

    # Never silently overwrite an earlier export.  Keep the GLB, log and metadata
    # stems together so a repeated export becomes __animated_1, __animated_2,
    # etc. rather than replacing the user's previous result.
    export_stem_base = f"{safe}__{file_suffix}"
    export_stem = export_stem_base
    duplicate_index = 0
    while (
        (glb_dir / f"{export_stem}.glb").exists()
        or (log_dir / f"{export_stem}_glb_export.log").exists()
        or (meta_dir / f"{export_stem}_glb_export.json").exists()
    ):
        duplicate_index += 1
        export_stem = f"{export_stem_base}_{duplicate_index}"

    glb_path = glb_dir / f"{export_stem}.glb"
    log_path = log_dir / f"{export_stem}_glb_export.log"
    json_path = meta_dir / f"{export_stem}_glb_export.json"

    combined: dict[str, Any] = {
        "asset": {"version": "2.0", "generator": f"UBE {APP_VERSION} build {APP_BUILD} combined export"},
        "scenes": [{"nodes": []}],
        "scene": 0,
        "nodes": [],
        "meshes": [],
        "materials": [],
        "samplers": [],
        "textures": [],
        "images": [],
        "bufferViews": [],
        "accessors": [],
        "skins": [],
    }
    blob = bytearray()
    extensions_used: set[str] = set()
    exported_parts: list[dict[str, Any]] = []
    skipped: list[str] = []
    pending_animations: list[dict[str, Any]] = []
    exported_skin_count = 0
    exported_joint_count = 0

    with tempfile.TemporaryDirectory(prefix="ube_multi_glb_export_") as tmp:
        tmp_root = Path(tmp)
        for idx, rec in enumerate(clean_records):
            name = str(getattr(rec, "name", f"part_{idx}"))
            part_dir = tmp_root / f"part_{idx:03d}_{safe_filename(name, 'part')}"
            part_dir.mkdir(parents=True, exist_ok=True)
            try:
                if getattr(rec, "type_name", "") == "Mesh":
                    result = export_mesh_glb_record(rec, part_dir, bundle_index, asset_graph, uv_channel=uv_channel)
                else:
                    result = export_object_glb_record(rec, part_dir, bundle_index, asset_graph, uv_channel=uv_channel)
            except Exception as exc:
                skipped.append(f"{name}: {exc}")
                continue
            if not getattr(result, "ok", False) or not getattr(result, "path", None):
                skipped.append(f"{name}: {getattr(result, 'message', 'export skipped')}")
                continue

            try:
                src_gltf, src_blob = _read_glb(Path(result.path))
            except Exception as exc:
                skipped.append(f"{name}: could not read temporary GLB: {exc}")
                continue

            skin_payload = _record_payload_lookup(record_skin_payloads, rec)
            if skin_payload:
                weights = list(skin_payload.get("weights") or []) if isinstance(skin_payload, dict) else []
                nodes_payload = list(skin_payload.get("nodes") or []) if isinstance(skin_payload, dict) else []
                joints_payload = list(skin_payload.get("joints") or []) if isinstance(skin_payload, dict) else []
                bind_payload = list(skin_payload.get("bind_poses") or []) if isinstance(skin_payload, dict) else []
                position_counts = []
                try:
                    for src_mesh in src_gltf.get("meshes", []) or []:
                        for prim in src_mesh.get("primitives", []) or []:
                            pos_index = (prim.get("attributes") or {}).get("POSITION")
                            if pos_index is not None:
                                position_counts.append(int((src_gltf.get("accessors", []) or [])[int(pos_index)].get("count", 0) or 0))
                except Exception:
                    position_counts = []
                renderer_node_value = int(skin_payload.get("renderer_node_index", -1)) if isinstance(skin_payload, dict) else -1
                raw_skin_times = list(skin_payload.get("times") or []) if isinstance(skin_payload, dict) else []
                joint_indices_valid = bool(joints_payload) and all(0 <= int(index) < len(nodes_payload) for index in joints_payload)
                parent_indices_valid = all(
                    int(node.get("parent_index", -1)) == -1
                    or 0 <= int(node.get("parent_index", -1)) < len(nodes_payload)
                    for node in nodes_payload
                    if isinstance(node, dict)
                )
                node_samples_valid = bool(raw_skin_times) and all(
                    len(list(node.get("matrices") or [])) >= len(raw_skin_times)
                    for node in nodes_payload
                    if isinstance(node, dict)
                )
                max_weight_joint = -1
                try:
                    max_weight_joint = max(
                        int(bone_index)
                        for row in weights
                        for bone_index, weight in (row or [])
                        if float(weight) > 1e-10
                    )
                except ValueError:
                    max_weight_joint = -1
                except Exception:
                    max_weight_joint = len(joints_payload)
                weight_indices_valid = max_weight_joint < len(joints_payload)
                if (
                    not weights or not nodes_payload or not joints_payload
                    or len(bind_payload) != len(joints_payload)
                    or not position_counts or any(count != len(weights) for count in position_counts)
                    or len(joints_payload) > 65535
                    or not joint_indices_valid or not parent_indices_valid
                    or not (0 <= renderer_node_value < len(nodes_payload))
                    or not node_samples_valid or not weight_indices_valid
                ):
                    skipped.append(
                        f"{name}: skinned GLB validation failed "
                        f"(vertices={position_counts or '-'}, weights={len(weights)}, "
                        f"joints={len(joints_payload)}, bind poses={len(bind_payload)}, "
                        f"nodes={len(nodes_payload)}, samples={len(raw_skin_times)})"
                    )
                    continue

            while len(blob) % 4:
                blob.append(0)
            blob_offset = len(blob)
            blob.extend(src_blob)

            accessor_offset = len(combined["accessors"])
            buffer_view_offset = len(combined["bufferViews"])
            image_offset = len(combined["images"])
            sampler_offset = len(combined["samplers"])
            texture_offset = len(combined["textures"])
            material_offset = len(combined["materials"])
            mesh_offset = len(combined["meshes"])
            node_offset = len(combined["nodes"])

            for bv in src_gltf.get("bufferViews", []) or []:
                nbv = copy.deepcopy(bv)
                nbv["buffer"] = 0
                nbv["byteOffset"] = int(nbv.get("byteOffset", 0) or 0) + blob_offset
                combined["bufferViews"].append(nbv)

            for acc in src_gltf.get("accessors", []) or []:
                nacc = copy.deepcopy(acc)
                if "bufferView" in nacc:
                    nacc["bufferView"] = int(nacc["bufferView"]) + buffer_view_offset
                combined["accessors"].append(nacc)

            for sampler in src_gltf.get("samplers", []) or []:
                combined["samplers"].append(copy.deepcopy(sampler))

            for img in src_gltf.get("images", []) or []:
                nimg = copy.deepcopy(img)
                if "bufferView" in nimg:
                    nimg["bufferView"] = int(nimg["bufferView"]) + buffer_view_offset
                combined["images"].append(nimg)

            for tex in src_gltf.get("textures", []) or []:
                ntex = copy.deepcopy(tex)
                if "sampler" in ntex:
                    ntex["sampler"] = int(ntex["sampler"]) + sampler_offset
                if "source" in ntex:
                    ntex["source"] = int(ntex["source"]) + image_offset
                combined["textures"].append(ntex)

            for mat in src_gltf.get("materials", []) or []:
                nmat = copy.deepcopy(mat)
                _adjust_material_texture_refs(nmat, texture_offset)
                combined["materials"].append(nmat)

            for mesh in src_gltf.get("meshes", []) or []:
                nmesh = copy.deepcopy(mesh)
                nmesh["name"] = f"{name} / {nmesh.get('name', 'mesh')}"
                for prim in nmesh.get("primitives", []) or []:
                    if "indices" in prim:
                        prim["indices"] = int(prim["indices"]) + accessor_offset
                    attrs = prim.get("attributes")
                    if isinstance(attrs, dict):
                        for k in list(attrs.keys()):
                            attrs[k] = int(attrs[k]) + accessor_offset
                    if "material" in prim:
                        prim["material"] = int(prim["material"]) + material_offset
                    targets = prim.get("targets")
                    if isinstance(targets, list):
                        for target in targets:
                            if isinstance(target, dict):
                                for k in list(target.keys()):
                                    target[k] = int(target[k]) + accessor_offset
                combined["meshes"].append(nmesh)

            src_nodes = src_gltf.get("nodes", []) or []
            for node in src_nodes:
                nnode = copy.deepcopy(node)
                nnode["name"] = f"{name} / {nnode.get('name', 'node')}"
                if "mesh" in nnode:
                    nnode["mesh"] = int(nnode["mesh"]) + mesh_offset
                if "children" in nnode and isinstance(nnode["children"], list):
                    nnode["children"] = [int(c) + node_offset for c in nnode["children"]]
                combined["nodes"].append(nnode)

            scene_index = int(src_gltf.get("scene", 0) or 0)
            src_scenes = src_gltf.get("scenes", []) or []
            scene_nodes = []
            if 0 <= scene_index < len(src_scenes):
                scene_nodes = src_scenes[scene_index].get("nodes", []) or []
            if not scene_nodes and src_nodes:
                scene_nodes = list(range(len(src_nodes)))
            part_scene_nodes = [int(n) + node_offset for n in scene_nodes]
            transform_matrix = _record_transform_lookup(record_matrices, rec)
            animation_payload = _record_payload_lookup(record_animation_matrices, rec)
            uses_obj_basis = _result_uses_unitypy_obj_basis(result)
            skin_was_exported = False

            if skin_payload and part_scene_nodes:
                raw_times = [float(value) for value in list(skin_payload.get("times") or [])]
                payload_nodes = list(skin_payload.get("nodes") or [])
                payload_joints = [int(value) for value in list(skin_payload.get("joints") or [])]
                renderer_node_local = int(skin_payload.get("renderer_node_index", -1))
                root_bone_local = int(skin_payload.get("root_bone_node_index", -1))
                bind_poses = list(skin_payload.get("bind_poses") or [])
                weights = list(skin_payload.get("weights") or [])

                hierarchy_node_offset = len(combined["nodes"])
                hierarchy_indices = []
                converted_node_rows = []
                for local_index, node_payload in enumerate(payload_nodes):
                    raw_matrices = list(node_payload.get("matrices") or [])
                    count = min(len(raw_times), len(raw_matrices))
                    converted_matrices = []
                    for matrix in raw_matrices[:count]:
                        converted = _coerce_matrix4(matrix)
                        if converted is not None and uses_obj_basis:
                            converted = _unity_matrix_to_unitypy_obj_basis(converted)
                        converted_matrices.append(converted)
                    trs_rows = [_matrix_to_gltf_trs(matrix) for matrix in converted_matrices]
                    if not trs_rows:
                        trs_rows = [_matrix_to_gltf_trs(None)]
                    translations = [row[0] for row in trs_rows]
                    rotations = _quaternion_sequence_continuous([row[1] for row in trs_rows])
                    scales = [row[2] for row in trs_rows]
                    node_index = len(combined["nodes"])
                    hierarchy_indices.append(node_index)
                    combined["nodes"].append({
                        "name": f"{name} / rig / {node_payload.get('name', 'Transform')}",
                        "translation": [float(v) for v in translations[0]],
                        "rotation": [float(v) for v in rotations[0]],
                        "scale": [float(v) for v in scales[0]],
                        "extras": {
                            "ubeSkinHierarchyNode": True,
                            "unityTransformPathID": node_payload.get("path_id"),
                        },
                    })
                    converted_node_rows.append((translations, rotations, scales))

                for local_index, node_payload in enumerate(payload_nodes):
                    parent_local = int(node_payload.get("parent_index", -1))
                    node_index = hierarchy_indices[local_index]
                    if 0 <= parent_local < len(hierarchy_indices):
                        parent_index = hierarchy_indices[parent_local]
                        combined["nodes"][parent_index].setdefault("children", []).append(node_index)
                    else:
                        combined["scenes"][0]["nodes"].append(node_index)

                if not (0 <= renderer_node_local < len(hierarchy_indices)):
                    raise ValueError(f"Skinned renderer hierarchy for {name} has no renderer node")
                renderer_node_index = hierarchy_indices[renderer_node_local]

                position_accessor_indices = set()
                for mesh_index in range(mesh_offset, mesh_offset + len(src_gltf.get("meshes", []) or [])):
                    mesh_row = combined["meshes"][mesh_index]
                    for prim in mesh_row.get("primitives", []) or []:
                        attrs = prim.get("attributes") or {}
                        if "POSITION" in attrs:
                            position_accessor_indices.add(int(attrs["POSITION"]))
                position_counts = {
                    int(combined["accessors"][accessor_index].get("count", 0) or 0)
                    for accessor_index in position_accessor_indices
                    if 0 <= accessor_index < len(combined["accessors"])
                }
                if len(position_counts) != 1:
                    raise ValueError(
                        f"Skinned renderer {name} uses incompatible primitive vertex layouts: "
                        f"{sorted(position_counts)}"
                    )
                exported_vertex_count = next(iter(position_counts))
                source_vertex_indices, vertex_map_method = _skin_source_vertex_indices(
                    skin_payload.get("mesh_record"),
                    uv_channel,
                )
                remapped_weights = _skin_remap_weights_for_gltf(
                    weights,
                    source_vertex_indices,
                    exported_vertex_count,
                )
                joint_vectors, weight_vectors = _skin_weight_vectors(remapped_weights, exported_vertex_count)
                joint_view = _glb_add_buffer_view(
                    blob, combined["bufferViews"],
                    _glb_pack_ushorts([value for row in joint_vectors for value in row]),
                    _GLTF_ARRAY_BUFFER,
                )
                joint_accessor = _glb_add_accessor(
                    combined["accessors"], joint_view, _GLTF_UNSIGNED_SHORT,
                    len(joint_vectors), "VEC4",
                )
                weight_view = _glb_add_buffer_view(
                    blob, combined["bufferViews"],
                    _glb_pack_floats(_glb_flatten_vecs(weight_vectors, 4)),
                    _GLTF_ARRAY_BUFFER,
                )
                weight_accessor = _glb_add_accessor(
                    combined["accessors"], weight_view, _GLTF_FLOAT,
                    len(weight_vectors), "VEC4",
                )

                converted_bind_poses = []
                for matrix in bind_poses:
                    converted = _coerce_matrix4(matrix)
                    if converted is not None and uses_obj_basis:
                        converted = _unity_matrix_to_unitypy_obj_basis(converted)
                    converted_bind_poses.extend(_matrix_to_gltf_column_major_full(converted))
                bind_view = _glb_add_buffer_view(
                    blob, combined["bufferViews"],
                    _glb_pack_floats(converted_bind_poses),
                )
                bind_accessor = _glb_add_accessor(
                    combined["accessors"], bind_view, _GLTF_FLOAT,
                    len(bind_poses), "MAT4",
                )

                skin_index = len(combined["skins"])
                skin_row = {
                    "name": f"{name} / skin",
                    "joints": [hierarchy_indices[index] for index in payload_joints],
                    "inverseBindMatrices": int(bind_accessor),
                    "extras": {
                        "ubeSkinnedExport": True,
                        "unityRecordPathID": getattr(rec, "path_id", None),
                        "ubeWeightVertexMap": vertex_map_method,
                        "ubeExportedVertexCount": int(exported_vertex_count),
                    },
                }
                # glTF's optional ``skeleton`` hint must be a common root of all
                # joints. Unity's m_RootBone is not guaranteed to satisfy that,
                # especially for rigs that include controller/helper branches.
                # Omitting the hint is valid and lets viewers derive the hierarchy
                # from the joint nodes without a false validator error.
                combined["skins"].append(skin_row)

                part_mesh_nodes = []
                for node_index in range(node_offset, node_offset + len(src_nodes)):
                    node_row = combined["nodes"][node_index]
                    if "mesh" in node_row:
                        node_row["skin"] = skin_index
                        part_mesh_nodes.append(node_index)
                if not part_mesh_nodes:
                    raise ValueError(f"Skinned renderer {name} exported no mesh-bearing glTF node")
                nested_mesh_nodes = [node for node in part_mesh_nodes if node not in part_scene_nodes]
                if nested_mesh_nodes:
                    raise ValueError(
                        f"Skinned renderer {name} uses a nested mesh-node layout that is not yet exported safely"
                    )
                # A glTF node carrying both ``mesh`` and ``skin`` must not rely on
                # parent transforms; validators warn that those transforms do not
                # affect the skinned result. Keep the skinned mesh node at scene
                # root and the joint hierarchy as a separate scene-root branch,
                # matching the layout produced by established DCC exporters.
                for mesh_node_index in part_mesh_nodes:
                    if mesh_node_index not in combined["scenes"][0]["nodes"]:
                        combined["scenes"][0]["nodes"].append(mesh_node_index)

                for mesh_index in range(mesh_offset, mesh_offset + len(src_gltf.get("meshes", []) or [])):
                    mesh_row = combined["meshes"][mesh_index]
                    for prim in mesh_row.get("primitives", []) or []:
                        attrs = prim.setdefault("attributes", {})
                        attrs["JOINTS_0"] = int(joint_accessor)
                        attrs["WEIGHTS_0"] = int(weight_accessor)

                count = min(len(raw_times), min((len(node.get("matrices") or []) for node in payload_nodes), default=0))
                skin_times = raw_times[:count]
                if skin_times:
                    for local_index, (translations, rotations, scales) in enumerate(converted_node_rows):
                        pending_animations.append({
                            "node": hierarchy_indices[local_index],
                            "times": skin_times,
                            "translation": translations[:count],
                            "rotation": rotations[:count],
                            "scale": scales[:count],
                            "record": rec,
                            "skin_node": True,
                        })
                exported_skin_count += 1
                exported_joint_count += len(payload_joints)
                skin_was_exported = True
                animation_payload = None
                transform_matrix = None

            if not skin_was_exported and animation_payload and part_scene_nodes:
                raw_times = list(animation_payload.get("times") or []) if isinstance(animation_payload, dict) else []
                raw_matrices = list(animation_payload.get("matrices") or []) if isinstance(animation_payload, dict) else []
                count = min(len(raw_times), len(raw_matrices))
                raw_times = [float(v) for v in raw_times[:count]]
                converted_matrices = []
                for matrix in raw_matrices[:count]:
                    converted = _coerce_matrix4(matrix)
                    if converted is not None and uses_obj_basis:
                        converted = _unity_matrix_to_unitypy_obj_basis(converted)
                    converted_matrices.append(converted)
                for matrix_index, matrix in enumerate(converted_matrices):
                    shear = _matrix_gltf_trs_shear(matrix)
                    if shear > 2e-4:
                        sample_time = raw_times[matrix_index] if matrix_index < len(raw_times) else 0.0
                        raise ValueError(
                            f"Rigid animation for {name} contains affine shear at "
                            f"{sample_time:.6f} s (normalized basis error {shear:.6g}). "
                            "This matrix cannot be represented by a glTF node's translation, rotation and scale."
                        )
                trs_rows = [_matrix_to_gltf_trs(matrix) for matrix in converted_matrices]
                if raw_times and trs_rows:
                    translations = [row[0] for row in trs_rows]
                    rotations = _quaternion_sequence_continuous([row[1] for row in trs_rows])
                    scales = [row[2] for row in trs_rows]
                    wrapper_index = len(combined["nodes"])
                    combined["nodes"].append({
                        "name": f"{name} / animated transform",
                        "translation": [float(v) for v in translations[0]],
                        "rotation": [float(v) for v in rotations[0]],
                        "scale": [float(v) for v in scales[0]],
                        "children": part_scene_nodes,
                        "extras": {
                            "ubeAnimatedWrapper": True,
                            "unityRecordPathID": getattr(rec, "path_id", None),
                        },
                    })
                    combined["scenes"][0]["nodes"].append(wrapper_index)
                    pending_animations.append({
                        "node": wrapper_index,
                        "times": raw_times,
                        "translation": translations,
                        "rotation": rotations,
                        "scale": scales,
                        "record": rec,
                    })
                    transform_matrix = converted_matrices[0]
                else:
                    animation_payload = None

            if not skin_was_exported and not animation_payload:
                # Native GLB geometry is normally decoded in Unity coordinates, so its
                # Unity matrix is already correct. Only the rare GLB fallback that was
                # rebuilt from UnityPy's mirrored-X OBJ output needs C × M × C.
                if transform_matrix is not None and uses_obj_basis:
                    transform_matrix = _unity_matrix_to_unitypy_obj_basis(transform_matrix)
                gltf_matrix = _matrix_to_gltf_column_major(transform_matrix)
                if gltf_matrix and part_scene_nodes:
                    wrapper_index = len(combined["nodes"])
                    combined["nodes"].append({
                        "name": f"{name} / parent-relative transform",
                        "matrix": gltf_matrix,
                        "children": part_scene_nodes,
                    })
                    combined["scenes"][0]["nodes"].append(wrapper_index)
                else:
                    combined["scenes"][0]["nodes"].extend(part_scene_nodes)

            for ext in src_gltf.get("extensionsUsed", []) or []:
                extensions_used.add(str(ext))

            exported_parts.append({
                "name": name,
                "type": getattr(rec, "type_name", ""),
                "path_id": getattr(rec, "path_id", None),
                "temporary_glb": str(result.path),
                "nodes_added": len(src_nodes),
                "meshes_added": len(src_gltf.get("meshes", []) or []),
                "materials_added": len(src_gltf.get("materials", []) or []),
                "images_added": len(src_gltf.get("images", []) or []),
                "parent_relative_transform": transform_matrix,
                "skinned": bool(skin_was_exported),
            })

    if len(exported_parts) < minimum_parts:
        msg = "No renderable descendant exported usable GLB geometry." if allow_single else "Fewer than two selected records exported usable GLB geometry."
        log_path.write_text(
            "Combined GLB Export\n"
            f"Status: SKIPPED\nReason: {msg}\n"
            f"Skipped: {'; '.join(skipped)}\n",
            encoding="utf-8",
        )
        return MeshExportResult(None, log_path, False, msg)

    animation_channel_count = 0
    animation_sampler_count = 0
    if pending_animations:
        gltf_animation = {
            "name": str(animation_name or name_override or safe or "Animation"),
            "samplers": [],
            "channels": [],
            "extras": {
                "ubeBakedVisualAnimation": True,
                "ubeSkinnedAnimation": bool(exported_skin_count),
                "note": "Visible rigid transforms and resolved local skin hierarchies baked at the source clip sample rate.",
            },
        }
        time_accessor_cache: dict[tuple[float, ...], int] = {}
        for row in pending_animations:
            raw_times = list(row.get("times") or [])
            times, keep_indices = _glb_strict_time_indices(raw_times)
            if len(times) < 2:
                continue
            time_key = tuple(times)
            input_accessor = time_accessor_cache.get(time_key)
            if input_accessor is None:
                time_view = _glb_add_buffer_view(blob, combined["bufferViews"], _glb_pack_floats(times))
                input_accessor = _glb_add_accessor(
                    combined["accessors"], time_view, _GLTF_FLOAT, len(times), "SCALAR",
                    [min(times)], [max(times)],
                )
                time_accessor_cache[time_key] = input_accessor

            for path_name, type_name, width in (
                ("translation", "VEC3", 3),
                ("rotation", "VEC4", 4),
                ("scale", "VEC3", 3),
            ):
                raw_values = list(row.get(path_name) or [])
                if len(raw_values) != len(raw_times):
                    continue
                values = [raw_values[index] for index in keep_indices if index < len(raw_values)]
                if len(values) != len(times) or not _animation_values_change(values):
                    continue
                value_view = _glb_add_buffer_view(
                    blob, combined["bufferViews"],
                    _glb_pack_floats(_glb_flatten_vecs(values, width)),
                )
                mins, maxs = _glb_bounds(values, width) if path_name != "rotation" else (None, None)
                output_accessor = _glb_add_accessor(
                    combined["accessors"], value_view, _GLTF_FLOAT, len(values), type_name, mins, maxs,
                )
                sampler_index = len(gltf_animation["samplers"])
                gltf_animation["samplers"].append({
                    "input": int(input_accessor),
                    "output": int(output_accessor),
                    "interpolation": "LINEAR",
                })
                gltf_animation["channels"].append({
                    "sampler": sampler_index,
                    "target": {"node": int(row["node"]), "path": path_name},
                })
        if gltf_animation["channels"]:
            combined["animations"] = [gltf_animation]
            animation_channel_count = len(gltf_animation["channels"])
            animation_sampler_count = len(gltf_animation["samplers"])

    if not combined.get("skins"):
        combined.pop("skins", None)
    if extensions_used:
        combined["extensionsUsed"] = sorted(extensions_used)
    glb_path.write_bytes(_glb_make_glb_bytes(combined, blob))

    meta = {
        "ube_version": APP_VERSION,
        "ube_build": APP_BUILD,
        "format": "animated_glb" if pending_animations else "combined_glb",
        "bundle": str(getattr(bundle_index, "path", "")) if bundle_index is not None else "",
        "uv_channel_exported": int(uv_channel or 0),
        "export": {
            "glb": str(glb_path.relative_to(root)),
            "log": str(log_path.relative_to(root)),
        },
        "parts": exported_parts,
        "skipped": skipped,
        "totals": {
            "parts_exported": len(exported_parts),
            "nodes": len(combined.get("nodes", [])),
            "meshes": len(combined.get("meshes", [])),
            "materials": len(combined.get("materials", [])),
            "images": len(combined.get("images", [])),
            "animation_channels": animation_channel_count,
            "animation_samplers": animation_sampler_count,
            "skins": exported_skin_count,
            "joints": exported_joint_count,
        },
        "note": (
            (
                "One GLB scene with glTF skins, local bone/helper hierarchy animation, and rigid wrapper animation; unsupported Unity runtime systems are deliberately excluded."
                if exported_skin_count else
                "One GLB scene with baked rigid visual animation on wrapper nodes; unsupported Unity runtime systems are deliberately excluded."
            )
            if pending_animations else
            (
                "One GLB scene with basis-aware parent-relative transforms stored on wrapper nodes; no per-part recentering is applied."
                if record_matrices else
                "One GLB scene with one node/mesh set per selected part. Authored coordinates are preserved; no per-part recentering is applied."
            )
        ),
        "animation": {
            "name": str(animation_name or ""),
            "animated_parts": len(pending_animations),
            "channels": animation_channel_count,
            "samplers": animation_sampler_count,
            "skins": exported_skin_count,
            "joints": exported_joint_count,
        } if pending_animations else None,
    }
    json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    log_path.write_text(
        ("Animated GLB Export\n" if pending_animations else "Combined GLB Export\n")
        + f"Name: {safe}\n"
        f"GLB: {glb_path}\n"
        f"Metadata: {json_path}\n"
        f"Parts exported: {len(exported_parts):,}\n"
        f"Nodes: {len(combined.get('nodes', [])):,}\n"
        f"Meshes: {len(combined.get('meshes', [])):,}\n"
        f"Materials: {len(combined.get('materials', [])):,}\n"
        f"Images embedded: {len(combined.get('images', [])):,}\n"
        f"Animation channels: {animation_channel_count:,}\n"
        f"Animated parts: {len(pending_animations):,}\n"
        f"Skipped: {len(skipped):,}\n"
        + ("Coordinate handling: basis-aware parent-relative transforms applied; UnityPy OBJ fallback receives mirrored-X matrix conversion; no per-part recentering.\n" if record_matrices else
           "Coordinate handling: authored/shared coordinates preserved; no per-part recentering.\n")
        + "Status: SUCCESS\n",
        encoding="utf-8",
    )
    message = (
        f"Exported animated GLB with {len(exported_parts)} parts, {exported_skin_count} skin(s), and {animation_channel_count} animation channels"
        if pending_animations else
        f"Exported combined GLB assembly with {len(exported_parts)} parts"
    )
    return MeshExportResult(glb_path, log_path, True, message, None, json_path)

