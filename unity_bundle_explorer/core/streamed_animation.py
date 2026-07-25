from __future__ import annotations

"""Small, dependency-free decoder for Unity AnimationClip StreamedClip curves.

Unity stores some generic AnimationClip keyframes as a uint32 word stream rather
than exposing m_PositionCurves / m_RotationCurves / m_EulerCurves arrays.  This
module decodes the frame records and maps scalar curve indices back to generic
Transform bindings.

The public function deliberately returns the same track shape used by UBE's
ordinary curve reader: ``kind``, ``path``, ``keys`` and ``target_transform``.
"""

from dataclasses import dataclass
import math
import struct
from typing import Any, Callable, Iterable


_TRANSFORM_TYPE_ID = 4
_TRANSFORM_BINDINGS: dict[int, tuple[str, int]] = {
    1: ("position", 3),
    2: ("rotation", 4),
    3: ("scale", 3),
    4: ("euler", 3),
}


def _get(value: Any, *names: str, default: Any = None) -> Any:
    if value is None:
        return default
    for name in names:
        try:
            if isinstance(value, dict) and name in value:
                return value[name]
            if hasattr(value, name):
                return getattr(value, name)
        except Exception:
            continue
    return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    try:
        if hasattr(value, "tolist"):
            converted = value.tolist()
            return converted if isinstance(converted, list) else list(converted)
    except Exception:
        pass
    try:
        return list(value)
    except Exception:
        return [value]


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _binding_type_id(binding: Any) -> int:
    type_value = _get(binding, "typeID", "typeId", "m_TypeID", "classID", "m_ClassID", default=0)
    try:
        # UnityPy may expose the target type as an enum-like object.
        return int(getattr(type_value, "value", type_value) or 0)
    except Exception:
        return 0


def _words_to_bytes(raw_words: Any) -> bytes:
    """Convert UnityPy's uint32 array (or already-byte payload) to bytes."""
    if raw_words is None:
        return b""
    if isinstance(raw_words, (bytes, bytearray, memoryview)):
        return bytes(raw_words)

    words = _as_list(raw_words)
    if not words:
        return b""

    # Some readers expose a byte array.  A real streamed uint32 payload normally
    # contains values far above 255 (float bit patterns), so this is unambiguous
    # for practical AnimationClip data.
    try:
        integers = [int(value) for value in words]
    except Exception:
        return b""
    if integers and all(0 <= value <= 0xFF for value in integers):
        return bytes(integers)

    out = bytearray()
    for value in integers:
        out.extend(struct.pack("<I", value & 0xFFFFFFFF))
    return bytes(out)


@dataclass(frozen=True)
class StreamedKey:
    index: int
    value: float
    out_slope: float
    coeff: tuple[float, float, float, float]


@dataclass(frozen=True)
class StreamedFrame:
    time: float
    keys: tuple[StreamedKey, ...]


