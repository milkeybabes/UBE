from __future__ import annotations

from typing import Any
import math


def _get(obj: Any, *names: str, default=None):
    if obj is None:
        return default
    for name in names:
        try:
            if isinstance(obj, dict) and name in obj:
                return obj[name]
            if hasattr(obj, name):
                return getattr(obj, name)
        except Exception:
            pass
    return default


def _as_list(value: Any) -> list:
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


def _matrix4(value: Any) -> list[list[float]] | None:
    if value is None:
        return None
    # Unity Matrix4x4 typetrees commonly expose e00..e33.
    rows = []
    try:
        for r in range(4):
            row = []
            for c in range(4):
                item = _get(value, f"e{r}{c}", f"m{r}{c}", default=None)
                if item is None:
                    raise ValueError
                row.append(float(item))
            rows.append(row)
        return rows
    except Exception:
        pass
    # Some decoders expose a flat or nested sequence.
    seq = _as_list(value)
    try:
        if len(seq) == 16:
            return [[float(seq[r * 4 + c]) for c in range(4)] for r in range(4)]
        if len(seq) == 4 and all(len(_as_list(row)) >= 4 for row in seq):
            return [[float(_as_list(seq[r])[c]) for c in range(4)] for r in range(4)]
    except Exception:
        pass
    return None


def extract_bind_poses(mesh_data: Any) -> list[list[list[float]]]:
    values = _as_list(_get(mesh_data, "m_BindPose", "bindPose", "bind_poses", "m_BindPoses", default=None))
    out = []
    for value in values:
        matrix = _matrix4(value)
        if matrix is not None:
            out.append(matrix)
    return out


def _weight_row(value: Any) -> tuple[tuple[int, float], ...]:
    pairs = []
    for i in range(4):
        weight = _get(value, f"weight{i}", f"m_Weight{i}", default=0.0)
        index = _get(value, f"boneIndex{i}", f"m_BoneIndex{i}", default=0)
        try:
            weight_f = float(weight)
            index_i = int(index)
        except Exception:
            continue
        if math.isfinite(weight_f) and weight_f > 1e-8 and index_i >= 0:
            pairs.append((index_i, weight_f))
    total = sum(weight for _index, weight in pairs)
    if total > 1e-8:
        pairs = [(index, weight / total) for index, weight in pairs]
    return tuple(pairs)


def _weights_from_explicit(mesh_data: Any) -> list[tuple[tuple[int, float], ...]]:
    values = _as_list(_get(
        mesh_data,
        "m_Skin",          # Unity's long-standing serialized BoneWeight array
        "m_BoneWeights",   # exposed by some typetrees/tools
        "boneWeights",
        "bone_weights",
        default=None,
    ))
    return [_weight_row(value) for value in values] if values else []


