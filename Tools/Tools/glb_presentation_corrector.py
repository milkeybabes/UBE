#!/usr/bin/env python3
r"""
GLB Presentation Corrector
==========================

Re-centres and optionally rotates a GLB with a presentation transform.
Static scene roots are placed beneath one parent node. Skinned mesh nodes stay
at the scene root as required by glTF; the presentation parent is applied to
their joint hierarchy instead. Original meshes, skins, materials and animation
tracks remain unchanged.

No third-party packages are required.

Typical examples
----------------
Centre horizontally, place the model on Y=0:
    python glb_presentation_corrector.py "Model.glb"

Turn the model around as well:
    python glb_presentation_corrector.py "Model.glb" --rotate-y 180

Centre around the full XYZ bounding box rather than grounding it:
    python glb_presentation_corrector.py "Model.glb" --center xyz --no-ground

Use the complete animated travel area:
    python glb_presentation_corrector.py "Model.glb" --bounds animation --samples 120

Process every GLB in a folder:
    python glb_presentation_corrector.py "D:\Exports" --recursive --rotate-y 180

Notes
-----
* The source GLB is never overwritten unless --overwrite is explicitly used.
* Default output suffix: "_presented".
* Default bounds mode is the first frame of animation 0, or the rest pose when
  the file contains no animation.
* Animated bounds follow node TRS animation. Skin deformation is not evaluated;
  the mesh's authored local bounds are transformed by the animated node tree.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

GLB_MAGIC = 0x46546C67
GLB_VERSION = 2
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
TOOL_VERSION = "1.1"
TOOL_MARKER = "glb_presentation_corrector"
TOOL_ROOT_NAME = "PresentationRoot_Corrector"

COMPONENT_FORMATS = {
    5120: ("b", 1),   # BYTE
    5121: ("B", 1),   # UNSIGNED_BYTE
    5122: ("h", 2),   # SHORT
    5123: ("H", 2),   # UNSIGNED_SHORT
    5125: ("I", 4),   # UNSIGNED_INT
    5126: ("f", 4),   # FLOAT
}
TYPE_COMPONENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}

Vec3 = Tuple[float, float, float]
Quat = Tuple[float, float, float, float]
Mat4 = List[List[float]]
Bounds = Tuple[Vec3, Vec3]


@dataclass
class GlbChunk:
    chunk_type: int
    data: bytes


@dataclass
class LoadedGlb:
    document: Dict[str, Any]
    chunks: List[GlbChunk]
    bin_data: bytes


def identity_matrix() -> Mat4:
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def matrix_multiply(a: Mat4, b: Mat4) -> Mat4:
    return [
        [
            sum(a[row][k] * b[k][col] for k in range(4))
            for col in range(4)
        ]
        for row in range(4)
    ]


def transform_point(m: Mat4, point: Sequence[float]) -> Vec3:
    x, y, z = float(point[0]), float(point[1]), float(point[2])
    return (
        m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
        m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
        m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3],
    )


def quaternion_normalize(q: Sequence[float]) -> Quat:
    x, y, z, w = map(float, q)
    length = math.sqrt(x * x + y * y + z * z + w * w)
    if length <= 1e-20:
        return (0.0, 0.0, 0.0, 1.0)
    return (x / length, y / length, z / length, w / length)


def quaternion_slerp(a: Sequence[float], b: Sequence[float], t: float) -> Quat:
    ax, ay, az, aw = quaternion_normalize(a)
    bx, by, bz, bw = quaternion_normalize(b)
    dot = ax * bx + ay * by + az * bz + aw * bw

    if dot < 0.0:
        bx, by, bz, bw = -bx, -by, -bz, -bw
        dot = -dot

    if dot > 0.9995:
        result = (
            ax + t * (bx - ax),
            ay + t * (by - ay),
            az + t * (bz - az),
            aw + t * (bw - aw),
        )
        return quaternion_normalize(result)

    dot = max(-1.0, min(1.0, dot))
    theta_0 = math.acos(dot)
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * t
    s0 = math.sin(theta_0 - theta) / sin_theta_0
    s1 = math.sin(theta) / sin_theta_0
    return (
        s0 * ax + s1 * bx,
        s0 * ay + s1 * by,
        s0 * az + s1 * bz,
        s0 * aw + s1 * bw,
    )


def trs_matrix(
    translation: Sequence[float],
    rotation: Sequence[float],
    scale: Sequence[float],
) -> Mat4:
    tx, ty, tz = map(float, translation)
    sx, sy, sz = map(float, scale)
    x, y, z, w = quaternion_normalize(rotation)

    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z

    # Rotation columns multiplied by scale: M = T * R * S.
    return [
        [(1.0 - 2.0 * (yy + zz)) * sx, (2.0 * (xy - wz)) * sy, (2.0 * (xz + wy)) * sz, tx],
        [(2.0 * (xy + wz)) * sx, (1.0 - 2.0 * (xx + zz)) * sy, (2.0 * (yz - wx)) * sz, ty],
        [(2.0 * (xz - wy)) * sx, (2.0 * (yz + wx)) * sy, (1.0 - 2.0 * (xx + yy)) * sz, tz],
        [0.0, 0.0, 0.0, 1.0],
    ]


def gltf_matrix_to_internal(values: Sequence[float]) -> Mat4:
    if len(values) != 16:
        raise ValueError("A glTF node matrix must contain 16 values.")
    # glTF stores matrices column-major.
    return [[float(values[col * 4 + row]) for col in range(4)] for row in range(4)]


def y_rotation_quaternion(degrees: float) -> Quat:
    radians = math.radians(degrees)
    half = radians * 0.5
    return (0.0, math.sin(half), 0.0, math.cos(half))


def y_rotation_matrix(degrees: float) -> Mat4:
    return trs_matrix((0.0, 0.0, 0.0), y_rotation_quaternion(degrees), (1.0, 1.0, 1.0))


def bounds_union(current: Optional[Bounds], other: Bounds) -> Bounds:
    if current is None:
        return other
    a_min, a_max = current
    b_min, b_max = other
    return (
        (
            min(a_min[0], b_min[0]),
            min(a_min[1], b_min[1]),
            min(a_min[2], b_min[2]),
        ),
        (
            max(a_max[0], b_max[0]),
            max(a_max[1], b_max[1]),
            max(a_max[2], b_max[2]),
        ),
    )


def bounds_corners(bounds: Bounds) -> Iterable[Vec3]:
    minimum, maximum = bounds
    for x in (minimum[0], maximum[0]):
        for y in (minimum[1], maximum[1]):
            for z in (minimum[2], maximum[2]):
                yield (x, y, z)


def transformed_bounds(bounds: Bounds, matrix: Mat4) -> Bounds:
    points = [transform_point(matrix, corner) for corner in bounds_corners(bounds)]
    return (
        (
            min(p[0] for p in points),
            min(p[1] for p in points),
            min(p[2] for p in points),
        ),
        (
            max(p[0] for p in points),
            max(p[1] for p in points),
            max(p[2] for p in points),
        ),
    )


def format_vec3(value: Sequence[float]) -> str:
    return f"({value[0]:.6g}, {value[1]:.6g}, {value[2]:.6g})"


def load_glb(path: Path) -> LoadedGlb:
    raw = path.read_bytes()
    if len(raw) < 12:
        raise ValueError("File is too short to be a GLB.")

    magic, version, declared_length = struct.unpack_from("<III", raw, 0)
    if magic != GLB_MAGIC:
        raise ValueError("Not a GLB file: invalid magic.")
    if version != GLB_VERSION:
        raise ValueError(f"Unsupported GLB version {version}; expected version 2.")
    if declared_length != len(raw):
        raise ValueError(
            f"GLB length mismatch: header says {declared_length}, file has {len(raw)} bytes."
        )

    offset = 12
    chunks: List[GlbChunk] = []
    document: Optional[Dict[str, Any]] = None
    bin_data = b""

    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError("Truncated GLB chunk header.")
        chunk_length, chunk_type = struct.unpack_from("<II", raw, offset)
        offset += 8
        end = offset + chunk_length
        if end > len(raw):
            raise ValueError("Truncated GLB chunk data.")
        data = raw[offset:end]
        offset = end
        chunks.append(GlbChunk(chunk_type=chunk_type, data=data))

        if chunk_type == JSON_CHUNK and document is None:
            json_text = data.rstrip(b" \t\r\n\x00").decode("utf-8")
            document = json.loads(json_text)
        elif chunk_type == BIN_CHUNK and not bin_data:
            bin_data = data

    if document is None:
        raise ValueError("GLB contains no JSON chunk.")

    return LoadedGlb(document=document, chunks=chunks, bin_data=bin_data)


def write_glb(path: Path, loaded: LoadedGlb) -> None:
    json_bytes = json.dumps(
        loaded.document,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)

    rebuilt_chunks: List[GlbChunk] = []
    replaced = False
    for chunk in loaded.chunks:
        if chunk.chunk_type == JSON_CHUNK and not replaced:
            rebuilt_chunks.append(GlbChunk(JSON_CHUNK, json_bytes))
            replaced = True
        else:
            rebuilt_chunks.append(chunk)

    if not replaced:
        rebuilt_chunks.insert(0, GlbChunk(JSON_CHUNK, json_bytes))

    total_length = 12 + sum(8 + len(chunk.data) for chunk in rebuilt_chunks)
    output = bytearray(struct.pack("<III", GLB_MAGIC, GLB_VERSION, total_length))
    for chunk in rebuilt_chunks:
        output += struct.pack("<II", len(chunk.data), chunk.chunk_type)
        output += chunk.data
    path.write_bytes(output)


class AccessorReader:
    def __init__(self, document: Dict[str, Any], bin_data: bytes):
        self.document = document
        self.bin_data = bin_data
        self._cache: Dict[int, List[Any]] = {}

    def read(self, accessor_index: int) -> List[Any]:
        if accessor_index in self._cache:
            return self._cache[accessor_index]

        accessors = self.document.get("accessors", [])
        buffer_views = self.document.get("bufferViews", [])
        accessor = accessors[accessor_index]

        if "sparse" in accessor:
            raise ValueError(
                f"Accessor {accessor_index} uses sparse storage, which this utility does not support."
            )
        if "bufferView" not in accessor:
            raise ValueError(f"Accessor {accessor_index} has no bufferView.")

        component_type = int(accessor["componentType"])
        if component_type not in COMPONENT_FORMATS:
            raise ValueError(
                f"Accessor {accessor_index} uses unsupported component type {component_type}."
            )
        fmt_char, component_size = COMPONENT_FORMATS[component_type]
        component_count = TYPE_COMPONENTS.get(accessor["type"])
        if component_count is None:
            raise ValueError(
                f"Accessor {accessor_index} uses unsupported type {accessor['type']}."
            )

        view = buffer_views[int(accessor["bufferView"])]
        if int(view.get("buffer", 0)) != 0:
            raise ValueError(
                f"Accessor {accessor_index} points to external/non-primary buffer "
                f"{view.get('buffer')}; only embedded GLB buffer 0 is supported."
            )

        base_offset = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
        element_size = component_size * component_count
        stride = int(view.get("byteStride", element_size))
        count = int(accessor["count"])
        normalized = bool(accessor.get("normalized", False))
        fmt = "<" + fmt_char * component_count

        values: List[Any] = []
        for index in range(count):
            start = base_offset + index * stride
            end = start + element_size
            if end > len(self.bin_data):
                raise ValueError(f"Accessor {accessor_index} exceeds the BIN chunk.")
            unpacked = struct.unpack_from(fmt, self.bin_data, start)
            converted = self._normalize_components(
                unpacked, component_type, normalized
            )
            if component_count == 1:
                values.append(converted[0])
            else:
                values.append(tuple(converted))

        self._cache[accessor_index] = values
        return values

    @staticmethod
    def _normalize_components(
        values: Sequence[float],
        component_type: int,
        normalized: bool,
    ) -> List[float]:
        if not normalized or component_type == 5126:
            return [float(value) for value in values]

        if component_type == 5120:
            return [max(float(v) / 127.0, -1.0) for v in values]
        if component_type == 5121:
            return [float(v) / 255.0 for v in values]
        if component_type == 5122:
            return [max(float(v) / 32767.0, -1.0) for v in values]
        if component_type == 5123:
            return [float(v) / 65535.0 for v in values]
        if component_type == 5125:
            return [float(v) / 4294967295.0 for v in values]
        return [float(value) for value in values]


def accessor_bounds(
    document: Dict[str, Any],
    reader: AccessorReader,
    accessor_index: int,
) -> Bounds:
    accessor = document["accessors"][accessor_index]
    if accessor.get("type") != "VEC3":
        raise ValueError(
            f"POSITION accessor {accessor_index} is {accessor.get('type')}, not VEC3."
        )

    if "min" in accessor and "max" in accessor:
        minimum = tuple(map(float, accessor["min"][:3]))
        maximum = tuple(map(float, accessor["max"][:3]))
        return (minimum, maximum)  # type: ignore[return-value]

    values = reader.read(accessor_index)
    if not values:
        raise ValueError(f"POSITION accessor {accessor_index} is empty.")
    return (
        (
            min(v[0] for v in values),
            min(v[1] for v in values),
            min(v[2] for v in values),
        ),
        (
            max(v[0] for v in values),
            max(v[1] for v in values),
            max(v[2] for v in values),
        ),
    )


def build_mesh_bounds(
    document: Dict[str, Any],
    reader: AccessorReader,
) -> List[Optional[Bounds]]:
    result: List[Optional[Bounds]] = []
    for mesh in document.get("meshes", []):
        mesh_bounds: Optional[Bounds] = None
        for primitive in mesh.get("primitives", []):
            position_accessor = primitive.get("attributes", {}).get("POSITION")
            if position_accessor is None:
                continue
            primitive_bounds = accessor_bounds(
                document, reader, int(position_accessor)
            )
            mesh_bounds = bounds_union(mesh_bounds, primitive_bounds)
        result.append(mesh_bounds)
    return result


def node_base_trs(node: Dict[str, Any]) -> Tuple[Vec3, Quat, Vec3]:
    translation = tuple(map(float, node.get("translation", (0.0, 0.0, 0.0))))
    rotation = quaternion_normalize(node.get("rotation", (0.0, 0.0, 0.0, 1.0)))
    scale = tuple(map(float, node.get("scale", (1.0, 1.0, 1.0))))
    return translation, rotation, scale  # type: ignore[return-value]


def sample_channel(
    reader: AccessorReader,
    sampler: Dict[str, Any],
    target_path: str,
    time_value: float,
) -> Sequence[float]:
    times = [float(v) for v in reader.read(int(sampler["input"]))]
    outputs = reader.read(int(sampler["output"]))
    if not times:
        raise ValueError("Animation sampler has no key times.")

    interpolation = str(sampler.get("interpolation", "LINEAR")).upper()
    cubic = interpolation == "CUBICSPLINE"

    def output_value(key_index: int) -> Sequence[float]:
        value_index = key_index * 3 + 1 if cubic else key_index
        value = outputs[value_index]
        if isinstance(value, tuple):
            return value
        return (float(value),)

    if time_value <= times[0]:
        return output_value(0)
    if time_value >= times[-1]:
        return output_value(len(times) - 1)

    right = bisect.bisect_right(times, time_value)
    left = right - 1
    if interpolation == "STEP":
        return output_value(left)

    t0, t1 = times[left], times[right]
    amount = 0.0 if abs(t1 - t0) <= 1e-20 else (time_value - t0) / (t1 - t0)
    a = output_value(left)
    b = output_value(right)

    # For bounds purposes, cubic spline values are approximated linearly between
    # stored key values. The original animation data remains untouched.
    if target_path == "rotation":
        return quaternion_slerp(a, b, amount)

    return tuple(
        float(a[index]) + (float(b[index]) - float(a[index])) * amount
        for index in range(min(len(a), len(b)))
    )


def animation_time_range(
    document: Dict[str, Any],
    reader: AccessorReader,
    animation_index: int,
) -> Tuple[float, float]:
    animations = document.get("animations", [])
    if not animations:
        return (0.0, 0.0)
    if not 0 <= animation_index < len(animations):
        raise ValueError(
            f"Animation index {animation_index} is outside 0..{len(animations) - 1}."
        )

    animation = animations[animation_index]
    starts: List[float] = []
    ends: List[float] = []
    for sampler in animation.get("samplers", []):
        times = [float(v) for v in reader.read(int(sampler["input"]))]
        if times:
            starts.append(times[0])
            ends.append(times[-1])
    if not starts:
        return (0.0, 0.0)
    return (min(starts), max(ends))


def animation_overrides(
    document: Dict[str, Any],
    reader: AccessorReader,
    animation_index: int,
    time_value: float,
) -> Dict[int, Dict[str, Sequence[float]]]:
    animations = document.get("animations", [])
    if not animations:
        return {}
    animation = animations[animation_index]
    samplers = animation.get("samplers", [])
    overrides: Dict[int, Dict[str, Sequence[float]]] = {}

    for channel in animation.get("channels", []):
        target = channel.get("target", {})
        node_index = target.get("node")
        target_path = target.get("path")
        if node_index is None or target_path not in {"translation", "rotation", "scale"}:
            continue
        sampler_index = int(channel["sampler"])
        sampled = sample_channel(
            reader,
            samplers[sampler_index],
            str(target_path),
            time_value,
        )
        overrides.setdefault(int(node_index), {})[str(target_path)] = sampled
    return overrides


def local_node_matrix(
    node: Dict[str, Any],
    override: Optional[Dict[str, Sequence[float]]] = None,
) -> Mat4:
    if "matrix" in node and not override:
        return gltf_matrix_to_internal(node["matrix"])

    translation, rotation, scale = node_base_trs(node)
    if override:
        translation = tuple(
            map(float, override.get("translation", translation))
        )  # type: ignore[assignment]
        rotation = quaternion_normalize(override.get("rotation", rotation))
        scale = tuple(
            map(float, override.get("scale", scale))
        )  # type: ignore[assignment]
    return trs_matrix(translation, rotation, scale)


def _scene_world_matrices(
    document: Dict[str, Any],
    scene_index: int,
    overrides: Dict[int, Dict[str, Sequence[float]]],
) -> Tuple[Dict[int, Mat4], List[int]]:
    scenes = document.get("scenes", [])
    nodes = document.get("nodes", [])
    if not scenes:
        return {}, []

    world_matrices: Dict[int, Mat4] = {}
    traversal_order: List[int] = []
    visiting: set[int] = set()

    def visit(node_index: int, parent_matrix: Mat4) -> None:
        if node_index in visiting:
            raise ValueError(f"Cycle detected in node hierarchy at node {node_index}.")
        if node_index in world_matrices:
            raise ValueError(
                f"Node {node_index} is reached more than once; glTF scenes must be trees."
            )
        visiting.add(node_index)
        node = nodes[node_index]
        local = local_node_matrix(node, overrides.get(node_index))
        world = matrix_multiply(parent_matrix, local)
        world_matrices[node_index] = world
        traversal_order.append(node_index)
        for child_value in node.get("children", []):
            visit(int(child_value), world)
        visiting.remove(node_index)

    for root_value in scenes[scene_index].get("nodes", []):
        visit(int(root_value), identity_matrix())
    return world_matrices, traversal_order


def _sampled_vertex_indices(count: int, limit: int) -> range | List[int]:
    if limit <= 0 or count <= limit:
        return range(count)
    if limit == 1:
        return [0]
    values = {
        int(round(index * (count - 1) / (limit - 1)))
        for index in range(limit)
    }
    return sorted(values)


def _skin_joint_matrices(
    document: Dict[str, Any],
    reader: AccessorReader,
    skin_index: int,
    world_matrices: Dict[int, Mat4],
) -> List[Mat4]:
    skins = document.get("skins", [])
    if not 0 <= skin_index < len(skins):
        raise ValueError(f"Invalid skin index {skin_index}.")
    skin = skins[skin_index]
    joints = [int(value) for value in skin.get("joints", [])]
    if not joints:
        raise ValueError(f"Skin {skin_index} contains no joints.")

    ibm_accessor = skin.get("inverseBindMatrices")
    if ibm_accessor is None:
        inverse_bind_matrices = [identity_matrix() for _ in joints]
    else:
        raw_ibms = reader.read(int(ibm_accessor))
        if len(raw_ibms) != len(joints):
            raise ValueError(
                f"Skin {skin_index} has {len(joints)} joints but "
                f"{len(raw_ibms)} inverse bind matrices."
            )
        inverse_bind_matrices = [
            gltf_matrix_to_internal(values) for values in raw_ibms
        ]

    result: List[Mat4] = []
    for joint_index, inverse_bind in zip(joints, inverse_bind_matrices):
        joint_world = world_matrices.get(joint_index)
        if joint_world is None:
            raise ValueError(
                f"Skin {skin_index} joint node {joint_index} is not in the scene."
            )
        result.append(matrix_multiply(joint_world, inverse_bind))
    return result


def _skinned_primitive_bounds(
    document: Dict[str, Any],
    reader: AccessorReader,
    primitive: Dict[str, Any],
    joint_matrices: Sequence[Mat4],
    pretransform: Mat4,
    vertex_limit: int,
) -> Optional[Bounds]:
    attributes = primitive.get("attributes", {})
    position_accessor = attributes.get("POSITION")
    joints0_accessor = attributes.get("JOINTS_0")
    weights0_accessor = attributes.get("WEIGHTS_0")
    if position_accessor is None:
        return None

    positions = reader.read(int(position_accessor))
    if not positions:
        return None

    # A malformed or unusual skin without explicit joint/weight attributes is
    # kept conservative: use authored local positions rather than inventing a
    # deformation. UBE's GLB exports normally provide both arrays.
    if joints0_accessor is None or weights0_accessor is None:
        points = [
            transform_point(pretransform, positions[index])
            for index in _sampled_vertex_indices(len(positions), vertex_limit)
        ]
        return (
            (
                min(point[0] for point in points),
                min(point[1] for point in points),
                min(point[2] for point in points),
            ),
            (
                max(point[0] for point in points),
                max(point[1] for point in points),
                max(point[2] for point in points),
            ),
        )

    joints0 = reader.read(int(joints0_accessor))
    weights0 = reader.read(int(weights0_accessor))
    joints1_accessor = attributes.get("JOINTS_1")
    weights1_accessor = attributes.get("WEIGHTS_1")
    joints1 = (
        reader.read(int(joints1_accessor))
        if joints1_accessor is not None
        else None
    )
    weights1 = (
        reader.read(int(weights1_accessor))
        if weights1_accessor is not None
        else None
    )

    count = len(positions)
    if len(joints0) != count or len(weights0) != count:
        raise ValueError("Skinned primitive POSITION/JOINTS_0/WEIGHTS_0 counts differ.")
    if (joints1 is None) != (weights1 is None):
        raise ValueError("Skinned primitive must provide JOINTS_1 and WEIGHTS_1 together.")
    if joints1 is not None and (
        len(joints1) != count or len(weights1) != count  # type: ignore[arg-type]
    ):
        raise ValueError("Skinned primitive secondary joint/weight counts differ.")

    minimum = [float("inf"), float("inf"), float("inf")]
    maximum = [float("-inf"), float("-inf"), float("-inf")]
    valid_points = 0

    for vertex_index in _sampled_vertex_indices(count, vertex_limit):
        position = positions[vertex_index]
        influence_pairs: List[Tuple[int, float]] = [
            (int(joint), float(weight))
            for joint, weight in zip(
                joints0[vertex_index],
                weights0[vertex_index],
            )
        ]
        if joints1 is not None and weights1 is not None:
            influence_pairs.extend(
                (int(joint), float(weight))
                for joint, weight in zip(
                    joints1[vertex_index],
                    weights1[vertex_index],
                )
            )

        total_weight = sum(
            weight for _joint, weight in influence_pairs if weight > 0.0
        )
        if total_weight <= 1e-20:
            skinned = (
                float(position[0]),
                float(position[1]),
                float(position[2]),
            )
        else:
            x = y = z = 0.0
            for joint_index, weight in influence_pairs:
                if weight <= 0.0:
                    continue
                if not 0 <= joint_index < len(joint_matrices):
                    raise ValueError(
                        f"Vertex {vertex_index} references skin joint "
                        f"{joint_index}, outside 0..{len(joint_matrices) - 1}."
                    )
                transformed = transform_point(
                    joint_matrices[joint_index],
                    position,
                )
                normalized_weight = weight / total_weight
                x += transformed[0] * normalized_weight
                y += transformed[1] * normalized_weight
                z += transformed[2] * normalized_weight
            skinned = (x, y, z)

        final_point = transform_point(pretransform, skinned)
        for axis in range(3):
            minimum[axis] = min(minimum[axis], final_point[axis])
            maximum[axis] = max(maximum[axis], final_point[axis])
        valid_points += 1

    if valid_points == 0:
        return None
    return (
        (minimum[0], minimum[1], minimum[2]),
        (maximum[0], maximum[1], maximum[2]),
    )


def _skinned_mesh_bounds(
    document: Dict[str, Any],
    reader: AccessorReader,
    mesh_index: int,
    skin_index: int,
    world_matrices: Dict[int, Mat4],
    pretransform: Mat4,
    vertex_limit: int,
    skin_matrix_cache: Dict[int, List[Mat4]],
) -> Optional[Bounds]:
    meshes = document.get("meshes", [])
    if not 0 <= mesh_index < len(meshes):
        raise ValueError(f"Invalid mesh index {mesh_index}.")

    joint_matrices = skin_matrix_cache.get(skin_index)
    if joint_matrices is None:
        joint_matrices = _skin_joint_matrices(
            document,
            reader,
            skin_index,
            world_matrices,
        )
        skin_matrix_cache[skin_index] = joint_matrices

    result: Optional[Bounds] = None
    for primitive in meshes[mesh_index].get("primitives", []):
        primitive_bounds = _skinned_primitive_bounds(
            document=document,
            reader=reader,
            primitive=primitive,
            joint_matrices=joint_matrices,
            pretransform=pretransform,
            vertex_limit=vertex_limit,
        )
        if primitive_bounds is not None:
            result = bounds_union(result, primitive_bounds)
    return result


def scene_bounds_at_pose(
    document: Dict[str, Any],
    reader: AccessorReader,
    mesh_bounds: Sequence[Optional[Bounds]],
    scene_index: int,
    overrides: Dict[int, Dict[str, Sequence[float]]],
    pretransform: Mat4,
    skin_vertex_limit: int = 0,
) -> Optional[Bounds]:
    nodes = document.get("nodes", [])
    world_matrices, traversal_order = _scene_world_matrices(
        document,
        scene_index,
        overrides,
    )
    result: Optional[Bounds] = None
    skin_matrix_cache: Dict[int, List[Mat4]] = {}

    for node_index in traversal_order:
        node = nodes[node_index]
        mesh_value = node.get("mesh")
        if mesh_value is None:
            continue
        mesh_index = int(mesh_value)

        if "skin" in node:
            node_bounds = _skinned_mesh_bounds(
                document=document,
                reader=reader,
                mesh_index=mesh_index,
                skin_index=int(node["skin"]),
                world_matrices=world_matrices,
                pretransform=pretransform,
                vertex_limit=skin_vertex_limit,
                skin_matrix_cache=skin_matrix_cache,
            )
        else:
            local_bounds = mesh_bounds[mesh_index]
            if local_bounds is None:
                node_bounds = None
            else:
                final_matrix = matrix_multiply(
                    pretransform,
                    world_matrices[node_index],
                )
                node_bounds = transformed_bounds(local_bounds, final_matrix)

        if node_bounds is not None:
            result = bounds_union(result, node_bounds)

    return result


def scene_bounds(
    document: Dict[str, Any],
    reader: AccessorReader,
    mesh_bounds: Sequence[Optional[Bounds]],
    scene_index: int,
    bounds_mode: str,
    animation_index: int,
    samples: int,
    pretransform: Mat4,
    max_skin_vertices: int,
) -> Bounds:
    animations = document.get("animations", [])
    combined: Optional[Bounds] = None

    # First/rest pose centring is exact. Full-animation mode may sample very
    # dense skins using the user-controlled cap to remain practical.
    vertex_limit = max_skin_vertices if bounds_mode == "animation" else 0

    if bounds_mode == "rest" or not animations:
        combined = scene_bounds_at_pose(
            document,
            reader,
            mesh_bounds,
            scene_index,
            {},
            pretransform,
            vertex_limit,
        )
    elif bounds_mode == "first":
        start, _ = animation_time_range(document, reader, animation_index)
        overrides = animation_overrides(
            document, reader, animation_index, start
        )
        combined = scene_bounds_at_pose(
            document,
            reader,
            mesh_bounds,
            scene_index,
            overrides,
            pretransform,
            vertex_limit,
        )
    elif bounds_mode == "animation":
        start, end = animation_time_range(document, reader, animation_index)
        sample_count = max(2, samples)
        if abs(end - start) <= 1e-20:
            sample_times = [start]
        else:
            sample_times = [
                start + (end - start) * index / (sample_count - 1)
                for index in range(sample_count)
            ]
        for time_value in sample_times:
            overrides = animation_overrides(
                document, reader, animation_index, time_value
            )
            pose_bounds = scene_bounds_at_pose(
                document,
                reader,
                mesh_bounds,
                scene_index,
                overrides,
                pretransform,
                vertex_limit,
            )
            if pose_bounds is not None:
                combined = bounds_union(combined, pose_bounds)
    else:
        raise ValueError(f"Unknown bounds mode: {bounds_mode}")

    if combined is None:
        raise ValueError(
            f"Scene {scene_index} contains no mesh POSITION bounds."
        )
    return combined


def unwrap_existing_tool_root(
    document: Dict[str, Any],
    scene: Dict[str, Any],
) -> Tuple[List[int], Optional[int]]:
    """Return the original scene roots and an existing tool wrapper, if present.

    v1.0 wrote the wrapper as the only scene root. v1.1 keeps skinned mesh nodes
    beside the wrapper, so the marker may now be one of several scene roots.
    """
    nodes = document.setdefault("nodes", [])
    roots = [int(index) for index in scene.get("nodes", [])]
    marked = [
        index
        for index in roots
        if nodes[index].get("extras", {}).get(TOOL_MARKER) is True
    ]
    if len(marked) > 1:
        raise ValueError("Scene contains more than one presentation-corrector root.")
    if not marked:
        return roots, None

    wrapper_index = marked[0]
    wrapper = nodes[wrapper_index]
    original_roots = [
        index for index in roots if index != wrapper_index
    ] + [int(index) for index in wrapper.get("children", [])]

    # Remove duplicates while preserving order.
    deduplicated: List[int] = []
    seen: set[int] = set()
    for index in original_roots:
        if index not in seen:
            seen.add(index)
            deduplicated.append(index)
    return deduplicated, wrapper_index


def _reachable_parent_map(
    document: Dict[str, Any],
    scene_roots: Sequence[int],
) -> Tuple[Dict[int, int], set[int]]:
    nodes = document.get("nodes", [])
    parent_map: Dict[int, int] = {}
    reachable: set[int] = set()
    visiting: set[int] = set()

    def visit(node_index: int) -> None:
        if node_index in visiting:
            raise ValueError(f"Cycle detected in node hierarchy at node {node_index}.")
        if node_index in reachable:
            return
        visiting.add(node_index)
        reachable.add(node_index)
        for child_value in nodes[node_index].get("children", []):
            child_index = int(child_value)
            if child_index in parent_map and parent_map[child_index] != node_index:
                raise ValueError(
                    f"Node {child_index} has multiple parents in the scene hierarchy."
                )
            parent_map[child_index] = node_index
            visit(child_index)
        visiting.remove(node_index)

    for root_index in scene_roots:
        visit(int(root_index))
    return parent_map, reachable


def _scene_root_ancestor(
    node_index: int,
    scene_root_set: set[int],
    parent_map: Dict[int, int],
) -> Optional[int]:
    current = int(node_index)
    visited: set[int] = set()
    while current not in scene_root_set:
        if current in visited:
            return None
        visited.add(current)
        parent = parent_map.get(current)
        if parent is None:
            return None
        current = parent
    return current


def prepare_original_scene_roots(
    document: Dict[str, Any],
) -> Dict[int, Tuple[List[int], List[int], List[int], Optional[int]]]:
    """Split each scene into fixed skinned roots and transformable roots.

    glTF requires the transform of a node containing a skinned mesh to be
    ignored. Such nodes therefore remain direct scene roots. Their separate
    rig/joint roots, plus all ordinary scene roots, are placed under the
    presentation wrapper.
    """
    result: Dict[
        int,
        Tuple[List[int], List[int], List[int], Optional[int]],
    ] = {}
    nodes = document.get("nodes", [])
    skins = document.get("skins", [])

    for scene_index, scene in enumerate(document.get("scenes", [])):
        roots, existing_root = unwrap_existing_tool_root(document, scene)
        if not roots:
            raise ValueError(f"Scene {scene_index} has no root nodes.")

        parent_map, reachable = _reachable_parent_map(document, roots)
        root_set = set(roots)

        all_skinned_nodes = [
            node_index
            for node_index in reachable
            if "skin" in nodes[node_index] and "mesh" in nodes[node_index]
        ]
        non_root_skinned = [
            node_index for node_index in all_skinned_nodes if node_index not in root_set
        ]
        if non_root_skinned:
            names = ", ".join(
                nodes[index].get("name", str(index))
                for index in non_root_skinned[:5]
            )
            raise ValueError(
                "Input already contains a skinned mesh below another node "
                f"({names}). A safe presentation correction cannot be added "
                "without rewriting the skin."
            )

        skinned_roots = [
            root_index
            for root_index in roots
            if "skin" in nodes[root_index] and "mesh" in nodes[root_index]
        ]
        movable_roots = [
            root_index for root_index in roots if root_index not in skinned_roots
        ]

        # Prove that every root-level skinned mesh has its joint hierarchy under
        # a movable scene root. Moving that root moves the skin; moving the mesh
        # node itself would have no effect under the glTF specification.
        for skinned_root in skinned_roots:
            skin_index = int(nodes[skinned_root]["skin"])
            if not 0 <= skin_index < len(skins):
                raise ValueError(
                    f"Skinned node {skinned_root} references invalid skin {skin_index}."
                )
            joint_roots: set[int] = set()
            for joint_value in skins[skin_index].get("joints", []):
                joint_root = _scene_root_ancestor(
                    int(joint_value), root_set, parent_map
                )
                if joint_root is not None:
                    joint_roots.add(joint_root)

            usable_joint_roots = [
                index for index in joint_roots if index in movable_roots
            ]
            if not usable_joint_roots:
                name = nodes[skinned_root].get("name", str(skinned_root))
                raise ValueError(
                    f"Skinned mesh '{name}' has no separate root-level joint "
                    "hierarchy that can receive the presentation transform."
                )

        scene["nodes"] = roots
        result[scene_index] = (
            roots,
            skinned_roots,
            movable_roots,
            existing_root,
        )
    return result


def apply_scene_wrappers(
    document: Dict[str, Any],
    original_roots: Dict[
        int,
        Tuple[List[int], List[int], List[int], Optional[int]],
    ],
    scene_transforms: Dict[int, Tuple[Vec3, Quat]],
    settings: Dict[str, Any],
) -> None:
    nodes = document.setdefault("nodes", [])

    for scene_index, scene in enumerate(document.get("scenes", [])):
        (
            _all_roots,
            skinned_roots,
            movable_roots,
            existing_root_index,
        ) = original_roots[scene_index]
        translation, rotation = scene_transforms[scene_index]

        wrapper_data = {
            "name": TOOL_ROOT_NAME,
            "children": movable_roots,
            "translation": list(translation),
            "rotation": list(rotation),
            "extras": {
                TOOL_MARKER: True,
                "settings": settings,
                "skinned_mesh_roots_preserved": len(skinned_roots),
            },
        }

        if existing_root_index is None:
            wrapper_index = len(nodes)
            nodes.append(wrapper_data)
        else:
            wrapper_index = existing_root_index
            nodes[wrapper_index] = wrapper_data

        # Skinned mesh nodes must remain direct scene roots. The wrapper moves
        # their joint hierarchy, which is what actually transforms a glTF skin.
        scene["nodes"] = skinned_roots + [wrapper_index]


def calculate_translation(
    bounds: Bounds,
    center_mode: str,
    ground: bool,
) -> Vec3:
    minimum, maximum = bounds
    center = (
        (minimum[0] + maximum[0]) * 0.5,
        (minimum[1] + maximum[1]) * 0.5,
        (minimum[2] + maximum[2]) * 0.5,
    )

    tx = 0.0
    ty = 0.0
    tz = 0.0

    if center_mode in {"xz", "xyz"}:
        tx = -center[0]
        tz = -center[2]
    if center_mode == "xyz":
        ty = -center[1]
    if ground:
        ty = -minimum[1]

    return (tx, ty, tz)


def output_path_for(
    source: Path,
    output: Optional[Path],
    output_dir: Optional[Path],
    suffix: str,
    overwrite: bool,
    multiple_inputs: bool,
) -> Path:
    if output is not None:
        if multiple_inputs:
            raise ValueError("--output can only be used with one input GLB.")
        destination = output
    elif output_dir is not None:
        destination = output_dir / f"{source.stem}{suffix}.glb"
    elif overwrite:
        destination = source
    else:
        destination = source.with_name(f"{source.stem}{suffix}.glb")

    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def collect_inputs(path: Path, recursive: bool) -> List[Path]:
    if path.is_file():
        if path.suffix.lower() != ".glb":
            raise ValueError(f"Input file is not a .glb: {path}")
        return [path]

    if not path.is_dir():
        raise ValueError(f"Input path does not exist: {path}")

    iterator = path.rglob("*.glb") if recursive else path.glob("*.glb")
    return sorted(item for item in iterator if item.is_file())


def process_file(
    source: Path,
    destination: Path,
    center_mode: str,
    ground: bool,
    rotate_y: float,
    bounds_mode: str,
    animation_index: int,
    samples: int,
    max_skin_vertices: int,
    dry_run: bool,
) -> None:
    loaded = load_glb(source)
    document = loaded.document

    scenes = document.get("scenes", [])
    if not scenes:
        raise ValueError("GLB contains no scenes.")

    original_roots = prepare_original_scene_roots(document)
    reader = AccessorReader(document, loaded.bin_data)
    mesh_bounds = build_mesh_bounds(document, reader)
    rotation_matrix = y_rotation_matrix(rotate_y)
    rotation_quaternion = y_rotation_quaternion(rotate_y)

    scene_transforms: Dict[int, Tuple[Vec3, Quat]] = {}
    print(f"\n{source}")
    print(f"  Bounds mode: {bounds_mode}")
    if document.get("animations") and bounds_mode != "rest":
        print(f"  Animation index: {animation_index}")

    for scene_index in range(len(scenes)):
        before_rotation = scene_bounds(
            document=document,
            reader=reader,
            mesh_bounds=mesh_bounds,
            scene_index=scene_index,
            bounds_mode=bounds_mode,
            animation_index=animation_index,
            samples=samples,
            pretransform=identity_matrix(),
            max_skin_vertices=max_skin_vertices,
        )
        rotated = scene_bounds(
            document=document,
            reader=reader,
            mesh_bounds=mesh_bounds,
            scene_index=scene_index,
            bounds_mode=bounds_mode,
            animation_index=animation_index,
            samples=samples,
            pretransform=rotation_matrix,
            max_skin_vertices=max_skin_vertices,
        )
        translation = calculate_translation(rotated, center_mode, ground)
        scene_transforms[scene_index] = (
            translation,
            rotation_quaternion,
        )

        print(f"  Scene {scene_index}:")
        print(
            f"    Original bounds: {format_vec3(before_rotation[0])} "
            f"to {format_vec3(before_rotation[1])}"
        )
        print(f"    Rotate Y: {rotate_y:g} degrees")
        print(f"    Translation: {format_vec3(translation)}")

    settings = {
        "center": center_mode,
        "ground": ground,
        "rotate_y_degrees": rotate_y,
        "bounds_mode": bounds_mode,
        "animation_index": animation_index,
        "samples": samples,
        "max_skin_vertices": max_skin_vertices,
        "tool_version": TOOL_VERSION,
    }
    apply_scene_wrappers(
        document,
        original_roots,
        scene_transforms,
        settings,
    )

    if dry_run:
        print("  Dry run: no file written.")
        return

    if source.resolve() == destination.resolve():
        temporary = destination.with_suffix(".glb.tmp")
        write_glb(temporary, loaded)
        os.replace(temporary, destination)
    else:
        write_glb(destination, loaded)
    print(f"  Written: {destination}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Re-centre and rotate GLB scenes by adding a parent presentation "
            "node while preserving original meshes and animation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input .glb file or folder containing .glb files.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="When input is a folder, include subfolders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Exact output path; valid only for one input file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Place processed files in this folder.",
    )
    parser.add_argument(
        "--suffix",
        default="_presented",
        help='Output filename suffix (default: "_presented").',
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the input GLB. Not recommended.",
    )
    parser.add_argument(
        "--center",
        choices=("xz", "xyz", "none"),
        default="xz",
        help=(
            "Centre horizontally (xz), centre all axes (xyz), or do not "
            "centre (none). Default: xz."
        ),
    )
    parser.add_argument(
        "--ground",
        dest="ground",
        action="store_true",
        default=True,
        help="Place the lowest bound on Y=0 (default).",
    )
    parser.add_argument(
        "--no-ground",
        dest="ground",
        action="store_false",
        help="Do not move the lowest bound to Y=0.",
    )
    parser.add_argument(
        "--rotate-y",
        type=float,
        default=0.0,
        help="Presentation rotation around the Y axis in degrees.",
    )
    parser.add_argument(
        "--bounds",
        choices=("rest", "first", "animation"),
        default="first",
        help=(
            "Bounds source: rest pose, first frame, or sampled complete "
            "animation travel. Default: first."
        ),
    )
    parser.add_argument(
        "--animation-index",
        type=int,
        default=0,
        help="Animation index used by first/animation bounds modes.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=120,
        help=(
            "Number of evenly spaced poses for --bounds animation "
            "(default: 120)."
        ),
    )
    parser.add_argument(
        "--max-skin-vertices",
        type=int,
        default=12000,
        help=(
            "Maximum vertices sampled per skinned primitive for "
            "--bounds animation (default: 12000). First/rest pose bounds "
            "always evaluate every vertex. Use 0 for all vertices."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate and report corrections without writing files.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"GLB Presentation Corrector {TOOL_VERSION}",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        sources = collect_inputs(args.input, args.recursive)
        if not sources:
            parser.error("No GLB files were found.")

        if args.output is not None and len(sources) != 1:
            parser.error("--output requires exactly one input GLB.")
        if args.overwrite and args.output is not None:
            parser.error("--overwrite and --output cannot be used together.")
        if args.overwrite and args.output_dir is not None:
            parser.error("--overwrite and --output-dir cannot be used together.")
        if args.samples < 2:
            parser.error("--samples must be at least 2.")
        if args.max_skin_vertices < 0:
            parser.error("--max-skin-vertices cannot be negative.")

        failures = 0
        for source in sources:
            try:
                destination = output_path_for(
                    source=source,
                    output=args.output,
                    output_dir=args.output_dir,
                    suffix=args.suffix,
                    overwrite=args.overwrite,
                    multiple_inputs=len(sources) > 1,
                )
                process_file(
                    source=source,
                    destination=destination,
                    center_mode=args.center,
                    ground=args.ground,
                    rotate_y=args.rotate_y,
                    bounds_mode=args.bounds,
                    animation_index=args.animation_index,
                    samples=args.samples,
                    max_skin_vertices=args.max_skin_vertices,
                    dry_run=args.dry_run,
                )
            except Exception as exc:
                failures += 1
                print(f"\nERROR processing {source}: {exc}", file=sys.stderr)

        if failures:
            print(
                f"\nCompleted with {failures} failed file(s) "
                f"out of {len(sources)}.",
                file=sys.stderr,
            )
            return 1

        print(f"\nDone. Processed {len(sources)} GLB file(s).")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