def decode_streamed_frames(
    raw_words: Any,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[list[StreamedFrame], str | None]:
    """Decode Unity's StreamedClip frame records.

    Record layout (little endian): float time, int key_count, followed by
    ``key_count`` entries of int curve_index + four float coefficients.  The
    sampled value is coefficient 3; coefficient 2 is the outgoing slope.
    """
    blob = _words_to_bytes(raw_words)
    if not blob:
        return [], "streamed clip contains no data words"

    frames: list[StreamedFrame] = []
    offset = 0
    max_frames = 200_000
    max_keys_per_frame = 1_000_000
    progress_bucket = -1
    try:
        while offset < len(blob):
            if progress_callback is not None and blob:
                bucket = min(10, int((offset * 10) / len(blob)))
                if bucket > progress_bucket:
                    progress_bucket = bucket
                    progress_callback(
                        f"Decoding streamed animation frame records: {bucket * 10}%…"
                    )
            remaining = len(blob) - offset
            if remaining < 8:
                # Padding is tolerated only when it is all zero.
                if any(blob[offset:]):
                    return [], f"truncated streamed frame header at byte {offset}"
                break
            frame_time, key_count = struct.unpack_from("<fi", blob, offset)
            offset += 8
            if key_count < 0 or key_count > max_keys_per_frame:
                return [], f"invalid streamed key count {key_count} at frame {len(frames)}"
            needed = key_count * 20
            if offset + needed > len(blob):
                return [], f"truncated streamed key data at frame {len(frames)}"

            keys: list[StreamedKey] = []
            for _ in range(key_count):
                index, c0, c1, c2, c3 = struct.unpack_from("<i4f", blob, offset)
                offset += 20
                if index < 0:
                    return [], f"invalid negative streamed curve index {index}"
                keys.append(
                    StreamedKey(
                        index=int(index),
                        value=float(c3),
                        out_slope=float(c2),
                        coeff=(float(c0), float(c1), float(c2), float(c3)),
                    )
                )
            frames.append(StreamedFrame(float(frame_time), tuple(keys)))
            if len(frames) > max_frames:
                return [], "streamed clip frame guard exceeded"
    except (struct.error, OverflowError, ValueError) as exc:
        return [], f"could not decode streamed frame data: {exc}"

    if not frames:
        return [], "streamed clip contained no frame records"
    return frames, None


def _binding_ranges(generic_bindings: Iterable[Any]) -> tuple[list[dict[str, Any]], int]:
    ranges: list[dict[str, Any]] = []
    cursor = 0
    for binding_index, binding in enumerate(generic_bindings):
        type_id = _binding_type_id(binding)
        attribute = _safe_int(_get(binding, "attribute", "m_Attribute", default=0), 0)
        if type_id == _TRANSFORM_TYPE_ID and attribute in _TRANSFORM_BINDINGS:
            kind, dimensions = _TRANSFORM_BINDINGS[attribute]
        else:
            # Non-Transform generic bindings consume one streamed scalar.  We
            # account for them so later Transform curve indices remain aligned,
            # but v2.2f does not attempt to preview those properties.
            kind, dimensions = None, 1
        path_hash = _safe_int(_get(binding, "path", "m_Path", default=0), 0) & 0xFFFFFFFF
        ranges.append(
            {
                "binding_index": binding_index,
                "start": cursor,
                "end": cursor + dimensions,
                "dimensions": dimensions,
                "kind": kind,
                "path_hash": path_hash,
                "attribute": attribute,
                "type_id": type_id,
            }
        )
        cursor += dimensions
    return ranges, cursor


def decode_streamed_transform_tracks(
    streamed_clip: Any,
    generic_bindings: Iterable[Any],
    resolve_path: Callable[[int], str | None],
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Decode streamed scalar channels into UBE Transform vector tracks."""
    raw_words = _get(streamed_clip, "data", "m_Data", default=None)
    declared_curve_count = _safe_int(
        _get(streamed_clip, "curveCount", "m_CurveCount", default=0),
        0,
    )
    frames, error = decode_streamed_frames(
        raw_words, progress_callback=progress_callback
    )
    meta: dict[str, Any] = {
        "error": error,
        "word_count": len(_as_list(raw_words)),
        "declared_curve_count": declared_curve_count,
        "decoded_frame_count": len(frames),
        "playable_frame_count": 0,
        "transform_track_count": 0,
        "unresolved_path_hashes": [],
    }
    if error or not frames:
        return [], meta

    bindings, flattened_count = _binding_ranges(generic_bindings)
    meta["flattened_binding_channel_count"] = flattened_count
    if not bindings:
        meta["error"] = "streamed clip has no generic bindings"
        return [], meta

    # Unity's StreamedClip contains a synthetic leading frame used for slope
    # reconstruction and a terminal frame (normally +infinity).  Exclude both,
    # matching Unity asset readers.  Very small malformed clips fall back to all
    # finite frames so the decoder fails gently instead of crashing.
    if len(frames) >= 3:
        playable = frames[1:-1]
    else:
        playable = [frame for frame in frames if math.isfinite(frame.time)]
    playable = [frame for frame in playable if math.isfinite(frame.time)]
    meta["playable_frame_count"] = len(playable)
    if not playable:
        meta["error"] = "streamed clip has no playable finite frames"
        return [], meta

    # Seed component state from the synthetic leading frame.  Later frames may
    # contain only changed scalar channels, so carried values are needed to
    # rebuild complete Vector3 / Quaternion samples.
    scalar_state: dict[int, float] = {}
    for key in frames[0].keys:
        scalar_state[key.index] = key.value

    keys_by_binding: dict[int, list[tuple[float, tuple[float, ...]]]] = {}
    binding_for_scalar: dict[int, int] = {}
    for entry_index, entry in enumerate(bindings):
        for scalar_index in range(int(entry["start"]), int(entry["end"])):
            binding_for_scalar[scalar_index] = entry_index

    playable_count = len(playable)
    progress_step = max(1, playable_count // 10) if playable_count else 1
    for frame_index, frame in enumerate(playable):
        if progress_callback is not None and (
            frame_index == 0
            or (frame_index + 1) % progress_step == 0
            or frame_index + 1 == playable_count
        ):
            progress_callback(
                f"Reconstructing streamed Transform channels: "
                f"{frame_index + 1:,}/{playable_count:,} frame record(s)…"
            )
        touched: set[int] = set()
        for key in frame.keys:
            scalar_state[key.index] = key.value
            entry_index = binding_for_scalar.get(key.index)
            if entry_index is not None:
                touched.add(entry_index)
        for entry_index in sorted(touched):
            entry = bindings[entry_index]
            if entry["kind"] is None:
                continue
            values: list[float] = []
            complete = True
            for scalar_index in range(int(entry["start"]), int(entry["end"])):
                if scalar_index not in scalar_state:
                    complete = False
                    break
                values.append(float(scalar_state[scalar_index]))
            if not complete:
                continue
            out = keys_by_binding.setdefault(entry_index, [])
            sample = (float(frame.time), tuple(values))
            if out and abs(out[-1][0] - sample[0]) <= 1.0e-7:
                out[-1] = sample
            else:
                out.append(sample)

    tracks: list[dict[str, Any]] = []
    unresolved_hashes: list[int] = []
    for entry_index, entry in enumerate(bindings):
        if entry["kind"] is None:
            continue
        keys = keys_by_binding.get(entry_index, [])
        if not keys:
            continue
        path_hash = int(entry["path_hash"])
        path = resolve_path(path_hash)
        if not path:
            unresolved_hashes.append(path_hash)
            continue
        tracks.append(
            {
                "kind": str(entry["kind"]),
                "path": str(path).strip("/"),
                "path_hash": path_hash,
                "keys": keys,
                "target_transform": None,
                "storage": "streamed",
                "binding_index": int(entry["binding_index"]),
                "attribute": int(entry["attribute"]),
            }
        )

    meta["transform_track_count"] = len(tracks)
    meta["unresolved_path_hashes"] = unresolved_hashes
    if declared_curve_count and flattened_count and declared_curve_count != flattened_count:
        meta["curve_count_note"] = (
            f"declared {declared_curve_count} streamed curves; generic bindings flatten to {flattened_count} channels"
        )
    return tracks, meta