def _weights_from_vertex_channels(mesh_data: Any, raw_override: bytes | None = None) -> list[tuple[tuple[int, float], ...]]:
    """Decode modern Unity BlendWeight/BlendIndices channels (normally 12/13)."""
    try:
        from ..exporters import mesh_exporter as me
        vdata = me._get(mesh_data, "m_VertexData", "vertex_data", default=None)
        if vdata is None:
            return []
        raw = raw_override or me._vertex_raw_bytes_from_vdata(vdata)
        if not raw:
            return []
        channels = me._as_list(me._get(vdata, "m_Channels", "channels", default=None))
        if len(channels) <= 13:
            return []
        weight_ch, index_ch = channels[12], channels[13]
        weight_dim = int(me._get(weight_ch, "dimension", "m_Dimension", default=0) or 0)
        index_dim = int(me._get(index_ch, "dimension", "m_Dimension", default=0) or 0)
        if index_dim <= 0:
            return []

        # Unity can optimise a mesh whose vertices are each controlled by one
        # bone into an index-only skin stream.  Such meshes have one
        # BlendIndices component per vertex and deliberately omit the
        # BlendWeight channel: the missing weight is implicitly 1.0.  Small
        # independently moving parts such as paired eyes commonly use this
        # representation.  Requiring channel 12 made these valid renderers look
        # static even though their eye/bone Transform curves decoded correctly.
        rigid_index_only = weight_dim <= 0 and index_dim == 1
        if weight_dim <= 0 and not rigid_index_only:
            return []

        count = int(me._get(vdata, "m_VertexCount", "vertex_count", default=0) or 0)
        if count <= 0:
            return []
        streams = me._as_list(me._get(vdata, "m_Streams", "streams", default=None))
        planar = me._infer_planar_stream_layout_when_streams_missing(vdata, channels, raw, count)

        def decode_scalar(offset: int, fmt: Any, comp_size: int, *, preserve_integer: bool):
            # mesh_exporter._read_vertex_component intentionally normalises several
            # integer formats for UV inspection. Bone *indices* must remain exact,
            # so decode them here using Unity's VertexAttributeFormat mapping.
            import struct
            try:
                f = int(fmt)
            except Exception:
                f = -1
            try:
                if f == 0 or (f < 0 and comp_size == 4):       # Float32
                    return float(struct.unpack_from("<f", raw, offset)[0])
                if f == 1 or (f < 0 and comp_size == 2):       # Float16
                    return float(struct.unpack_from("<e", raw, offset)[0])
                if comp_size == 1:
                    signed = f in (3, 7)
                    value = struct.unpack_from("<b" if signed else "<B", raw, offset)[0]
                    if preserve_integer:
                        return int(value)
                    if f == 3:
                        return max(-1.0, float(value) / 127.0)
                    if f == 2:
                        return float(value) / 255.0
                    return float(value)
                if comp_size == 2:
                    signed = f in (5, 9)
                    value = struct.unpack_from("<h" if signed else "<H", raw, offset)[0]
                    if preserve_integer:
                        return int(value)
                    if f == 5:
                        return max(-1.0, float(value) / 32767.0)
                    if f == 4:
                        return float(value) / 65535.0
                    return float(value)
                if comp_size == 4:
                    signed = f == 11
                    value = struct.unpack_from("<i" if signed else "<I", raw, offset)[0]
                    return int(value) if preserve_integer else float(value)
            except Exception:
                return None
            return None

        def decode(ch, vertex_index: int, *, preserve_integer: bool):
            stream_index = int(me._get(ch, "stream", "m_Stream", default=0) or 0)
            offset = int(me._get(ch, "offset", "m_Offset", default=0) or 0)
            fmt = me._get(ch, "format", "m_Format", default=0)
            dim = min(4, int(me._get(ch, "dimension", "m_Dimension", default=0) or 0))
            stream = streams[stream_index] if 0 <= stream_index < len(streams) else None
            if stream is None and stream_index in planar:
                stream_offset, stride = planar[stream_index]
            else:
                stream_offset = int(me._get(stream, "offset", "m_Offset", default=0) or 0) if stream is not None else 0
                stride = me._vertex_stream_stride(stream, channels, stream_index)
                if not stride:
                    stride = len(raw) // count
            comp_size = me._infer_component_size_for_channel(ch, channels, stream_index, stride) or me._component_size_for_vertex_format(fmt)
            if not comp_size:
                return []
            base = stream_offset + vertex_index * stride + offset
            return [
                decode_scalar(base + i * comp_size, fmt, comp_size, preserve_integer=preserve_integer)
                for i in range(dim)
            ]

        out = []
        bind_pose_count = len(extract_bind_poses(mesh_data))
        if rigid_index_only and bind_pose_count <= 0:
            return []
        for vertex_index in range(count):
            indices = decode(index_ch, vertex_index, preserve_integer=True)

            if rigid_index_only:
                try:
                    bi = int(round(float(indices[0])))
                except Exception:
                    return []
                # The bind-pose table is strong structural evidence that this
                # really is a skin index stream rather than an unrelated compact
                # vertex attribute.  Reject the inference rather than creating
                # an unsafe out-of-range influence.
                if bi < 0 or (bind_pose_count > 0 and bi >= bind_pose_count):
                    return []
                out.append(((bi, 1.0),))
                continue

            weights = decode(weight_ch, vertex_index, preserve_integer=False)
            pairs = []
            for i in range(min(len(weights), len(indices), 4)):
                try:
                    w = float(weights[i])
                    bi = int(round(float(indices[i])))
                except Exception:
                    continue
                if math.isfinite(w) and w > 1e-8 and bi >= 0:
                    pairs.append((bi, w))
            total = sum(w for _bi, w in pairs)
            out.append(tuple((bi, w / total) for bi, w in pairs) if total > 1e-8 else ())
        return out
    except Exception:
        return []


def extract_bone_weights(mesh_data: Any, raw_override: bytes | None = None) -> list[tuple[tuple[int, float], ...]]:
    explicit = _weights_from_explicit(mesh_data)
    if explicit:
        return explicit
    return _weights_from_vertex_channels(mesh_data, raw_override=raw_override)


def apply_matrix_point(matrix: list[list[float]], point: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = point
    return (
        matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3],
        matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3],
        matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3],
    )


def skin_vertices_obj_basis(
    source_obj_vertices: list[tuple[float, float, float]],
    weights: list[tuple[tuple[int, float], ...]],
    skin_matrices: list[list[list[float]]],
) -> list[tuple[float, float, float]]:
    """CPU linear-blend skinning. Input/output vertices use UnityPy OBJ (-X,Y,Z)."""
    out = []
    for i, obj_vertex in enumerate(source_obj_vertices):
        unity_vertex = (-float(obj_vertex[0]), float(obj_vertex[1]), float(obj_vertex[2]))
        influences = weights[i] if i < len(weights) else ()
        if not influences:
            out.append(obj_vertex)
            continue
        sx = sy = sz = total = 0.0
        for bone_index, weight in influences:
            if not (0 <= bone_index < len(skin_matrices)):
                continue
            px, py, pz = apply_matrix_point(skin_matrices[bone_index], unity_vertex)
            sx += px * weight
            sy += py * weight
            sz += pz * weight
            total += weight
        if total <= 1e-8:
            out.append(obj_vertex)
        else:
            out.append((-sx / total, sy / total, sz / total))
    return out


def pack_bone_weights(weights):
    """Return compact NumPy index/weight arrays when NumPy is available."""
    try:
        import numpy as np
        count = len(weights)
        indices = np.zeros((count, 4), dtype=np.int32)
        values = np.zeros((count, 4), dtype=np.float32)
        for row_index, row in enumerate(weights):
            for slot, (bone_index, weight) in enumerate(row[:4]):
                indices[row_index, slot] = int(bone_index)
                values[row_index, slot] = float(weight)
        return indices, values
    except Exception:
        return None


def skin_vertices_obj_basis_packed(source_obj_vertices, packed_weights, skin_matrices):
    """Vectorised CPU skinning used by the live viewer when NumPy is present."""
    if packed_weights is None:
        return skin_vertices_obj_basis(source_obj_vertices, [], skin_matrices)
    try:
        import numpy as np
        vertices = np.asarray(source_obj_vertices, dtype=np.float64)
        indices, weights = packed_weights
        if len(vertices) != len(indices):
            return list(source_obj_vertices)
        mats = np.asarray(skin_matrices, dtype=np.float64)
        if mats.ndim != 3 or mats.shape[1:] != (4, 4) or len(mats) == 0:
            return list(source_obj_vertices)
        unity = vertices.copy()
        unity[:, 0] *= -1.0
        homogeneous = np.concatenate((unity, np.ones((len(unity), 1), dtype=np.float64)), axis=1)
        result = np.zeros((len(unity), 3), dtype=np.float64)
        total = np.zeros((len(unity),), dtype=np.float64)
        for slot in range(4):
            slot_weights = weights[:, slot].astype(np.float64, copy=False)
            valid = (slot_weights > 1e-8) & (indices[:, slot] >= 0) & (indices[:, slot] < len(mats))
            if not np.any(valid):
                continue
            selected = mats[indices[valid, slot]]
            transformed = np.einsum("nij,nj->ni", selected, homogeneous[valid])[:, :3]
            result[valid] += transformed * slot_weights[valid, None]
            total[valid] += slot_weights[valid]
        valid_total = total > 1e-8
        result[valid_total] /= total[valid_total, None]
        result[~valid_total] = unity[~valid_total]
        result[:, 0] *= -1.0
        return [tuple(float(v) for v in row) for row in result]
    except Exception:
        return list(source_obj_vertices)
