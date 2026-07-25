from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any
import zlib


@dataclass(slots=True)
class TextureDetails:
    name: str = ""
    width: int | None = None
    height: int | None = None
    texture_format: str = ""
    texture_format_raw: str = ""
    mip_count: int | None = None
    complete_image_size: int | None = None
    stream_offset: int | None = None
    stream_size: int | None = None
    stream_path: str = ""


@dataclass(slots=True)
class TextureArrayDetails:
    name: str = ""
    width: int | None = None
    height: int | None = None
    depth: int | None = None
    texture_format: str = ""
    texture_format_raw: str = ""
    mip_count: int | None = None
    complete_image_size: int | None = None
    image_data_size: int | None = None
    stream_offset: int | None = None
    stream_size: int | None = None
    stream_path: str = ""




@dataclass(slots=True)
class CubemapDetails:
    name: str = ""
    width: int | None = None
    height: int | None = None
    texture_format: str = ""
    texture_format_raw: str = ""
    mip_count: int | None = None
    face_count: int | None = None
    image_count: int | None = None
    complete_image_size: int | None = None
    stream_offset: int | None = None
    stream_size: int | None = None
    stream_path: str = ""
    filter_mode: Any = None
    aniso_level: Any = None
    wrap_mode: Any = None


@dataclass(slots=True)
class AudioDetails:
    name: str = ""
    length: float | None = None
    channels: int | None = None
    frequency: int | None = None
    bits_per_sample: int | None = None
    load_type: Any = None
    compression_format: str = ""
    audio_data_size: int | None = None
    resource_offset: int | None = None
    resource_size: int | None = None
    resource_source: str = ""


# Unity TextureFormat enum values most commonly seen in Android/PC bundles.
# Unknown values remain visible as the raw number so we never hide useful data.
TEXTURE_FORMAT_NAMES: dict[int, str] = {
    1: "Alpha8",
    2: "ARGB4444",
    3: "RGB24",
    4: "RGBA32",
    5: "ARGB32",
    7: "RGB565",
    9: "R16",
    10: "DXT1 / BC1",
    12: "DXT5 / BC3",
    13: "RGBA4444",
    14: "BGRA32",
    15: "RHalf",
    16: "RGHalf",
    17: "RGBAHalf",
    18: "RFloat",
    19: "RGFloat",
    20: "RGBAFloat",
    21: "YUY2",
    22: "RGB9e5Float",
    24: "BC6H",
    25: "BC7",
    26: "BC4",
    27: "BC5",
    28: "DXT1 Crunched",
    29: "DXT5 Crunched",
    30: "PVRTC RGB2",
    31: "PVRTC RGBA2",
    32: "PVRTC RGB4",
    33: "PVRTC RGBA4",
    34: "ETC RGB4",
    41: "ETC2 RGB",
    42: "ETC2 RGBA1",
    43: "ETC2 RGBA8",
    44: "EAC R",
    45: "EAC R Signed",
    46: "EAC RG",
    47: "EAC RG Signed",
    48: "ASTC RGB 4x4",
    49: "ASTC RGB 5x5",
    50: "ASTC RGB 6x6",
    51: "ASTC RGB 8x8",
    52: "ASTC RGB 10x10",
    53: "ASTC RGB 12x12",
    54: "ASTC RGBA 4x4",
    55: "ASTC RGBA 5x5",
    56: "ASTC RGBA 6x6",
    57: "ASTC RGBA 8x8",
    58: "ASTC RGBA 10x10",
    59: "ASTC RGBA 12x12",
    60: "ETC RGB4 3DS",
    61: "ETC RGBA8 3DS",
    62: "RG16",
    63: "R8",
    64: "ETC RGB4 Crunched",
    65: "ETC2 RGBA8 Crunched",
    66: "ASTC HDR 4x4",
    67: "ASTC HDR 5x5",
    68: "ASTC HDR 6x6",
    69: "ASTC HDR 8x8",
    70: "ASTC HDR 10x10",
    71: "ASTC HDR 12x12",
    72: "RG32",
    73: "RGB48",
    74: "RGBA64",
}


TREE_ICONS: dict[str, str] = {
    "AssetBundle": "📦",
    "Bundle": "📦",
    "Texture2D": "🖼",
    "Texture2DArray": "🧱",
    "Cubemap": "🌌",
    "Material": "🎨",
    "Mesh": "🧊",
    "MeshFilter": "🧊",
    "MeshRenderer": "🧊",
    "SkinnedMeshRenderer": "🧍",
    "Sprite": "🖼",
    "SpriteRenderer": "🖼",
    "SpriteMask": "🎭",
    "LineRenderer": "〰",
    "TrailRenderer": "〰",
    "Rigidbody": "🧲",
    "SphereCollider": "◯",
    "CapsuleCollider": "⬭",
    "MeshCollider": "▧",
    "PhysicMaterial": "🧲",
    "TextAsset": "🔤",
    "Font": "🔠",
    "TMP_FontAsset": "🔠",
    "PlayableDirector": "🎬",
    "NavMeshData": "🧭",
    "NavMeshSettings": "🧭",
    "NavMeshProjectSettings": "🧭",
    "AudioClip": "🔊",
    "AudioSource": "🎧",
    "AudioMixerController": "🎚",
    "AudioMixerGroupController": "🎛",
    "AudioMixerSnapshotController": "📸",
    "AudioMixerEffectController": "✨",
    "Animation": "🎬",
    "AnimationClip": "🎬",
    "Animator": "🎬",
    "AnimatorController": "🎛",
    "AnimatorOverrideController": "🎛",
    "Shader": "⚙",
    "GameObject": "🎲",
    "Transform": "↔",
    "Camera": "📷",
    "BoxCollider": "▭",
    "Collider": "▭",
    "Canvas": "🖼",
    "CanvasGroup": "🖼",
    "CanvasRenderer": "🖼",
    "RectTransform": "▭",
    "Light": "💡",
    "ReflectionProbe": "🪞",
    "LODGroup": "📉",
    "LightProbeGroup": "💡",
    "LightingSettings": "🌗",
    "LightmapSettings": "🌗",
    "ParticleSystem": "✨",
    "ParticleSystemRenderer": "✨",
    "MonoBehaviour": "🧩",
    "Folder": "📁",
    "Project": "📁",
    "Course": "⛳",
    "OBB": "📦",
}


FRIENDLY_TYPE_NAMES: dict[str, str] = {
    "AssetBundle": "Bundle",
    "Bundle": "Bundle",
    "Texture2D": "Texture",
    "Texture2DArray": "Texture Array",
    "Cubemap": "Cubemap",
    "Material": "Material",
    "Mesh": "Mesh",
    "MeshFilter": "Mesh Link",
    "MeshRenderer": "Renderer",
    "SkinnedMeshRenderer": "Skinned Renderer",
    "Sprite": "Sprite",
    "SpriteRenderer": "Sprite Renderer",
    "SpriteMask": "Sprite Mask",
    "LineRenderer": "Line Renderer",
    "TrailRenderer": "Trail Renderer",
    "Rigidbody": "Rigidbody",
    "SphereCollider": "Sphere Collider",
    "CapsuleCollider": "Capsule Collider",
    "MeshCollider": "Mesh Collider",
    "PhysicMaterial": "Physics Material",
    "TextAsset": "Text Asset",
    "Font": "Font",
    "TMP_FontAsset": "TextMeshPro Font",
    "PlayableDirector": "Playable Director",
    "NavMeshData": "NavMesh Data",
    "NavMeshSettings": "NavMesh Settings",
    "NavMeshProjectSettings": "NavMesh Project Settings",
    "AudioClip": "Audio",
    "AudioSource": "Audio Source",
    "AudioMixerController": "Audio Mixer",
    "AudioMixerGroupController": "Audio Mixer Group",
    "AudioMixerSnapshotController": "Audio Mixer Snapshot",
    "AudioMixerEffectController": "Audio Mixer Effect",
    "Animation": "Animation",
    "AnimationClip": "Animation Clip",
    "Animator": "Animator",
    "Avatar": "Avatar",
    "AnimatorController": "Animator Controller",
    "AnimatorOverrideController": "Animator Override Controller",
    "Shader": "Shader",
    "GameObject": "Object",
    "Transform": "Transform",
    "Camera": "Camera",
    "BoxCollider": "Box Collider",
    "Collider": "Collider",
    "Canvas": "Canvas",
    "CanvasGroup": "Canvas Group",
    "CanvasRenderer": "Canvas Renderer",
    "RectTransform": "Rect Transform",
    "Light": "Light",
    "ReflectionProbe": "Reflection Probe",
    "LODGroup": "LOD Group",
    "LightProbeGroup": "Light Probe Group",
    "LightingSettings": "Lighting Settings",
    "LightmapSettings": "Lightmap Settings",
    "ParticleSystem": "Particle System",
    "ParticleSystemRenderer": "Particle System Renderer",
    "MonoBehaviour": "Script",
    "Folder": "Folder",
    "Project": "Project",
    "Course": "Course",
    "OBB": "Android OBB",
}

PROPERTY_ICONS: dict[str, str] = {
    "name": "🏷",
    "type": "🧩",
    "path": "#",
    "texture": "🖼",
    "material": "🎨",
    "mesh": "🧊",
    "shader": "⚙",
    "size": "💾",
    "resolution": "↔",
    "mip": "📚",
    "stream": "📦",
    "link": "🔗",
    "warning": "⚠",
    "info": "ℹ",
    "colour": "🎨",
    "float": "🔢",
    "vertex": "🔺",
}

def _get_material_base_color(data):
    props = _get(data, "m_SavedProperties", "saved_properties", default=None)
    if not props:
        return None

    colors = _as_list(_get(props, "m_Colors", "colors", default=None))

    for item in colors:

        key, value = _pair_key_value(item)

        if not key:
            continue

        key = str(key)

        if key in ("_Color", "_BaseColor"):
            r = _get(value, "r", default=None)
            g = _get(value, "g", default=None)
            b = _get(value, "b", default=None)

            if r is None or g is None or b is None:
                continue

            return (float(r), float(g), float(b))

    return None

def friendly_type_name(type_name: str) -> str:
    return FRIENDLY_TYPE_NAMES.get(type_name, type_name)


def visual_label(key: str, label: str) -> str:
    icon = PROPERTY_ICONS.get(key, "")
    return f"{icon} {label}" if icon else label


def icon_for_type(type_name: str) -> str:
    return TREE_ICONS.get(type_name, "")


def display_name_with_icon(name: str, type_name: str) -> str:
    icon = icon_for_type(type_name)
    return f"{icon} {name}" if icon else name


def human_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    n = float(value)
    for unit in ("bytes", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            if unit == "bytes":
                return f"{int(n):,} {unit}"
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{value:,} bytes"


def texture_format_name(value: Any) -> str:
    raw = str(value) if value is not None else ""
    if not raw:
        return "-"
    # UnityPy may expose enum objects as strings like "TextureFormat.ASTC_RGB_6x6".
    if not raw.lstrip("-").isdigit():
        return raw.replace("TextureFormat.", "")
    code = int(raw)
    friendly = TEXTURE_FORMAT_NAMES.get(code)
    return f"{friendly} ({code})" if friendly else f"Unknown ({code})"


def decoded_rgba_size(width: int | None, height: int | None) -> int | None:
    if not width or not height:
        return None
    return int(width) * int(height) * 4


def compression_ratio(decoded: int | None, compressed: int | None) -> str:
    if not decoded or not compressed:
        return "-"
    if compressed == 0:
        return "-"
    return f"{decoded / compressed:.2f}:1"


def is_likely_data_texture(texture_format: str, name: str = "") -> bool:
    fmt = (texture_format or "").lower()
    lname = (name or "").lower()
    data_formats = ("half", "float", "r16", "rg16", "rg32", "rgba64")
    data_names = ("postex", "pos_tex", "position", "lookup", "lut", "data", "offset", "voronoi")
    return any(x in fmt for x in data_formats) or any(x in lname for x in data_names)


def preview_unavailable_message(texture_format: str = "", name: str = "") -> str:
    if is_likely_data_texture(texture_format, name):
        return (
            "Preview unavailable\n\n"
            f"{name or 'This texture'} appears to be a GPU/data texture rather than normal artwork.\n"
            f"Format: {texture_format or '-'}\n\n"
            "These are often used for baked animation positions, lookup tables, masks, "
            "simulation data or other shader/GPU data. Metadata is still available."
        )
    return (
        "Texture preview unavailable.\n\n"
        "This texture may use a format not supported by the current decoder, "
        "or the external .resS data may not be available. Metadata is still available."
    )


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            try:
                return getattr(obj, name)
            except Exception:
                pass
    return default


def _vec2_tuple(value: Any, default: tuple[float, float] | None = None) -> tuple[float, float] | None:
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



def _get_any(obj: Any, *names: str, default: Any = None) -> Any:
    """Like _get, but also handles dict-style UnityPy/raw containers."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
    return _get(obj, *names, default=default)


def _num_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _vec3_tuple(value: Any, default: tuple[float, float, float] | None = None) -> tuple[float, float, float] | None:
    if value is None:
        return default
    if all(hasattr(value, c) for c in ("x", "y", "z")):
        try:
            return (float(value.x), float(value.y), float(value.z))
        except Exception:
            return default
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        try:
            return (float(value[0]), float(value[1]), float(value[2]))
        except Exception:
            return default
    return default


def _vec4_tuple(value: Any, default: tuple[float, float, float, float] | None = None) -> tuple[float, float, float, float] | None:
    if value is None:
        return default
    if all(hasattr(value, c) for c in ("x", "y", "z", "w")):
        try:
            return (float(value.x), float(value.y), float(value.z), float(value.w))
        except Exception:
            return default
    if all(hasattr(value, c) for c in ("r", "g", "b", "a")):
        try:
            return (float(value.r), float(value.g), float(value.b), float(value.a))
        except Exception:
            return default
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        try:
            return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
        except Exception:
            return default
    return default


def _rect_tuple(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    # Unity Rect normally has x, y, width, height.
    if all(hasattr(value, c) for c in ("x", "y", "width", "height")):
        try:
            return (float(value.x), float(value.y), float(value.width), float(value.height))
        except Exception:
            return None
    # Some serialized shapes expose x/y/z/w instead.
    v4 = _vec4_tuple(value, None)
    if v4 is not None:
        return v4
    return None


def _fmt_float(value: Any, digits: int = 3) -> str:
    try:
        f = float(value)
    except Exception:
        return "-"
    if abs(f - round(f)) < 0.000001:
        return str(int(round(f)))
    return f"{f:.{digits}f}"


def _fmt_vec2(value: Any) -> str:
    v = _vec2_tuple(value, None)
    return f"{_fmt_float(v[0])}, {_fmt_float(v[1])}" if v else "-"


def _fmt_vec3(value: Any) -> str:
    v = _vec3_tuple(value, None)
    return f"{_fmt_float(v[0])}, {_fmt_float(v[1])}, {_fmt_float(v[2])}" if v else "-"


def _fmt_vec4(value: Any) -> str:
    v = _vec4_tuple(value, None)
    return f"{_fmt_float(v[0])}, {_fmt_float(v[1])}, {_fmt_float(v[2])}, {_fmt_float(v[3])}" if v else "-"


def _colour_line(value: Any) -> str:
    rgba = _vec4_tuple(value, None)
    hx = _colour_hex(value)
    if rgba is None:
        return str(value)
    text = f"{rgba[0]:.3f}, {rgba[1]:.3f}, {rgba[2]:.3f}, {rgba[3]:.3f}"
    return f"{text} {hx}" if hx else text


def _list_len(value: Any) -> int | None:
    try:
        return len(value)
    except Exception:
        return None


def _resolve_pptr_name_type(pptr: Any, bundle_index: Any | None) -> tuple[str, str, int | None]:
    rec = _resolve_record(bundle_index, pptr)
    if rec is not None:
        return rec.name, rec.type_name, rec.path_id
    pid = _pptr_path_id(pptr)
    return (f"PathID {pid}" if pid not in (None, 0) else "-", "", pid)

def _record_source_name(record: Any) -> str:
    try:
        return str(getattr(record, "source_name", "") or "")
    except Exception:
        return ""


def _pptr_target_source_path_id(pptr: Any) -> tuple[str, int] | None:
    """Resolve a UnityPy PPtr to its real target SerializedFile + PathID.

    In UnityFS files, PathID 2 can exist in sharedassets0.assets and also in
    resources.assets.  PPtr.m_FileID tells UnityPy which external SerializedFile
    to use, but pptr.assetsfile is often the source file, not the target.  The
    reliable route is pptr.deref(), which returns the target ObjectReader.
    """
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
    # Fallback for normal local references where UnityPy deref is unavailable.
    try:
        pid = _pptr_path_id(pptr)
        af = getattr(pptr, "assetsfile", None) or getattr(pptr, "assets_file", None)
        src = str(getattr(af, "name", "") or "")
        if src and pid is not None:
            return src, int(pid)
    except Exception:
        pass
    return None

def _texture_env_transform_text(value: Any) -> str:
    scale = _vec2_tuple(_get(value, "m_Scale", "scale", "Scale", default=None), (1.0, 1.0)) or (1.0, 1.0)
    offset = _vec2_tuple(_get(value, "m_Offset", "offset", "Offset", default=None), (0.0, 0.0)) or (0.0, 0.0)
    sx, sy = scale
    ox, oy = offset
    if abs(sx - 1.0) < 1e-6 and abs(sy - 1.0) < 1e-6 and abs(ox) < 1e-6 and abs(oy) < 1e-6:
        return ""
    return f"  UV transform: scale {sx:.3f}, {sy:.3f}; offset {ox:.3f}, {oy:.3f}"


def _read(record: Any) -> Any | None:
    try:
        return record.object.read()
    except Exception:
        return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _pair_key_value(item: Any) -> tuple[Any, Any]:
    if item is None:
        return None, None

    # Case 1: normal tuple/list
    if isinstance(item, (list, tuple)) and len(item) >= 2:
        return item[0], item[1]

    # Case 2: UnityPy-style objects
    for a, b in (("key", "value"), ("first", "second"), ("Key", "Value")):
        if hasattr(item, a) and hasattr(item, b):
            try:
                return getattr(item, a), getattr(item, b)
            except Exception:
                pass

    # Case 3: dictionary-like
    if isinstance(item, dict):
        # Unity sometimes gives {"m_Key": ..., "m_Value": ...}
        for k_key, k_val in (("key", "value"), ("m_Key", "m_Value")):
            if k_key in item and k_val in item:
                return item[k_key], item[k_val]

    # ❗ IMPORTANT FIX: NEVER return broken key/value pair
    return None, None

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


def _pptr_external_source_name(pptr: Any) -> str:
    """Return the external SerializedFile/CAB selected by a PPtr FileID.

    This is a best-effort diagnostic.  It supports the common UnityPy external
    table attribute names without making bundle resolution depend on them.
    """
    fid = _pptr_file_id(pptr)
    if fid in (None, 0):
        return ""
    assets_file = (
        getattr(pptr, "assetsfile", None)
        or getattr(pptr, "assets_file", None)
        or getattr(pptr, "assetsFile", None)
    )
    if assets_file is None:
        return ""
    externals = None
    for name in ("externals", "m_Externals", "external_files", "externalFiles"):
        try:
            value = getattr(assets_file, name)
        except Exception:
            value = None
        if value is not None:
            externals = value
            break
    rows = _as_list(externals)
    if not rows or int(fid) < 1 or int(fid) > len(rows):
        return ""
    item = rows[int(fid) - 1]
    for name in ("path", "name", "file_name", "fileName", "m_PathName", "m_FileName"):
        value = _get(item, name, default=None)
        if value:
            text = str(value).replace("\\", "/").rstrip("/")
            return text.rsplit("/", 1)[-1]
    text = str(item or "").strip()
    return text if text and text != "None" else ""


def _record_name_from_pptr(pptr: Any, bundle_index: Any | None = None) -> str:
    path_id = _pptr_path_id(pptr)
    if path_id is not None and bundle_index is not None:
        # Use the same resolver path as the object/render chain.  Earlier builds
        # only looked in the current bundle here, which made material/shader
        # summaries less useful once external sibling bundles were attached.
        rec = _resolve_record(bundle_index, pptr)
        if rec is not None:
            return rec.name
    return f"PathID {path_id}" if path_id is not None else "-"




# Friendly material-property helpers. Unity shaders use many different property
# names, so these are intentionally heuristic: show the useful intent without
# hiding the raw Unity name.
TEXTURE_SLOT_ROLES: list[tuple[tuple[str, ...], str]] = [
    (("basemap", "maintex", "maintexture", "albedo", "basecolor", "colormap", "colourmap", "diffuse"), "🖼 Base colour"),
    (("bumpmap", "normal", "normalmap"), "🟣 Normal map"),
    (("metallic", "metal", "roughness", "smoothness", "maskmap", "mask", "specgloss"), "⚫ Mask / metallic / smoothness"),
    (("emission", "emissive", "glow"), "✨ Emission"),
    (("occlusion", "ao"), "🌑 Occlusion"),
    (("height", "parallax"), "⛰ Height / parallax"),
    (("detail"), "🧵 Detail"),
]

IMPORTANT_FLOAT_KEYS = (
    "_Surface", "_Blend", "_AlphaClip", "_Cutoff", "_ZWrite", "_Cull",
    "_Metallic", "_Smoothness", "_Glossiness", "_SpecularHighlights",
    "_EnvironmentReflections", "_BumpScale", "_Emission", "_QueueOffset",
)

IMPORTANT_COLOR_KEYS = (
    "_BaseColor", "_Color", "_EmissionColor", "_SpecColor", "_Tint",
)

FRIENDLY_PROPERTY_NAMES = {
    "_BaseMap": "🖼 Base colour texture",
    "_ColorMap": "🖼 Base colour texture",
    "_ColourMap": "🖼 Base colour texture",
    "_BaseColorMap": "🖼 Base colour texture",
    "_MainTex": "🖼 Main texture",
    "_MainTexture": "🖼 Main texture",
    "_Albedo": "🖼 Albedo texture",
    "_BaseTex": "🖼 Base colour texture",
    "_BaseColor": "🎨 Base colour",
    "_Color": "🎨 Colour",
    "_EmissionColor": "✨ Emission colour",
    "_EmissionMap": "✨ Emission texture",
    "_BumpMap": "🟣 Normal map",
    "_NormalMap": "🟣 Normal map",
    "_MetallicGlossMap": "⚫ Metallic / smoothness map",
    "_MaskMap": "⚫ Mask map",
    "_SpecGlossMap": "⚫ Specular / gloss map",
    "_OcclusionMap": "🌑 Occlusion map",
    "_ParallaxMap": "⛰ Height / parallax map",
    "_Smoothness": "🪞 Smoothness",
    "_Glossiness": "🪞 Glossiness",
    "_Metallic": "⚙ Metallic",
    "_Cutoff": "✂ Alpha cutoff",
    "_AlphaClip": "✂ Alpha clip",
    "_Surface": "🧪 Surface mode",
    "_Blend": "🧪 Blend mode",
    "_ZWrite": "🧪 Depth write",
    "_Cull": "🧪 Culling",
}


def friendly_property_name(value: Any) -> str:
    raw = _clean_prop_name(value)
    friendly = FRIENDLY_PROPERTY_NAMES.get(raw)
    if friendly:
        return f"{friendly} ({raw})"
    return raw


def _colour_hex(value: Any) -> str | None:
    comps = []
    for c in ("r", "g", "b", "a"):
        v = _get(value, c, default=None)
        if v is None:
            return None
        try:
            fv = max(0.0, min(1.0, float(v)))
        except Exception:
            return None
        comps.append(int(round(fv * 255)))
    return "#" + "".join(f"{x:02X}" for x in comps)


def _clean_prop_name(value: Any) -> str:
    text = str(value) if value is not None else ""
    return text.strip().strip("'").strip('"')


def _normalised_prop_name(value: Any) -> str:
    return _clean_prop_name(value).lower().replace("_", "").replace(" ", "")


def material_texture_role(prop_name: Any) -> str:
    normalised = _normalised_prop_name(prop_name)
    for needles, label in TEXTURE_SLOT_ROLES:
        if any(n in normalised for n in needles):
            return label
    return "🖼 Texture"


def _format_material_value(value: Any) -> str:
    if value is None:
        return "-"
    try:
        if isinstance(value, float):
            return f"{value:.4g}"
        if isinstance(value, int):
            return str(value)
    except Exception:
        pass
    # Unity colour/vector structs normally expose x/y/z/w or r/g/b/a.
    comp_sets = (("r", "g", "b", "a"), ("x", "y", "z", "w"))
    for comps in comp_sets:
        vals = []
        ok = True
        for c in comps:
            v = _get(value, c, default=None)
            if v is None:
                ok = False
                break
            try:
                vals.append(f"{float(v):.3f}")
            except Exception:
                vals.append(str(v))
        if ok:
            return ", ".join(vals)
    return str(value)


def _pairs_to_dict(items: list[Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items:
        key, value = _pair_key_value(item)
        key_text = _clean_prop_name(key)
        if key_text:
            out[key_text] = value
    return out


def _float_number(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _surface_name(floats: dict[str, Any]) -> str:
    surface = _float_number(floats.get("_Surface"))
    blend = _float_number(floats.get("_Blend"))
    alpha_clip = _float_number(floats.get("_AlphaClip"))
    zwrite = _float_number(floats.get("_ZWrite"))
    queue = _float_number(floats.get("_QueueOffset"))

    parts: list[str] = []
    if surface is not None:
        parts.append("Transparent" if int(surface) == 1 else "Opaque")
    if blend is not None:
        blend_names = {0: "Alpha", 1: "Premultiply", 2: "Additive", 3: "Multiply"}
        parts.append(f"Blend: {blend_names.get(int(blend), int(blend))}")
    if alpha_clip is not None:
        parts.append("Alpha clip: on" if alpha_clip >= 0.5 else "Alpha clip: off")
    if zwrite is not None:
        parts.append("ZWrite: on" if zwrite >= 0.5 else "ZWrite: off")
    if queue is not None and queue != 0:
        parts.append(f"Queue offset: {int(queue)}")
    return " | ".join(parts) if parts else "Not explicitly exposed"


def _property_subset(props: dict[str, Any], keys: tuple[str, ...], limit: int = 30) -> list[tuple[str, Any]]:
    selected: list[tuple[str, Any]] = []
    used = set()
    for wanted in keys:
        if wanted in props:
            selected.append((wanted, props[wanted]))
            used.add(wanted)
    # Include other shader properties that look likely to matter visually.
    visual_words = ("alpha", "cutoff", "metal", "smooth", "rough", "gloss", "bump", "emission", "surface", "blend", "zwrite", "cull")
    for k, v in props.items():
        if k in used:
            continue
        nk = k.lower()
        if any(w in nk for w in visual_words):
            selected.append((k, v))
            used.add(k)
        if len(selected) >= limit:
            break
    return selected



def audio_details(record: Any) -> AudioDetails | None:
    data = _read(record)
    if data is None:
        return None

    direct = _get(data, "m_AudioData", "audio_data", default=None)
    direct_size = None
    if isinstance(direct, (bytes, bytearray)):
        direct_size = len(direct)
    elif isinstance(direct, list):
        direct_size = len(direct)

    resource = _get(data, "m_Resource", "resource", default=None)
    return AudioDetails(
        name=_get(data, "m_Name", "name", default=record.name) or record.name,
        length=_get(data, "m_Length", "length", default=None),
        channels=_get(data, "m_Channels", "channels", default=None),
        frequency=_get(data, "m_Frequency", "frequency", default=None),
        bits_per_sample=_get(data, "m_BitsPerSample", "bits_per_sample", default=None),
        load_type=_get(data, "m_LoadType", "load_type", default=None),
        compression_format=str(_get(data, "m_CompressionFormat", "compression_format", default="")),
        audio_data_size=direct_size,
        resource_offset=_get(resource, "m_Offset", "offset", default=None) if resource is not None else None,
        resource_size=_get(resource, "m_Size", "size", default=None) if resource is not None else None,
        resource_source=_get(resource, "m_Source", "source", default="") if resource is not None else "",
    )


def _describe_audio(record: Any) -> list[str]:
    ad = audio_details(record)
    if not ad:
        return ["Audio metadata could not be read."]

    lines: list[str] = ["🔊 AudioClip"]
    if ad.length is not None:
        try:
            lines.append(f"⏱ Length: {float(ad.length):.3f} seconds")
        except Exception:
            lines.append(f"⏱ Length: {ad.length}")
    lines.append(f"🎚 Channels: {ad.channels if ad.channels is not None else '-'}")
    lines.append(f"📈 Frequency: {ad.frequency if ad.frequency is not None else '-'} Hz")
    lines.append(f"🔢 Bits per sample: {ad.bits_per_sample if ad.bits_per_sample is not None else '-'}")
    lines.append(f"📦 Load type: {ad.load_type if ad.load_type is not None else '-'}")
    if ad.compression_format:
        lines.append(f"🧩 Compression format: {ad.compression_format}")

    lines.append("")
    lines.append("💾 Audio data")
    lines.append(f"  Embedded data size: {human_bytes(ad.audio_data_size)}")
    if ad.resource_source or ad.resource_size is not None or ad.resource_offset is not None:
        lines.append("")
        lines.append("📦 External / streamed resource")
        lines.append(f"  Source: {ad.resource_source or '-'}")
        if ad.resource_offset is not None:
            lines.append(f"  Offset: {int(ad.resource_offset):,}")
        if ad.resource_size is not None:
            lines.append(f"  Size: {human_bytes(int(ad.resource_size))}")
        lines.append("  UBE automatically searches beside the opened Unity file for matching .resource/.resS support files.")

    lines.append("")
    lines.append("🎧 Audio insight")
    lines.append("UBE exports the original audio container safely.")
    lines.append("FMOD FSB5 clips can be previewed through the optional vgmstream-cli decoder; UBE converts only a temporary WAV for playback and preserves the original FSB for export.")
    return lines


def _audio_bool_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return "True" if bool(value) else "False"
    except Exception:
        return str(value)


def _audio_curve_key_count(curve: Any) -> int | None:
    if curve is None:
        return None
    for name in ("m_Curve", "curve", "keys", "m_Keys"):
        values = _get(curve, name, default=None)
        if isinstance(values, (list, tuple)):
            return len(values)
    try:
        return len(curve)
    except Exception:
        return None


def _describe_audio_source(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    """Describe Unity AudioSource playback and its assigned AudioClip.

    AudioSource is the scene component that plays a clip.  It does not contain
    the encoded audio bytes itself; ``m_audioClip``/``m_AudioClip`` points to an
    AudioClip asset, which UBE exposes as a clickable relationship.
    """
    data = _read(record)
    lines: list[str] = ["🎧 Audio Source inspector"]
    if data is None:
        lines.append("Unable to read AudioSource data.")
        return lines

    game_object = _get(data, "m_GameObject", "gameObject", "game_object", default=None)
    enabled = _get(data, "m_Enabled", "enabled", default=None)
    clip_pptr = _get(
        data,
        "m_audioClip", "m_AudioClip", "audioClip", "audio_clip", "m_Clip", "clip",
        default=None,
    )
    mixer_pptr = _get(
        data,
        "m_OutputAudioMixerGroup", "OutputAudioMixerGroup", "outputAudioMixerGroup",
        "output_audio_mixer_group", default=None,
    )

    lines.append(f"Enabled: {_audio_bool_text(enabled)}")
    lines.append(f"Owning object: {_pptr_text(game_object, bundle_index)}")
    lines.append("")
    lines.append("🔊 Assigned audio")
    clip_pid = _pptr_path_id(clip_pptr)
    clip_rec = _resolve_record(bundle_index, clip_pptr)
    if clip_pid in (None, 0):
        lines.append("  AudioClip: none assigned")
    else:
        lines.append(f"  AudioClip: {_pptr_text(clip_pptr, bundle_index)}")
        if clip_rec is not None and getattr(clip_rec, "type_name", "") == "AudioClip":
            details = audio_details(clip_rec)
            if details is not None:
                if details.length is not None:
                    try:
                        lines.append(f"  Duration: {float(details.length):.3f}s")
                    except Exception:
                        lines.append(f"  Duration: {details.length}")
                if details.channels is not None:
                    lines.append(f"  Channels: {details.channels}")
                if details.frequency is not None:
                    lines.append(f"  Frequency: {details.frequency} Hz")
                if details.compression_format:
                    lines.append(f"  Compression: {details.compression_format}")
                if details.resource_source:
                    lines.append(f"  Streamed resource: {details.resource_source}")
                elif details.audio_data_size is not None:
                    lines.append(f"  Embedded audio data: {human_bytes(details.audio_data_size)}")
        else:
            lines.extend(_pptr_resolution_lines("AudioClip", clip_pptr, bundle_index, indent="  "))

    if mixer_pptr is not None and _pptr_path_id(mixer_pptr) not in (None, 0):
        lines.append(f"  Output mixer group: {_pptr_text(mixer_pptr, bundle_index)}")

    lines.append("")
    lines.append("▶ Playback settings")
    playback_fields = (
        ("Play on awake", ("m_PlayOnAwake", "playOnAwake", "play_on_awake"), "bool"),
        ("Loop", ("Loop", "m_Loop", "loop"), "bool"),
        ("Mute", ("Mute", "m_Mute", "mute"), "bool"),
        ("Volume", ("m_Volume", "volume"), "number"),
        ("Pitch", ("m_Pitch", "pitch"), "number"),
        ("Priority", ("Priority", "m_Priority", "priority"), "number"),
        ("Bypass effects", ("BypassEffects", "m_BypassEffects", "bypassEffects"), "bool"),
        ("Bypass listener effects", ("BypassListenerEffects", "m_BypassListenerEffects", "bypassListenerEffects"), "bool"),
        ("Bypass reverb zones", ("BypassReverbZones", "m_BypassReverbZones", "bypassReverbZones"), "bool"),
    )
    found_playback = False
    for label, names, kind in playback_fields:
        value = _get(data, *names, default=None)
        if value is None:
            continue
        found_playback = True
        text = _audio_bool_text(value) if kind == "bool" else _fmt_float(value)
        lines.append(f"  {label}: {text}")
    if not found_playback:
        lines.append("  No standard playback fields were exposed by this Unity version/typetree.")

    lines.append("")
    lines.append("📍 2D / 3D spatial audio")
    spatial_fields = (
        ("Spatial blend", ("m_SpatialBlend", "SpatialBlend", "spatialBlend", "spatial_blend")),
        ("Stereo pan", ("Pan2D", "m_Pan2D", "panStereo", "stereoPan")),
        ("Doppler level", ("DopplerLevel", "m_DopplerLevel", "dopplerLevel")),
        ("Spread", ("Spread", "m_Spread", "spread")),
        ("Min distance", ("MinDistance", "m_MinDistance", "minDistance")),
        ("Max distance", ("MaxDistance", "m_MaxDistance", "maxDistance")),
        ("Rolloff mode", ("rolloffMode", "m_RolloffMode", "RolloffMode")),
        ("Reverb zone mix", ("m_ReverbZoneMix", "ReverbZoneMix", "reverbZoneMix")),
        ("Spatialize", ("m_Spatialize", "Spatialize", "spatialize")),
        ("Spatialize post effects", ("m_SpatializePostEffects", "SpatializePostEffects", "spatializePostEffects")),
    )
    found_spatial = False
    for label, names in spatial_fields:
        value = _get(data, *names, default=None)
        if value is None:
            continue
        found_spatial = True
        if isinstance(value, bool):
            text = _audio_bool_text(value)
        else:
            try:
                text = _fmt_float(value)
            except Exception:
                text = str(value)
        lines.append(f"  {label}: {text}")
    if not found_spatial:
        lines.append("  No spatial-audio fields were exposed by this Unity version/typetree.")

    curve_rows: list[str] = []
    for label, names in (
        ("Volume rolloff", ("rolloffCustomCurve", "m_RolloffCustomCurve")),
        ("Spatial blend", ("panLevelCustomCurve", "m_PanLevelCustomCurve")),
        ("Spread", ("spreadCustomCurve", "m_SpreadCustomCurve")),
        ("Reverb zone mix", ("reverbZoneMixCustomCurve", "m_ReverbZoneMixCustomCurve")),
    ):
        curve = _get(data, *names, default=None)
        count = _audio_curve_key_count(curve)
        if count is not None:
            curve_rows.append(f"  {label} curve: {count} key(s)")
    if curve_rows:
        lines.append("")
        lines.append("📈 Distance/custom curves")
        lines.extend(curve_rows)

    lines.append("")
    lines.append("🧠 AudioSource insight")
    if clip_pid not in (None, 0):
        lines.append("This component is the scene playback link to the AudioClip shown above. Open the AudioClip from References to preview or export the actual sound.")
    else:
        lines.append("This AudioSource has no serialized AudioClip assigned. A script may assign or play audio dynamically at runtime.")
    lines.append("An AudioSource beside an animation owner is a strong companion-audio clue, but exact synchronisation may still be started by a MonoBehaviour, AnimationEvent, Timeline, or other runtime code.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _audio_mixer_id_text(value: Any) -> str:
    """Readable mixer parameter/group IDs without pretending they are values."""
    if value is None:
        return "-"
    if isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
        return raw.hex() if raw else "-"
    if isinstance(value, bool):
        return _audio_bool_text(value)
    if isinstance(value, int):
        return f"{value} (0x{value & 0xFFFFFFFF:08X})" if abs(value) > 9999 else str(value)
    # Unity GUID/Hash128-like structures commonly expose four words or a string form.
    for names in (("data", "m_Data"), ("value", "m_Value")):
        inner = _get_any(value, *names, default=None)
        if inner is not None and inner is not value:
            return _audio_mixer_id_text(inner)
    if isinstance(value, (list, tuple)):
        try:
            vals = [int(v) for v in value]
            return "-".join(f"{v & 0xFFFFFFFF:08X}" for v in vals)
        except Exception:
            return str(value)
    text = str(value)
    return text if text and text != "None" else "-"


def _audio_mixer_pptr_list(value: Any) -> list[Any]:
    out: list[Any] = []
    for item in _as_list(value):
        pptr = _get_any(item, "group", "m_Group", "effect", "m_Effect", "snapshot", "m_Snapshot", default=item)
        if _pptr_path_id(pptr) not in (None, 0):
            out.append(pptr)
    return out


def _audio_mixer_parameter_rows(value: Any, limit: int = 20) -> list[str]:
    rows: list[str] = []
    for i, item in enumerate(_as_list(value)[:limit]):
        key, val = _pair_key_value(item)
        if key is not None:
            rows.append(f"  {i}: {_audio_mixer_id_text(key)} = {_fmt_float(val) if isinstance(val, (int, float)) else _audio_mixer_id_text(val)}")
            continue
        name = _get_any(item, "name", "m_Name", "parameterName", "m_ParameterName", default=None)
        guid = _get_any(item, "guid", "m_Guid", "id", "m_ID", "parameter", "m_Parameter", default=None)
        if name is not None or guid is not None:
            text = str(name or f"Parameter {i}")
            if guid is not None:
                text += f" — {_audio_mixer_id_text(guid)}"
            rows.append(f"  {text}")
        else:
            rows.append(f"  {i}: {_audio_mixer_id_text(item)}")
    return rows


def _describe_audio_mixer_group(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🎛 Audio Mixer Group inspector"]
    if data is None:
        lines.append("Unable to read AudioMixerGroup data.")
        return lines

    mixer = _get_any(data, "m_AudioMixer", "audioMixer", "m_Controller", "controller", default=None)
    parent = _get_any(data, "m_Parent", "parent", "m_ParentGroup", "parentGroup", default=None)
    children = _audio_mixer_pptr_list(_get_any(data, "m_Children", "children", "m_ChildGroups", "childGroups", default=None))
    effects = _audio_mixer_pptr_list(_get_any(data, "m_Effects", "effects", "m_EffectChain", "effectChain", default=None))

    lines.append("Routing role: receives AudioSource output, applies group processing, then routes into the mixer hierarchy.")
    if mixer is not None and _pptr_path_id(mixer) not in (None, 0):
        lines.append(f"Owning mixer: {_pptr_text(mixer, bundle_index)}")
    if parent is not None and _pptr_path_id(parent) not in (None, 0):
        lines.append(f"Parent group: {_pptr_text(parent, bundle_index)}")

    lines.append("")
    lines.append("🎚 Group controls / parameter IDs")
    shown = False
    for label, names, kind in (
        ("Group ID", ("m_GroupID", "groupID", "m_ID", "id"), "id"),
        ("Volume parameter", ("m_Volume", "volume", "m_VolumeParameter", "volumeParameter"), "id"),
        ("Pitch parameter", ("m_Pitch", "pitch", "m_PitchParameter", "pitchParameter"), "id"),
        ("Send parameter", ("m_Send", "send", "m_SendParameter", "sendParameter"), "id"),
        ("Mute", ("m_Mute", "mute"), "bool"),
        ("Solo", ("m_Solo", "solo"), "bool"),
        ("Bypass effects", ("m_BypassEffects", "bypassEffects"), "bool"),
        ("User colour index", ("m_UserColorIndex", "userColorIndex"), "value"),
    ):
        value = _get_any(data, *names, default=None)
        if value is None:
            continue
        shown = True
        if kind == "bool":
            text = _audio_bool_text(value)
        elif kind == "id":
            text = _audio_mixer_id_text(value)
        else:
            text = _fmt_float(value) if isinstance(value, (int, float)) else str(value)
        lines.append(f"  {label}: {text}")
    if not shown:
        lines.append("  No standard group-control fields were exposed by this Unity version/typetree.")

    lines.append("")
    lines.append("🌳 Mixer hierarchy")
    if children:
        lines.append(f"  Child groups: {len(children)}")
        for i, child in enumerate(children[:24]):
            lines.append(f"    {i}: {_pptr_text(child, bundle_index)}")
        if len(children) > 24:
            lines.append(f"    ... {len(children) - 24} more")
    else:
        lines.append("  Child groups: 0 or not exposed")

    lines.append("")
    lines.append("✨ Effect chain")
    if effects:
        lines.append(f"  Effects: {len(effects)}")
        for i, effect in enumerate(effects[:24]):
            lines.append(f"    {i}: {_pptr_text(effect, bundle_index)}")
        if len(effects) > 24:
            lines.append(f"    ... {len(effects) - 24} more")
    else:
        lines.append("  No serialized effect references were exposed on this group.")

    lines.append("")
    lines.append("🧠 Audio Mixer Group insight")
    lines.append("An AudioMixerGroup is a routing bus, not a sound library. AudioSources can send their output here, and the group can apply volume, pitch, effects and snapshot-controlled values.")
    lines.append("The reverse Used by list is the useful connection back to AudioSources routed through this group. A group does not normally identify which AudioClip an empty AudioSource will receive at runtime.")

    fields = _short_field_list(data, {
        "m_Name", "m_AudioMixer", "m_Controller", "m_Parent", "m_ParentGroup", "m_Children", "m_ChildGroups",
        "m_Effects", "m_EffectChain", "m_GroupID", "m_ID", "m_Volume", "m_Pitch", "m_Send",
        "m_Mute", "m_Solo", "m_BypassEffects", "m_UserColorIndex",
    }, limit=32)
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_audio_mixer_controller(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🎚 Audio Mixer inspector"]
    if data is None:
        lines.append("Unable to read AudioMixer data.")
        return lines

    output = _get_any(data, "m_OutputGroup", "outputGroup", "m_MasterGroup", "masterGroup", default=None)
    start_snapshot = _get_any(data, "m_StartSnapshot", "startSnapshot", "m_CurrentSnapshot", "currentSnapshot", default=None)
    groups = _audio_mixer_pptr_list(_get_any(data, "m_Groups", "groups", "m_GroupList", "groupList", default=None))
    snapshots = _audio_mixer_pptr_list(_get_any(data, "m_Snapshots", "snapshots", default=None))
    exposed = _get_any(data, "m_ExposedParameters", "exposedParameters", "m_ExposedParameterNames", default=None)

    lines.append("This asset defines the audio routing tree shared by AudioSources and AudioMixerGroups.")
    lines.append("")
    lines.append("🔀 Routing")
    if output is not None and _pptr_path_id(output) not in (None, 0):
        lines.append(f"  Master/output group: {_pptr_text(output, bundle_index)}")
    else:
        lines.append("  Master/output group: not exposed")
    if start_snapshot is not None and _pptr_path_id(start_snapshot) not in (None, 0):
        lines.append(f"  Start snapshot: {_pptr_text(start_snapshot, bundle_index)}")

    lines.append("")
    lines.append("🌳 Groups and snapshots")
    lines.append(f"  Group references: {len(groups)}")
    for i, group in enumerate(groups[:32]):
        lines.append(f"    Group {i}: {_pptr_text(group, bundle_index)}")
    if len(groups) > 32:
        lines.append(f"    ... {len(groups) - 32} more")
    lines.append(f"  Snapshot references: {len(snapshots)}")
    for i, snap in enumerate(snapshots[:24]):
        lines.append(f"    Snapshot {i}: {_pptr_text(snap, bundle_index)}")
    if len(snapshots) > 24:
        lines.append(f"    ... {len(snapshots) - 24} more")

    lines.append("")
    lines.append("⏸ Runtime/suspend settings")
    settings_found = False
    for label, names, kind in (
        ("Enable suspend", ("m_EnableSuspend", "enableSuspend"), "bool"),
        ("Suspend threshold", ("m_SuspendThreshold", "suspendThreshold"), "value"),
        ("Update mode", ("m_UpdateMode", "updateMode"), "value"),
    ):
        value = _get_any(data, *names, default=None)
        if value is None:
            continue
        settings_found = True
        lines.append(f"  {label}: {_audio_bool_text(value) if kind == 'bool' else _fmt_float(value)}")
    if not settings_found:
        lines.append("  No standard runtime mixer fields were exposed.")

    exposed_rows = _audio_mixer_parameter_rows(exposed, 32)
    if exposed_rows:
        lines.append("")
        lines.append(f"🎚 Exposed parameters ({len(_as_list(exposed))})")
        lines.extend(exposed_rows)
        if len(_as_list(exposed)) > 32:
            lines.append(f"  ... {len(_as_list(exposed)) - 32} more")

    lines.append("")
    lines.append("🧠 Audio Mixer insight")
    lines.append("The mixer organizes routing, effects and snapshots. It does not store the dialogue/music clips themselves; AudioClip selection remains on AudioSources or in runtime scripts/events.")

    fields = _short_field_list(data, {
        "m_Name", "m_OutputGroup", "m_MasterGroup", "m_StartSnapshot", "m_CurrentSnapshot", "m_Groups", "m_GroupList",
        "m_Snapshots", "m_ExposedParameters", "m_ExposedParameterNames", "m_EnableSuspend", "m_SuspendThreshold", "m_UpdateMode",
    }, limit=36)
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_audio_mixer_snapshot(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["📸 Audio Mixer Snapshot inspector"]
    if data is None:
        lines.append("Unable to read AudioMixerSnapshot data.")
        return lines

    mixer = _get_any(data, "m_AudioMixer", "audioMixer", "m_Controller", "controller", default=None)
    snapshot_id = _get_any(data, "m_SnapshotID", "snapshotID", "m_ID", "id", default=None)
    float_values = _get_any(data, "m_FloatValues", "floatValues", "m_Values", "values", default=None)
    transitions = _get_any(data, "m_TransitionOverrides", "transitionOverrides", "m_Transitions", "transitions", default=None)

    if mixer is not None and _pptr_path_id(mixer) not in (None, 0):
        lines.append(f"Owning mixer: {_pptr_text(mixer, bundle_index)}")
    if snapshot_id is not None:
        lines.append(f"Snapshot ID: {_audio_mixer_id_text(snapshot_id)}")

    values_list = _as_list(float_values)
    lines.append("")
    lines.append(f"🎚 Stored parameter values: {len(values_list)}")
    rows = _audio_mixer_parameter_rows(values_list, 32)
    lines.extend(rows if rows else ["  No parameter-value map was exposed."])
    if len(values_list) > 32:
        lines.append(f"  ... {len(values_list) - 32} more")

    transition_list = _as_list(transitions)
    lines.append("")
    lines.append(f"↔ Transition overrides: {len(transition_list)}")
    transition_rows = _audio_mixer_parameter_rows(transition_list, 24)
    lines.extend(transition_rows if transition_rows else ["  No transition override map was exposed."])
    if len(transition_list) > 24:
        lines.append(f"  ... {len(transition_list) - 24} more")

    lines.append("")
    lines.append("🧠 Audio Mixer Snapshot insight")
    lines.append("A snapshot stores a preset of mixer parameter values. Scripts can blend or switch snapshots to change ambience, music, dialogue balance or effects, but the snapshot does not choose the AudioClip itself.")

    fields = _short_field_list(data, {
        "m_Name", "m_AudioMixer", "m_Controller", "m_SnapshotID", "m_ID", "m_FloatValues", "m_Values",
        "m_TransitionOverrides", "m_Transitions",
    }, limit=32)
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_audio_mixer_effect(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["✨ Audio Mixer Effect inspector"]
    if data is None:
        lines.append("Unable to read AudioMixerEffect data.")
        return lines

    group = _get_any(data, "m_Group", "group", "m_Owner", "owner", default=None)
    send_target = _get_any(data, "m_SendTarget", "sendTarget", "m_Target", "target", default=None)
    if group is not None and _pptr_path_id(group) not in (None, 0):
        lines.append(f"Owning group: {_pptr_text(group, bundle_index)}")
    if send_target is not None and _pptr_path_id(send_target) not in (None, 0):
        lines.append(f"Send target: {_pptr_text(send_target, bundle_index)}")

    lines.append("")
    lines.append("⚙ Effect settings")
    found = False
    for label, names, kind in (
        ("Effect ID", ("m_EffectID", "effectID", "m_ID", "id"), "id"),
        ("Enabled", ("m_Enabled", "enabled"), "bool"),
        ("Bypass", ("m_Bypass", "bypass"), "bool"),
        ("Wet mix parameter", ("m_WetMixLevel", "wetMixLevel", "m_WetMixParameter", "wetMixParameter"), "id"),
    ):
        value = _get_any(data, *names, default=None)
        if value is None:
            continue
        found = True
        lines.append(f"  {label}: {_audio_bool_text(value) if kind == 'bool' else _audio_mixer_id_text(value)}")
    params = _get_any(data, "m_Parameters", "parameters", "m_ParameterValues", "parameterValues", default=None)
    param_rows = _audio_mixer_parameter_rows(params, 32)
    if param_rows:
        lines.append(f"  Parameters: {len(_as_list(params))}")
        lines.extend("  " + row.strip() for row in param_rows)
    if not found and not param_rows:
        lines.append("  No standard effect fields were exposed.")

    lines.append("")
    lines.append("🧠 Audio Mixer Effect insight")
    lines.append("This is a processor in an AudioMixerGroup effect chain. It changes routed sound but does not normally contain or select an AudioClip.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def texture_details(record: Any) -> TextureDetails | None:
    data = _read(record)
    if data is None:
        return None

    fmt_raw = _get(data, "m_TextureFormat", "texture_format", default="")

    stream = _get(data, "m_StreamData", "stream_data", default=None)
    stream_offset = stream_size = None
    stream_path = ""
    if stream is not None:
        stream_offset = _get(stream, "offset", "m_Offset", default=None)
        stream_size = _get(stream, "size", "m_Size", default=None)
        stream_path = _get(stream, "path", "m_Path", default="") or ""

    return TextureDetails(
        name=_get(data, "name", "m_Name", default=record.name) or record.name,
        width=_get(data, "m_Width", "width", default=None),
        height=_get(data, "m_Height", "height", default=None),
        texture_format=texture_format_name(fmt_raw),
        texture_format_raw=str(fmt_raw) if fmt_raw is not None else "",
        mip_count=_get(data, "m_MipCount", "m_MipMap", "mip_count", default=None),
        complete_image_size=_get(data, "m_CompleteImageSize", "complete_image_size", default=None),
        stream_offset=stream_offset,
        stream_size=stream_size,
        stream_path=stream_path,
    )


def texture_array_details(record: Any) -> TextureArrayDetails | None:
    data = _read(record)
    if data is None:
        return None

    fmt_raw = _get(data, "m_TextureFormat", "texture_format", "m_Format", "format", default="")

    stream = _get(data, "m_StreamData", "stream_data", default=None)
    stream_offset = stream_size = None
    stream_path = ""
    if stream is not None:
        stream_offset = _get(stream, "offset", "m_Offset", default=None)
        stream_size = _get(stream, "size", "m_Size", default=None)
        stream_path = _get(stream, "path", "m_Path", default="") or ""

    image_data = _get(data, "image_data", "m_ImageData", "image_data_bytes", default=None)
    image_data_size = None
    try:
        if image_data is not None:
            image_data_size = len(image_data)
    except Exception:
        image_data_size = None

    depth = _get(
        data,
        "m_Depth", "depth", "m_DepthTexture", "m_Count", "count", "slice_count", "slices",
        default=None,
    )
    # If UnityPy exposes a list of images/slices, use that length as a useful fallback.
    if depth is None:
        for attr in ("images", "image_list", "slice_images"):
            values = _get(data, attr, default=None)
            if isinstance(values, (list, tuple)):
                depth = len(values)
                break

    return TextureArrayDetails(
        name=_get(data, "name", "m_Name", default=record.name) or record.name,
        width=_get(data, "m_Width", "width", default=None),
        height=_get(data, "m_Height", "height", default=None),
        depth=depth,
        texture_format=texture_format_name(fmt_raw),
        texture_format_raw=str(fmt_raw) if fmt_raw is not None else "",
        mip_count=_get(data, "m_MipCount", "m_MipMap", "mip_count", default=None),
        complete_image_size=_get(data, "m_CompleteImageSize", "complete_image_size", default=None),
        image_data_size=image_data_size,
        stream_offset=stream_offset,
        stream_size=stream_size,
        stream_path=stream_path,
    )



def cubemap_details(record: Any) -> CubemapDetails | None:
    data = _read(record)
    if data is None:
        return None

    fmt_raw = _get(data, "m_TextureFormat", "texture_format", "m_Format", "format", default="")

    stream = _get(data, "m_StreamData", "stream_data", default=None)
    stream_offset = stream_size = None
    stream_path = ""
    if stream is not None:
        stream_offset = _get(stream, "offset", "m_Offset", default=None)
        stream_size = _get(stream, "size", "m_Size", default=None)
        stream_path = _get(stream, "path", "m_Path", default="") or ""

    tex_settings = _get(data, "m_TextureSettings", "texture_settings", default=None)
    width = _get(data, "m_Width", "width", "m_Size", "size", default=None)
    height = _get(data, "m_Height", "height", "m_Size", "size", default=None)
    if height is None:
        height = width

    image_count = _get(data, "m_ImageCount", "image_count", "images_count", default=None)
    face_count = _get(data, "m_FaceCount", "face_count", default=None)
    if face_count is None:
        # Most Unity cubemaps contain six square faces.  Some decoders expose
        # image count instead of a direct face count, especially with mip data.
        try:
            if image_count is not None and int(image_count) in (6, 12, 18, 24, 30, 36):
                face_count = 6
        except Exception:
            pass
    if face_count is None:
        face_count = 6

    return CubemapDetails(
        name=_get(data, "name", "m_Name", default=record.name) or record.name,
        width=width,
        height=height,
        texture_format=texture_format_name(fmt_raw),
        texture_format_raw=str(fmt_raw) if fmt_raw is not None else "",
        mip_count=_get(data, "m_MipCount", "m_MipMap", "mipmap_count", "mip_count", default=None),
        face_count=face_count,
        image_count=image_count,
        complete_image_size=_get(data, "m_CompleteImageSize", "complete_image_size", default=None),
        stream_offset=stream_offset,
        stream_size=stream_size,
        stream_path=stream_path,
        filter_mode=_get(tex_settings, "m_FilterMode", "filter_mode", default=None) if tex_settings is not None else None,
        aniso_level=_get(tex_settings, "m_Aniso", "m_AnisoLevel", "aniso", "aniso_level", default=None) if tex_settings is not None else None,
        wrap_mode=_get(tex_settings, "m_WrapMode", "wrap_mode", default=None) if tex_settings is not None else None,
    )


def _describe_cubemap(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    cd = cubemap_details(record)
    lines: list[str] = []
    if not cd:
        return ["Cubemap metadata could not be read."]

    lines.append("🌌 Cubemap")
    lines.append(f"↔ Face resolution: {cd.width} x {cd.height}")
    lines.append(f"🧊 Faces: {cd.face_count if cd.face_count is not None else '-'}")
    if cd.image_count is not None:
        lines.append(f"🖼 Stored images / face+mip records: {cd.image_count}")
    lines.append(f"🧩 Format: {cd.texture_format}")
    lines.append(f"📚 Mip levels: {cd.mip_count if cd.mip_count is not None else '-'}")
    gpu_size = cd.stream_size if cd.stream_size is not None else cd.complete_image_size
    decoded_size = None
    try:
        if cd.width and cd.height and cd.face_count:
            decoded_size = int(cd.width) * int(cd.height) * int(cd.face_count) * 4
    except Exception:
        decoded_size = None
    lines.append(f"💾 GPU / stream size: {human_bytes(gpu_size)}")
    lines.append(f"💾 Decoded RGBA estimate: {human_bytes(decoded_size)}")
    lines.append(f"📉 Compression ratio: {compression_ratio(decoded_size, gpu_size)}")

    if cd.filter_mode is not None or cd.wrap_mode is not None or cd.aniso_level is not None:
        lines.append("")
        lines.append("🎛 Sampling settings")
        if cd.filter_mode is not None:
            lines.append(f"  Filter mode: {cd.filter_mode}")
        if cd.wrap_mode is not None:
            lines.append(f"  Wrap mode: {cd.wrap_mode}")
        if cd.aniso_level is not None:
            lines.append(f"  Aniso level: {cd.aniso_level}")

    if cd.stream_path or cd.stream_size is not None or cd.stream_offset is not None:
        lines.append("")
        lines.append("📦 External stream data")
        lines.append(f"  Path: {cd.stream_path or '-'}")
        if cd.stream_offset is not None:
            lines.append(f"  Offset: {int(cd.stream_offset):,}")
        if cd.stream_size is not None:
            lines.append(f"  Size: {human_bytes(int(cd.stream_size))}")

    lines.append("")
    lines.append("🧠 Cubemap insight")
    lines.append("A Cubemap is a six-sided environment texture: +X, -X, +Y, -Y, +Z and -Z.")
    lines.append("Unity commonly uses cubemaps for skyboxes, reflection probes, shiny materials, ambient lighting and distant background scenery.")
    lines.append("Unlike a normal Texture2D, it is sampled by a 3D direction vector rather than a flat U/V coordinate.")

    if bundle_index is not None or asset_graph is not None:
        # Reuse normal relationship output where available; materials often refer
        # to cubemaps through reflection/environment slots.
        try:
            rel_lines = _relationship_lines(record, bundle_index, asset_graph)
            if rel_lines:
                lines.extend(rel_lines)
        except Exception:
            pass
    return lines

def _describe_texture_array(record: Any) -> list[str]:
    td = texture_array_details(record)
    if not td:
        return ["Texture2DArray metadata could not be read."]

    gpu_size = td.stream_size if td.stream_size is not None else (td.image_data_size if td.image_data_size is not None else td.complete_image_size)

    lines: list[str] = []
    lines.append("🧱 Texture2DArray")
    lines.append(f"↔ Slice resolution: {td.width} x {td.height}")
    lines.append(f"🧱 Slices / depth: {td.depth if td.depth is not None else '-'}")
    lines.append(f"🧩 Format: {td.texture_format}")
    lines.append(f"📚 Mip levels: {td.mip_count if td.mip_count is not None else '-'}")
    lines.append(f"💾 GPU / stream size: {human_bytes(gpu_size)}")

    if td.stream_path or td.stream_size is not None or td.stream_offset is not None:
        lines.append("")
        lines.append("📦 External stream data")
        lines.append(f"  Path: {td.stream_path or '-'}")
        if td.stream_offset is not None:
            lines.append(f"  Offset: {td.stream_offset:,}")
        if td.stream_size is not None:
            lines.append(f"  Size: {human_bytes(td.stream_size)}")

    lines.append("")
    lines.append("🧠 Texture array insight")
    lines.append("This is not a normal single PNG texture.")
    lines.append("Shaders sample one slice using a value such as _TextureIndex.")
    lines.append("For example, a fish material may use _BaseMap/_ColorMap = a visible colour texture and _TextureIndex = 12.")
    lines.append("UBE can inspect this metadata and Export Selected Asset can write decoded slices/contact sheets when the data is available or stored in a simple uncompressed format such as RGB24.")
    return lines


def _describe_texture(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    td = texture_details(record)
    lines: list[str] = []
    if not td:
        return ["Texture metadata could not be read."]
    lines.append("🖼 Texture")
    lines.append(f"↔ Resolution: {td.width} x {td.height}")
    lines.append(f"🧩 Format: {td.texture_format}")
    lines.append(f"📚 Mip levels: {td.mip_count if td.mip_count is not None else '-'}")
    gpu_size = td.stream_size if td.stream_size is not None else td.complete_image_size
    decoded_size = decoded_rgba_size(td.width, td.height)
    lines.append(f"💾 GPU size: {human_bytes(gpu_size)}")
    lines.append(f"💾 Decoded RGBA size: {human_bytes(decoded_size)}")
    lines.append(f"📉 Compression ratio: {compression_ratio(decoded_size, gpu_size)}")
    if td.stream_path or td.stream_size is not None or td.stream_offset is not None:
        lines.append("")
        lines.append("📦 External stream data")
        lines.append(f"  Path: {td.stream_path or '-'}")
        if td.stream_offset is not None:
            lines.append(f"  Offset: {td.stream_offset:,}")
        if td.stream_size is not None:
            lines.append(f"  Size: {human_bytes(td.stream_size)}")
    lines.extend(_describe_texture_usage(record, bundle_index, asset_graph))
    return lines


def _record_from_graph_source(rel: Any, bundle_index: Any | None) -> Any | None:
    if bundle_index is None:
        return None
    pid = getattr(rel, "source_path_id", None)
    if pid is None:
        return None
    rec = getattr(bundle_index, "record_by_path_id", {}).get(pid)
    if rec is None:
        rec = getattr(bundle_index, "external_record_by_path_id", {}).get(pid)
    return rec


def _renderer_gameobject_name(renderer_rec: Any, bundle_index: Any | None) -> str:
    data = _read(renderer_rec)
    if data is None:
        return "-"
    go = _get_any(data, "m_GameObject", "game_object", default=None)
    rec = _resolve_record(bundle_index, go)
    if rec is not None:
        return rec.name
    return _pptr_text(go, bundle_index)


def _texture_sprite_users(record: Any, bundle_index: Any | None) -> list[tuple[Any, tuple[float, float, float, float] | None]]:
    if bundle_index is None:
        return []
    out: list[tuple[Any, tuple[float, float, float, float] | None]] = []
    target_pid = int(getattr(record, "path_id", 0))
    for spr in getattr(bundle_index, "objects_by_type", {}).get("Sprite", []):
        data = _read(spr)
        if data is None:
            continue
        tex = _sprite_texture_pptr(data)
        alpha = _sprite_alpha_texture_pptr(data)
        if _pptr_path_id(tex) == target_pid or _pptr_path_id(alpha) == target_pid:
            out.append((spr, _sprite_rect(data)))
    return out


def _describe_texture_usage(record: Any, bundle_index: Any | None, asset_graph: Any | None) -> list[str]:
    """Texture Usage Finder: trace Texture2D -> Material/Sprite -> renderable objects.

    This is intentionally a fast, current-bundle/course-local lookup.  It does not
    open every bundle in a giant game install, but it uses the same related-bundle
    resolver UBE already attaches when a project/course is loaded.
    """
    if bundle_index is None:
        return []

    lines: list[str] = []
    material_rels: list[Any] = []
    render_object_rows: list[tuple[str, str, str, str]] = []
    sprite_rows = _texture_sprite_users(record, bundle_index)

    if asset_graph is not None:
        try:
            asset_graph.index_all_materials(bundle_index)
            asset_graph.index_render_links(bundle_index)
            material_rels = [r for r in asset_graph.used_by(record, bundle_index) if getattr(r, "source_type", "") == "Material"]
        except Exception:
            material_rels = []

        seen_renderer_pids: set[int] = set()
        for mrel in material_rels:
            mat_rec = _record_from_graph_source(mrel, bundle_index)
            if mat_rec is None:
                continue
            try:
                users = asset_graph.used_by(mat_rec, bundle_index)
            except Exception:
                users = []
            for urel in users:
                stype = getattr(urel, "source_type", "")
                if stype not in ("MeshRenderer", "SkinnedMeshRenderer"):
                    continue
                renderer = _record_from_graph_source(urel, bundle_index)
                if renderer is None or renderer.path_id in seen_renderer_pids:
                    continue
                seen_renderer_pids.add(renderer.path_id)
                go_name = _renderer_gameobject_name(renderer, bundle_index)
                render_object_rows.append((mat_rec.name, go_name, renderer.name, getattr(mrel, "relationship", "Texture")))

    if not material_rels and not sprite_rows and not render_object_rows:
        lines.append("")
        lines.append("🔎 Texture Usage Finder")
        lines.append("  No material, sprite or renderer users were found in the currently loaded bundle/related bundle cache.")
        lines.append("  Tip: if you can see this texture in a course, open the level bundle as well, or build/use the project PathID index for global hunts.")
        return lines

    lines.append("")
    lines.append("🔎 Texture Usage Finder")
    lines.append("  Starts from this Texture2D and traces the likely route back to visible assets:")
    lines.append("  Texture → Material/Sprite → Renderer/GameObject")

    if material_rels:
        lines.append("")
        lines.append(f"🎨 Materials using this texture ({len(material_rels)})")
        for i, rel in enumerate(material_rels[:24], 1):
            bundle_note = f"  [{Path(str(getattr(rel, 'external_bundle', '') or '')).name}]" if getattr(rel, "external_bundle", None) else ""
            lines.append(f"  {i}: {getattr(rel, 'source_name', '?')}  via {getattr(rel, 'relationship', 'Texture')}{bundle_note}")
        if len(material_rels) > 24:
            lines.append(f"  ... {len(material_rels) - 24} more materials")

    if render_object_rows:
        lines.append("")
        lines.append(f"🎲 Rendered objects found through those materials ({len(render_object_rows)})")
        for i, (mat_name, go_name, renderer_name, slot) in enumerate(render_object_rows[:48], 1):
            lines.append(f"  {i}: {go_name}  | Renderer: {renderer_name}  | Material: {mat_name} [{slot}]")
        if len(render_object_rows) > 48:
            lines.append(f"  ... {len(render_object_rows) - 48} more renderers")

    if sprite_rows:
        lines.append("")
        lines.append(f"🖼 Sprites using this texture ({len(sprite_rows)})")
        for i, (spr, rect) in enumerate(sprite_rows[:32], 1):
            if rect is not None:
                x, y, w, h = rect
                lines.append(f"  {i}: {spr.name}  rect x {_fmt_float(x)}, y {_fmt_float(y)}, w {_fmt_float(w)}, h {_fmt_float(h)}")
            else:
                lines.append(f"  {i}: {spr.name}")
        if len(sprite_rows) > 32:
            lines.append(f"  ... {len(sprite_rows) - 32} more sprites")

    lines.append("")
    lines.append("🧠 Usage insight")
    lines.append("If the texture is a big atlas, many objects may share it. The material slot name tells you the role: _BaseMap/_ColorMap is visible colour, _BumpMap/_NormalMap is surface detail, _EmissionMap is glow, and mask/metal/roughness textures are shader data rather than direct colour.")

    atlas_lines = _describe_texture_atlas_region_finder(record, bundle_index, asset_graph, material_rels)
    if atlas_lines:
        lines.extend(atlas_lines)
    return lines


def _material_texture_links(mat_rec: Any, bundle_index: Any | None) -> list[tuple[str, Any, Any | None]]:
    """Return (slot/property name, texture pptr, resolved texture record) for a material."""
    data = _read(mat_rec)
    if data is None:
        return []
    saved = _get(data, "m_SavedProperties", "saved_properties", default=None)
    tex_envs = _as_list(_get(saved, "m_TexEnvs", "tex_envs", default=None)) if saved is not None else []
    rows: list[tuple[str, Any, Any | None]] = []
    for item in tex_envs:
        key, value = _pair_key_value(item)
        key_text = _clean_prop_name(key) or "Texture"
        texture = _get(value, "m_Texture", "texture", default=value)
        tex_rec = _resolve_record(bundle_index, texture)
        rows.append((key_text, texture, tex_rec))
    return rows


def _material_uses_texture(mat_rec: Any, target_pid: int, bundle_index: Any | None) -> list[str]:
    slots: list[str] = []
    for key_text, texture, tex_rec in _material_texture_links(mat_rec, bundle_index):
        pid = getattr(tex_rec, "path_id", None) if tex_rec is not None else _pptr_path_id(texture)
        try:
            if int(pid) == int(target_pid):
                slots.append(key_text)
        except Exception:
            pass
    return slots


def _materials_using_texture_fast(record: Any, bundle_index: Any | None, asset_graph: Any | None, known_rels: list[Any] | None = None) -> list[tuple[Any, list[str]]]:
    """Return resolved Material records that reference this texture.

    Prefer the relationship graph when present, then add a direct scan fallback for
    current/related loaded material records.
    """
    if bundle_index is None:
        return []
    target_pid = int(getattr(record, "path_id", 0) or 0)
    out: list[tuple[Any, list[str]]] = []
    seen: set[int] = set()

    for rel in known_rels or []:
        mat = _record_from_graph_source(rel, bundle_index)
        if mat is None or getattr(mat, "type_name", "") != "Material":
            continue
        pid = getattr(mat, "path_id", None)
        if pid in seen:
            continue
        seen.add(pid)
        slot = str(getattr(rel, "relationship", "Texture") or "Texture")
        out.append((mat, [slot]))

    candidates = list(getattr(bundle_index, "objects_by_type", {}).get("Material", []))
    # Some related-bundle material records may only be in the external PathID map.
    for rec in getattr(bundle_index, "external_record_by_path_id", {}).values():
        if getattr(rec, "type_name", "") == "Material":
            candidates.append(rec)

    for mat in candidates:
        pid = getattr(mat, "path_id", None)
        if pid in seen:
            continue
        slots = _material_uses_texture(mat, target_pid, bundle_index)
        if slots:
            seen.add(pid)
            out.append((mat, slots))
    return out


def _renderer_material_slots(renderer_rec: Any, bundle_index: Any | None) -> list[tuple[int, Any | None, Any]]:
    data = _read(renderer_rec)
    if data is None:
        return []
    mats = _as_list(_get(data, "m_Materials", "materials", default=None))
    rows: list[tuple[int, Any | None, Any]] = []
    for i, mat_pptr in enumerate(mats):
        rows.append((i, _resolve_record(bundle_index, mat_pptr), mat_pptr))
    return rows


def _renderers_using_materials(bundle_index: Any | None, material_pids: set[int]) -> list[tuple[Any, int, Any]]:
    if bundle_index is None or not material_pids:
        return []
    rows: list[tuple[Any, int, Any]] = []
    for type_name in ("MeshRenderer", "SkinnedMeshRenderer"):
        candidates = list(getattr(bundle_index, "objects_by_type", {}).get(type_name, []))
        # External records can be metadata-only, but if readable they are useful.
        for rec in getattr(bundle_index, "external_record_by_path_id", {}).values():
            if getattr(rec, "type_name", "") == type_name:
                candidates.append(rec)
        for renderer in candidates:
            for slot_index, mat_rec, mat_pptr in _renderer_material_slots(renderer, bundle_index):
                pid = getattr(mat_rec, "path_id", None) if mat_rec is not None else _pptr_path_id(mat_pptr)
                try:
                    if int(pid) in material_pids:
                        rows.append((renderer, slot_index, mat_rec if mat_rec is not None else mat_pptr))
                except Exception:
                    pass
    return rows


def _atlas_region_quality_text(bounds: dict[str, float], width: int, height: int) -> str:
    try:
        area = max(0.0, float(bounds.get("u_span", 0.0))) * max(0.0, float(bounds.get("v_span", 0.0)))
    except Exception:
        return ""
    if area <= 0:
        return ""
    if area < 0.04:
        return "small atlas tile"
    if area < 0.25:
        return "atlas region"
    if area > 0.85:
        return "mostly full texture"
    return "large atlas region"


def _describe_texture_atlas_region_finder(record: Any, bundle_index: Any | None, asset_graph: Any | None, known_material_rels: list[Any] | None = None) -> list[str]:
    """Estimate which UV pixel regions renderers sample from this selected texture.

    This is the automatic phase of the atlas finder: it starts from Texture2D,
    finds materials/renderers that use it, resolves the attached mesh, then maps
    mesh UV bounds back into this texture's pixel space.
    """
    td = texture_details(record)
    if bundle_index is None or not td or not td.width or not td.height:
        return []

    materials = _materials_using_texture_fast(record, bundle_index, asset_graph, known_material_rels)
    material_pids = {int(getattr(m, "path_id", 0)) for m, _slots in materials if getattr(m, "path_id", None) is not None}
    if not material_pids:
        return []

    renderers = _renderers_using_materials(bundle_index, material_pids)
    if not renderers:
        return []

    try:
        from ..exporters.mesh_exporter import uv_bounds
    except Exception:
        return []

    mat_slot_names: dict[int, list[str]] = {int(getattr(m, "path_id", 0)): slots for m, slots in materials if getattr(m, "path_id", None) is not None}

    # One displayed row is now one renderer/material/mesh combination, and each
    # row lists every available UV channel.  Earlier builds printed UV0 and UV1
    # as separate numbered rows, which made ball/atlas cases confusing because
    # the first click often highlighted UV0 even though the visible colour atlas
    # might be UV1.  Keeping the UV choices together makes it obvious which box
    # belongs to which channel.
    rows: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int]] = set()

    for renderer_rec, slot_index, mat_obj in renderers:
        mesh_rec = _mesh_for_renderer_component(renderer_rec, bundle_index)
        if mesh_rec is None:
            continue
        key_base = (int(getattr(renderer_rec, "path_id", 0) or 0), int(getattr(mesh_rec, "path_id", 0) or 0), int(slot_index))
        if key_base in seen:
            continue
        seen.add(key_base)

        uv_sets = _uv_sets_for_mesh_record(mesh_rec)
        if not uv_sets:
            continue

        mat_rec = mat_obj if getattr(mat_obj, "type_name", "") == "Material" else _resolve_record(bundle_index, mat_obj)
        mat_name = getattr(mat_rec, "name", _pptr_text(mat_obj, bundle_index))
        mat_pid = getattr(mat_rec, "path_id", None)
        slot_names = mat_slot_names.get(int(mat_pid), []) if mat_pid is not None else []
        slot_text = ", ".join(slot_names[:3]) if slot_names else f"material slot {slot_index}"
        go_name = _gameobject_name_for_component(renderer_rec, bundle_index)

        uv_infos: list[dict[str, Any]] = []
        for channel_index in sorted(uv_sets.keys())[:4]:
            bounds = uv_bounds(uv_sets[channel_index])
            if not bounds:
                continue
            region_text = _atlas_region_text(bounds, int(td.width), int(td.height))
            if not region_text:
                continue
            u_text = (
                f"U {bounds['u_min']:.4f}–{bounds['u_max']:.4f}, "
                f"V {bounds['v_min']:.4f}–{bounds['v_max']:.4f}"
            )
            quality = _atlas_region_quality_text(bounds, int(td.width), int(td.height))
            try:
                area = max(0.0, float(bounds.get("u_span", 0.0))) * max(0.0, float(bounds.get("v_span", 0.0)))
            except Exception:
                area = 999.0
            uv_infos.append({
                "channel": channel_index,
                "region_text": region_text,
                "uv_text": f"{u_text}; {quality}" if quality else u_text,
                "quality": quality,
                "area": area,
            })

        if not uv_infos:
            continue

        # Comparison hint only: if multiple UV sets are available, the smallest
        # non-zero rectangle is often the packed atlas patch.  This is not proof
        # that the shader samples this texture with that UV channel.  The shader
        # may use UV0, another channel, world/projected coordinates, or generated
        # data.  All available UV links remain visible for comparison.
        non_zero = [u for u in uv_infos if float(u.get("area", 0.0) or 0.0) > 0.000001]
        likely = min(non_zero or uv_infos, key=lambda u: float(u.get("area", 999.0) or 999.0))
        rows.append({
            "go_name": go_name,
            "renderer_name": getattr(renderer_rec, "name", "Renderer"),
            "mesh_name": getattr(mesh_rec, "name", "Mesh"),
            "mat_name": mat_name,
            "slot_text": slot_text,
            "uv_infos": uv_infos,
            "likely_channel": int(likely.get("channel", 0)),
        })
        if len(rows) >= 48:
            break

    if not rows:
        return []

    uv_link_count = sum(len(r.get("uv_infos", [])) for r in rows)

    lines: list[str] = []
    lines.append("")
    lines.append("🗺 Mesh UV comparison on this texture")
    lines.append("  Important: a Texture2D does not own UV coordinates. UV0/UV1/UV2 belong to each renderer's attached mesh.")
    lines.append("  UBE projects every available mesh UV channel onto this image for comparison; the Material/Shader decides which channel actually samples each texture slot.")
    lines.append("  Conventional _BaseMap/_ColorMap/_MainTex materials commonly use UV0, while UV1+ often hold lightmap or secondary data, but custom shaders can deliberately use something else.")
    lines.append("  A nearly full-size UV1/UV2 box can therefore be a secondary unwrap; it does not mean this colour texture is necessarily sampled with that channel.")
    lines.append("  The 'atlas candidate' marker only identifies the smallest non-zero rectangle. It is a browsing hint, not confirmed shader wiring.")
    lines.append("  Tip: click a row number or an individual UV link to draw that box over the texture preview.")
    lines.append("  Display limit: up to the first 48 renderer/mesh usages are shown for responsiveness. An object's own inspector can show its exact UV bounds even when it is not listed here.")
    lines.append("")
    lines.append(f"🎯 Mesh UV bounds projected onto {td.width}×{td.height} ({len(rows)} renderer rows, {uv_link_count} UV links shown)")
    for i, row in enumerate(rows[:48], 1):
        go_name = row.get("go_name", "Object")
        renderer_name = row.get("renderer_name", "Renderer")
        mesh_name = row.get("mesh_name", "Mesh")
        mat_name = row.get("mat_name", "Material")
        slot_text = row.get("slot_text", "Texture")
        likely_channel = row.get("likely_channel", None)
        lines.append(f"  {i}: {go_name}")
        lines.append(f"     Mesh: {mesh_name}  | Renderer: {renderer_name}")
        lines.append(f"     Material: {mat_name} [{slot_text}]")
        for info in row.get("uv_infos", []):
            channel_index = int(info.get("channel", 0))
            note = "  ← smallest atlas candidate (not confirmed)" if likely_channel == channel_index and len(row.get("uv_infos", [])) > 1 else ""
            lines.append(f"     UV{channel_index}: {info.get('region_text', '')}{note}")
            lines.append(f"       {info.get('uv_text', '')}")
    if len(rows) > 48:
        lines.append(f"  ... {len(rows) - 48} more renderer rows")
    lines.append("")
    lines.append("🧠 How to read these bounds")
    lines.append("Small rectangles are strong atlas clues. Nearly full-image rectangles are often secondary unwraps, repeating/detail coordinates, or generated lightmap-style layouts.")
    lines.append("For normal Unity materials, UV0 is the usual starting point for base colour. Treat UV1/UV2 as additional mesh data unless the shader, preview result, or known asset behaviour shows otherwise.")
    lines.append("The 3D preview is the practical visual check: its status line shows the currently selected UV channel, and U cycles the available channels without changing the underlying asset data.")
    return lines


def _is_near_zero(value: Any, eps: float = 1e-6) -> bool:
    try:
        return abs(float(value)) <= eps
    except Exception:
        return False


def _numeric_components(value: Any) -> list[float] | None:
    parts = []
    for name in ("r", "g", "b", "a"):
        v = _get(value, name, default=None)
        if v is None:
            for alt in (name.upper(),):
                v = _get(value, alt, default=None)
                if v is not None:
                    break
        if v is None:
            # UnityPy may also expose tuple/list-like colours.
            try:
                if isinstance(value, (list, tuple)):
                    return [float(x) for x in value]
            except Exception:
                pass
            return None
        try:
            parts.append(float(v))
        except Exception:
            return None
    return parts


def _is_default_or_empty_colour(value: Any) -> bool:
    comps = _numeric_components(value)
    if not comps:
        return False
    # Treat pure zero/black and default white as non-informative in normal view.
    if all(abs(x) <= 1e-6 for x in comps):
        return True
    if len(comps) >= 4 and all(abs(x - 1.0) <= 1e-6 for x in comps[:4]):
        return True
    if len(comps) >= 4 and all(abs(x) <= 1e-6 for x in comps[:3]) and abs(comps[3] - 1.0) <= 1e-6:
        return True
    return False


def _is_empty_texture_ref(texture: Any, target: str) -> bool:
    pid = _pptr_path_id(texture)
    if pid in (None, 0):
        return True
    if target in ("PathID 0", "PathID None", "-"):
        return True
    return False

def _describe_material(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🎨 Material"]

    if data is None:
        lines.append("Unable to read material data.")
        return lines

    # =====================================================
    # 🧠 STEP 1 — SHADER INTERPRETATION (ENHANCED)
    # =====================================================

    shader = _get(data, "m_Shader", "shader", default=None)

    is_transparent = False
    is_emissive = False

    if shader is not None:
        shader_name = _record_name_from_pptr(shader, bundle_index)
        shader_lower = str(shader_name).lower()

        lines.append(f"⚙ Shader: {shader_name}")

        pid = _pptr_path_id(shader)
        fid = _pptr_file_id(shader)

        refs = []
        if fid is not None:
            refs.append(f"file {fid}")
        if pid is not None:
            refs.append(f"path {pid}")

        if refs:
            lines.append(f"  🔗 Shader ref: {', '.join(refs)}")

        # ✔ MATERIAL CLASSIFICATION (STEP 1 CORE)
        if any(token in shader_lower for token in ("transparent", "glass", "water", "overlay")):
            is_transparent = True
        if "emission" in shader_lower or "emissive" in shader_lower:
            is_emissive = True

        # Shader Graph / URP materials often do not expose a simple _Surface value on the
        # material.  If the referenced Shader is present, read its SubShader tags too so
        # glass shaders such as Amplify/Venice/Venice_Glass are not mislabelled opaque.
        try:
            shader_rec = _resolve_record(bundle_index, shader)
            shader_data = _read(shader_rec) if shader_rec is not None else None
            parsed_shader = _get(shader_data, "m_ParsedForm", "parsed_form", default=None) if shader_data is not None else None
            for sub in _as_list(_get(parsed_shader, "m_SubShaders", "sub_shaders", default=None)):
                tag_text = " ".join(_shader_tag_lines(_get(sub, "m_Tags", "tags", default=None))).lower()
                if "transparent" in tag_text or "queue: transparent" in tag_text or "rendertype: transparent" in tag_text:
                    is_transparent = True
        except Exception:
            pass

    saved = _get(data, "m_SavedProperties", "saved_properties", default=None)

    if saved is None:
        lines.append("Saved properties: -")
        return lines

    tex_envs = _as_list(_get(saved, "m_TexEnvs", "tex_envs", default=None))
    floats = _as_list(_get(saved, "m_Floats", "floats", default=None))
    colors = _as_list(_get(saved, "m_Colors", "colors", default=None))

    float_props = _pairs_to_dict(floats)
    colour_props = _pairs_to_dict(colors)
    base_colour = _get_material_base_color(data)
    # =====================================================
    # 🧠 STEP 4/5 — MATERIAL INSIGHT BLOCK (NEW ADDITION)
    # =====================================================

    lines.append("")
    lines.append("🧠 Material Insight")

    if is_transparent and is_emissive:
        lines.append("• Transparent + Emissive (glass / energy / UI glow)")
    elif is_transparent:
        lines.append("• Transparent / glass-like material (shader queue or name suggests see-through rendering)")
    elif is_emissive:
        lines.append("• Emissive material (glow / lighting / effects)")
    else:
        lines.append("• Opaque material (solid surface)")

    # =====================================================
    # 🧪 RENDERING HINTS (UNCHANGED BUT SAFE)
    # =====================================================

    lines.append("")
    if base_colour:
        r, g, b = base_colour
        lines.append(f"🎨 Base colour (preview): {r:.3f}, {g:.3f}, {b:.3f}")
    lines.append("🧪 Rendering hints")
    lines.append(f"  Surface: {_surface_name(float_props)}")

    for key, value in _property_subset(
        float_props,
        ("_Surface", "_Blend", "_AlphaClip", "_Cutoff", "_ZWrite", "_Cull", "_Metallic", "_Smoothness", "_Glossiness"),
        limit=18
    ):
        lines.append(f"  {friendly_property_name(key)}: {_format_material_value(value)}")

    for key, value in _property_subset(
        colour_props,
        ("_BaseColor", "_Color", "_EmissionColor", "_SpecColor", "_Tint"),
        limit=8
    ):
        lines.append(f"  {friendly_property_name(key)}: {_format_material_value(value)}")

    # =====================================================
    # 🖼 TEXTURE ROLE NORMALISATION (STEP 2)
    # =====================================================

    meaningful_tex_envs = []
    unresolved_base_colour_refs = []

    for item in tex_envs:

        key, value = _pair_key_value(item)

        texture = _get(value, "m_Texture", "texture", default=value)
        target = _record_name_from_pptr(texture, bundle_index)

        if _is_empty_texture_ref(texture, target):
            continue

        meaningful_tex_envs.append((key, value, texture, target))

    if meaningful_tex_envs:

        lines.append("")
        hidden = len(tex_envs) - len(meaningful_tex_envs)
        hidden_note = f", {hidden} empty hidden" if hidden else ""

        lines.append(f"🖼 Texture roles ({len(meaningful_tex_envs)}{hidden_note})")

        for key, value, texture, target in meaningful_tex_envs[:100]:

            pid = _pptr_path_id(texture)
            prop = _clean_prop_name(key)

            # ✔ STEP 2 UPGRADE (texture role label)
            role = material_texture_role(prop)

            suffix = f"  (PathID {pid})" if pid is not None and not target.startswith("PathID") else ""

            lines.append(f"  {role}: {target}  [{friendly_property_name(prop)}]{suffix}")

            if role == "🖼 Base colour" and _resolve_record(bundle_index, texture) is None and pid not in (None, 0):
                unresolved_base_colour_refs.append({
                    "property": prop,
                    "path_id": pid,
                    "file_id": _pptr_file_id(texture),
                    "source": _pptr_external_source_name(texture),
                })

        if len(meaningful_tex_envs) > 100:
            lines.append(f"  ... {len(meaningful_tex_envs) - 100} more texture slots")

    elif tex_envs:
        lines.append("")
        lines.append(f"🖼 Texture roles: none populated ({len(tex_envs)} empty hidden)")
    else:
        lines.append("")
        lines.append("🖼 Texture roles: none found")

    if unresolved_base_colour_refs:
        lines.append("")
        lines.append("⚠ External colour texture not loaded")
        lines.append("  UBE recognised the material's base-colour slot, but its texture is outside the currently loaded/indexed bundle set.")
        for ref in unresolved_base_colour_refs[:8]:
            bits = []
            if ref.get("file_id") not in (None, 0):
                bits.append(f"FileID {ref['file_id']}")
            bits.append(f"PathID {ref['path_id']}")
            source = f" → {ref['source']}" if ref.get("source") else ""
            lines.append(f"  • {ref['property']}: {', '.join(bits)}{source}")
        if len(unresolved_base_colour_refs) > 8:
            lines.append(f"  ... {len(unresolved_base_colour_refs) - 8} more unresolved base-colour references")
        lines.append("  Geometry, UVs, material and animation may still be intact. Open/scan the folder containing the dependency bundle and use the PathID index; UBE will apply the texture when it becomes resolvable.")

    # =====================================================
    # 📊 PROPERTY SUMMARY (UNCHANGED)
    # =====================================================

    lines.append("")
    lines.append("📊 Material property counts")
    lines.append(f"  Texture slots: {len(tex_envs)}")
    lines.append(f"  Float properties: {len(floats)}")
    lines.append(f"  Colour properties: {len(colors)}")

    # =====================================================
    # 🔢 FLOAT FILTERING (STEP 3 BEHAVIOUR PRESERVED)
    # =====================================================

    meaningful_floats = []

    for item in floats:
        key, value = _pair_key_value(item)
        if _is_near_zero(value):
            continue
        meaningful_floats.append((key, value))

    if meaningful_floats:
        lines.append("")
        hidden = len(floats) - len(meaningful_floats)
        hidden_note = f", {hidden} zero hidden" if hidden else ""
        lines.append(f"🔢 Float properties ({len(meaningful_floats)}{hidden_note})")

        for key, value in meaningful_floats[:60]:
            lines.append(f"  {friendly_property_name(key)}: {_format_material_value(value)}")

        if len(meaningful_floats) > 60:
            lines.append(f"  ... {len(meaningful_floats) - 60} more float properties")

    elif floats:
        lines.append("")
        lines.append(f"🔢 Float properties: none significant ({len(floats)} zero/default hidden)")

    # =====================================================
    # 🎨 COLOUR FILTERING (UNCHANGED)
    # =====================================================

    meaningful_colors = []

    for item in colors:
        key, value = _pair_key_value(item)
        if _is_default_or_empty_colour(value):
            continue
        meaningful_colors.append((key, value))

    if meaningful_colors:
        lines.append("")
        hidden = len(colors) - len(meaningful_colors)
        hidden_note = f", {hidden} default hidden" if hidden else ""
        lines.append(f"🎨 Colour properties ({len(meaningful_colors)}{hidden_note})")

        for key, value in meaningful_colors[:40]:
            hex_value = _colour_hex(value)
            hex_suffix = f"  {hex_value}" if hex_value else ""
            lines.append(f"  {friendly_property_name(key)}: {_format_material_value(value)}{hex_suffix}")

        if len(meaningful_colors) > 40:
            lines.append(f"  ... {len(meaningful_colors) - 40} more colour properties")

    elif colors:
        lines.append("")
        lines.append(f"🎨 Colour properties: none significant ({len(colors)} zero/default hidden)")

    motion_clue = _material_motion_clues(record, bundle_index)
    lines.append("")
    lines.append("🎞 Material motion clues")
    if motion_clue is not None:
        categories = ", ".join(motion_clue.get("categories") or ["procedural material motion"])
        lines.append(f"  Likely system: {categories}")
        lines.append(f"  Shader: {motion_clue.get('shader_name') or '-'}")
        prop_hits = [p for p in motion_clue.get("properties", []) if any(t in p.lower() for t in _MOTION_PROPERTY_TOKENS)]
        if prop_hits:
            lines.append("  Motion-related properties:")
            for prop in prop_hits[:24]:
                lines.append(f"    • {prop}")
            if len(prop_hits) > 24:
                lines.append(f"    ... {len(prop_hits) - 24} more")
        lines.append("  This is a heuristic clue: the shader/property names indicate time-, noise-, flow-, wind- or vertex-driven movement without requiring an AnimationClip.")
    else:
        lines.append("  No obvious wind/deformation/flow/time property names were detected.")

    # =====================================================
    # 🔗 RELATIONSHIPS (UNCHANGED)
    # =====================================================

    lines.extend(_relationship_lines(record, bundle_index, asset_graph))

    return lines

def _vec3_text(value: Any) -> str:
    if value is None:
        return "-"
    parts = []
    for name in ("x", "y", "z"):
        v = _get(value, name, default=None)
        if v is None:
            return str(value)
        try:
            parts.append(f"{float(v):.3f}")
        except Exception:
            parts.append(str(v))
    return ", ".join(parts)


def _vec3_double_text(value: Any) -> str:
    """Return the full size from a Unity AABB extent vector."""
    if value is None:
        return "-"
    parts = []
    for name in ("x", "y", "z"):
        v = _get(value, name, default=None)
        if v is None:
            return "-"
        try:
            parts.append(f"{float(v) * 2.0:.3f}")
        except Exception:
            return "-"
    return " × ".join(parts)


_VERTEX_FORMAT_NAMES: dict[int, str] = {
    # Unity's modern VertexAttributeFormat enum. Unknown/legacy values remain
    # visible as raw numbers rather than being guessed incorrectly.
    0: "Float32",
    1: "Float16",
    2: "UNorm8",
    3: "SNorm8",
    4: "UNorm16",
    5: "SNorm16",
    6: "UInt8",
    7: "SInt8",
    8: "UInt16",
    9: "SInt16",
    10: "UInt32",
    11: "SInt32",
}


def _format_vertex_channel(dim: Any, fmt: Any) -> str:
    try:
        d = int(dim)
    except Exception:
        d = None
    try:
        f = int(fmt)
    except Exception:
        f = None
    if not d:
        return "present"
    fmt_name = _VERTEX_FORMAT_NAMES.get(f, f"fmt {fmt}" if fmt is not None else "unknown")
    if fmt_name == "Float32":
        return f"Float{d}"
    return f"{fmt_name} x{d}"


def _channel_summary(channel: Any) -> str:
    dim = _get(channel, "dimension", "m_Dimension", default=None)
    fmt = _get(channel, "format", "m_Format", default=None)
    stream = _get(channel, "stream", "m_Stream", default=None)
    offset = _get(channel, "offset", "m_Offset", default=None)
    parts = []
    if dim not in (None, 0):
        parts.append(_format_vertex_channel(dim, fmt))
    elif fmt not in (None, 0):
        parts.append(f"fmt {fmt}")
    if stream is not None:
        parts.append(f"stream {stream}")
    if offset is not None:
        parts.append(f"offset {offset}")
    return ", ".join(parts) if parts else "present"




def _uv_grid_hint_from_region(region: dict[str, Any] | None, cell_px: int = 128) -> str:
    """Return a compact atlas-grid hint for UV regions.

    The golf-ball atlas is a good example: many designs appear to use a
    128-pixel row height, but some designs span multiple cells horizontally.
    This intentionally reports variable-width regions rather than forcing a
    square tile assumption.
    """
    if not region:
        return ""
    try:
        x = int(region.get("x", 0))
        y = int(region.get("y", 0))
        w = int(region.get("w", 0))
        h = int(region.get("h", 0))
    except Exception:
        return ""
    if w <= 0 or h <= 0:
        return ""

    def near_int(value: float, tolerance: float = 0.15) -> int | None:
        rounded = round(value)
        if rounded <= 0:
            return None
        return int(rounded) if abs(value - rounded) <= tolerance else None

    cols = near_int(w / float(cell_px))
    rows = near_int(h / float(cell_px))
    col0 = round(x / float(cell_px))
    row0 = round(y / float(cell_px))
    parts: list[str] = []
    if cols and rows:
        parts.append(f"≈ {cols}×{rows} cells of {cell_px}px")
        parts.append(f"cell {col0}, {row0}")
    elif rows:
        parts.append(f"≈ {rows} row(s) high on {cell_px}px grid")
    elif cols:
        parts.append(f"≈ {cols} column(s) wide on {cell_px}px grid")
    return "; ".join(parts)


def _atlas_region_text(bounds: dict[str, float], width: int, height: int) -> str:
    try:
        from ..exporters.mesh_exporter import atlas_region_from_uv_bounds
    except Exception:
        return ""
    try:
        region = atlas_region_from_uv_bounds(bounds, int(width), int(height))
    except Exception:
        return ""
    if not region:
        return ""
    hint = _uv_grid_hint_from_region(region, 128)
    text = f"x {region['x']}–{region['x'] + region['w']}, y {region['y']}–{region['y'] + region['h']} ({region['w']}×{region['h']} px)"
    return f"{text}; {hint}" if hint else text


def _uv_sets_for_mesh_record(mesh_rec: Any) -> dict[int, list[tuple[float, float]]]:
    data = _read(mesh_rec)
    if data is None:
        return {}
    try:
        from ..exporters.mesh_exporter import mesh_uv_channels_from_record, obj_uv_bounds
        uv_sets = mesh_uv_channels_from_record(mesh_rec)
    except Exception:
        uv_sets = {}

    # Conservative fallback: UnityPy's OBJ exporter often exposes UV0 even when
    # raw channel extraction is unavailable in this Python/UnityPy version.
    # Build 155 fix: data.export() can return str, bytes, or a small export object.
    # The old code assumed bytes and called .decode(), so the object-level atlas
    # insight silently disappeared for some meshes such as the golf balls.
    if not uv_sets:
        try:
            obj_text = None
            exp = getattr(data, "export", None)
            result = exp() if callable(exp) else None
            if isinstance(result, bytes):
                obj_text = result.decode("utf-8", errors="replace")
            elif isinstance(result, str):
                obj_text = result
            else:
                for attr in ("obj", "text", "data"):
                    value = getattr(result, attr, None)
                    if isinstance(value, bytes):
                        obj_text = value.decode("utf-8", errors="replace")
                        break
                    if isinstance(value, str):
                        obj_text = value
                        break
            if obj_text:
                bounds = obj_uv_bounds(obj_text)
                if bounds:
                    # Reconstruct only enough points for bounds reporting.  The real
                    # OBJ export still contains the real UVs; this is just inspector text.
                    uv_sets[0] = [
                        (bounds["u_min"], bounds["v_min"]),
                        (bounds["u_max"], bounds["v_max"]),
                    ]
        except Exception:
            pass
    return uv_sets


def _texture_dimensions_for_record(tex_rec: Any) -> tuple[int, int] | None:
    if tex_rec is None:
        return None
    data = _read(tex_rec)
    if data is None:
        return None
    for w_name, h_name in (("m_Width", "m_Height"), ("width", "height")):
        w = _get(data, w_name, default=None)
        h = _get(data, h_name, default=None)
        try:
            if int(w) > 0 and int(h) > 0:
                return int(w), int(h)
        except Exception:
            pass
    return None


def _material_texture_candidates_for_atlas(materials: list[Any], bundle_index: Any | None) -> list[tuple[str, str, Any, tuple[int, int] | None]]:
    rows: list[tuple[str, str, Any, tuple[int, int] | None]] = []
    seen: set[int] = set()
    for mat in materials:
        mat_rec = _resolve_record(bundle_index, mat)
        data = _read(mat_rec) if mat_rec is not None else None
        if data is None:
            continue
        saved = _get(data, "m_SavedProperties", "saved_properties", default=None)
        tex_envs = _as_list(_get(saved, "m_TexEnvs", "tex_envs", default=None)) if saved is not None else []
        for item in tex_envs:
            key, value = _pair_key_value(item)
            key_text = _clean_prop_name(key) or "Texture"
            texture = _get(value, "m_Texture", "texture", default=value)
            tex_rec = _resolve_record(bundle_index, texture)
            if tex_rec is None or getattr(tex_rec, "type_name", "") not in ("Texture2D", "Texture2DArray"):
                continue
            pid = getattr(tex_rec, "path_id", None)
            if pid in seen:
                continue
            seen.add(pid)
            name = getattr(tex_rec, "name", "Texture")
            dims = _texture_dimensions_for_record(tex_rec)
            rows.append((key_text, name, tex_rec, dims))
    return rows


def _describe_mesh_uv_atlas(record: Any) -> list[str]:
    """Small educational UV summary for atlas-heavy assets such as golf balls."""
    try:
        from ..exporters.mesh_exporter import uv_bounds
    except Exception:
        return []
    uv_sets = _uv_sets_for_mesh_record(record)
    if not uv_sets:
        return []

    lines: list[str] = ["", "🗺 UV / atlas insight"]
    for channel_index in sorted(uv_sets.keys())[:4]:
        bounds = uv_bounds(uv_sets[channel_index])
        if not bounds:
            continue
        u_span = bounds["u_span"]
        v_span = bounds["v_span"]
        lines.append(
            f"  UV{channel_index}: U {bounds['u_min']:.6f} → {bounds['u_max']:.6f} "
            f"(span {u_span:.6f}), V {bounds['v_min']:.6f} → {bounds['v_max']:.6f} "
            f"(span {v_span:.6f}), {int(bounds['count'])} coords"
        )

        # Common atlas hint for Walkabout golf balls and similar shared atlases.
        # This now supports variable-width tiles such as 256×128 or 512×128.
        region_text = _atlas_region_text(bounds, 2048, 2048)
        if region_text:
            lines.append(f"    On a 2048×2048 atlas: {region_text}")

    if len(lines) == 2:
        return []
    lines.append("  Tip: for shared atlases, the material may be identical and the mesh UV rectangle selects the design.")
    return lines


def _describe_attached_mesh_atlas(mesh_rec: Any | None, material_pptrs: list[Any], bundle_index: Any | None, indent: str = "  ") -> list[str]:
    """Show UV/atlas information for an Object's attached mesh.

    This is the object-level version of the mesh UV insight.  It is especially
    useful for golf balls: hundreds of objects share Ball_Material and the same
    BallsTexture atlas, while each BallXXX mesh selects a different atlas region
    through its UVs.
    """
    if mesh_rec is None:
        return []
    try:
        from ..exporters.mesh_exporter import uv_bounds
    except Exception:
        return []
    uv_sets = _uv_sets_for_mesh_record(mesh_rec)
    if not uv_sets:
        return []

    texture_rows = _material_texture_candidates_for_atlas(material_pptrs, bundle_index)
    # Prefer base/ball texture first, but keep emission/normal visible because
    # they usually share the same UV rectangle.
    def tex_score(row: tuple[str, str, Any, tuple[int, int] | None]) -> int:
        key, name, _rec, _dims = row
        text = f"{key} {name}".lower()
        if "ballstexture" in text and "normal" not in text and "emis" not in text and "metal" not in text:
            return 0
        if "base" in text or "maintex" in text or "albedo" in text:
            return 1
        if "emis" in text or "emission" in text:
            return 2
        if "normal" in text or "bump" in text:
            return 3
        return 4
    texture_rows = sorted(texture_rows, key=tex_score)

    lines: list[str] = [
        f"{indent}Mesh UV channels projected onto referenced textures:",
        f"{indent}  UV coordinates belong to this Mesh, not to the Material or Texture2D.",
        f"{indent}  UBE shows every available UV channel against each referenced texture for comparison; the Shader decides the real texture/channel pairing.",
        f"{indent}  For a conventional _BaseMap/_ColorMap/_MainTex slot, UV0 is the usual starting assumption, but custom shaders and known exceptions may use another channel.",
    ]
    for channel_index in sorted(uv_sets.keys())[:4]:
        bounds = uv_bounds(uv_sets[channel_index])
        if not bounds:
            continue
        lines.append(
            f"{indent}  UV{channel_index}: U {bounds['u_min']:.6f} → {bounds['u_max']:.6f} "
            f"(span {bounds['u_span']:.6f}), V {bounds['v_min']:.6f} → {bounds['v_max']:.6f} "
            f"(span {bounds['v_span']:.6f})"
        )
        for key_text, tex_name, tex_rec, dims in texture_rows[:4]:
            if not dims:
                continue
            region_text = _atlas_region_text(bounds, dims[0], dims[1])
            if region_text:
                lines.append(f"{indent}    {tex_name} [{key_text}] ({dims[0]}×{dims[1]}): {region_text}")

    if len(lines) == 4:
        return []
    if not texture_rows:
        lines.append(f"{indent}  No attached texture dimensions found, so only raw UV bounds are shown.")
    else:
        lines.append(f"{indent}  Reading tip: a full-size UV1/UV2 rectangle is often secondary mesh data; it does not override a compact UV0 base-colour atlas patch by itself.")
        lines.append(f"{indent}  The 3D preview status line shows which UV channel UBE is currently displaying; press U to compare channels.")
    return lines

def _describe_mesh(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧊 Mesh"]
    if data is None:
        lines.append("Unable to read mesh data.")
        return lines

    vertex_count = _get(data, "m_VertexCount", "vertex_count", default=None)
    submeshes = _get(data, "m_SubMeshes", "sub_meshes", default=None)
    submesh_count = len(submeshes) if isinstance(submeshes, list) else (submeshes if submeshes is not None else "-")
    lines.append(f"🔺 Vertices: {vertex_count if vertex_count is not None else 'Not available'}")
    lines.append(f"🧩 Submeshes: {submesh_count}")

    # Index/triangle estimate from submesh index counts. Topology 0 is triangles in Unity.
    total_indices = 0
    triangle_estimate = None
    if isinstance(submeshes, list):
        for sm in submeshes:
            ic = _get(sm, "indexCount", "m_IndexCount", default=None)
            try:
                total_indices += int(ic or 0)
            except Exception:
                pass
        if total_indices:
            triangle_estimate = total_indices // 3
            lines.append(f"🔻 Indices: {total_indices:,}")
            lines.append(f"🔻 Triangles estimate: {triangle_estimate:,}")

    # Bounds / local AABB where available.
    bounds = _get(data, "m_LocalAABB", "local_aabb", default=None)
    if bounds is not None:
        center = _get(bounds, "m_Center", "center", default=None)
        extent = _get(bounds, "m_Extent", "extent", default=None)
        lines.append("")
        lines.append("📐 Bounds")
        lines.append(f"  Center: {_vec3_text(center)}")
        lines.append(f"  Extent: {_vec3_text(extent)}")
        lines.append(f"  Size: {_vec3_double_text(extent)}")

    # Vertex channel information gives us an early visual of what data the mesh carries.
    vdata = _get(data, "m_VertexData", "vertex_data", default=None)
    channels = _as_list(_get(vdata, "m_Channels", "channels", default=None)) if vdata is not None else []
    active_channels = []
    for idx, ch in enumerate(channels):
        dim = _get(ch, "dimension", "m_Dimension", default=None)
        if dim not in (None, 0):
            active_channels.append((idx, ch))
    if active_channels:
        lines.append("")
        lines.append(f"📊 Vertex channels ({len(active_channels)})")
        # Common Unity channel order varies by version, but these labels are a helpful guide.
        channel_names = {
            0: "Position", 1: "Normal", 2: "Tangent", 3: "Colour",
            4: "UV0", 5: "UV1", 6: "UV2", 7: "UV3",
            12: "Blend weights", 13: "Blend indices",
        }
        for idx, ch in active_channels[:16]:
            label = channel_names.get(idx, f"Channel {idx}")
            lines.append(f"  {label}: {_channel_summary(ch)}")
        if len(active_channels) > 16:
            lines.append(f"  ... {len(active_channels) - 16} more channels")

        # Unity can omit BlendWeight for rigid-per-vertex skinning.  A single
        # BlendIndices value then selects the only controlling bone and carries
        # an implicit full weight.  Expose this unusual but valid layout so a
        # static-looking animated part is diagnosable directly from the Mesh.
        try:
            weight_dim = int(_get(channels[12], "dimension", "m_Dimension", default=0) or 0) if len(channels) > 12 else 0
            index_dim = int(_get(channels[13], "dimension", "m_Dimension", default=0) or 0) if len(channels) > 13 else 0
            bind_pose_count = len(_as_list(_get(data, "m_BindPose", "bindPose", "bind_poses", default=None)))
            if weight_dim <= 0 and index_dim == 1 and bind_pose_count > 0:
                lines.append(f"  🦴 Skinning layout: rigid index-only; one bone index per vertex, implicit weight 1.0 ({bind_pose_count} bind poses)")
        except Exception:
            pass

    lines.extend(_describe_mesh_uv_atlas(record))

    # Raw Mesh assets can be reused by many renderers with different materials.
    # Show likely renderer contexts so users understand why clicking the owning
    # GameObject can preview/export with a better texture than the raw Mesh alone.
    try:
        from ..exporters.mesh_exporter import (
            best_renderer_context_for_mesh,
            mesh_renderer_context_candidates,
        )
        contexts = mesh_renderer_context_candidates(record, bundle_index, asset_graph, limit=6) if bundle_index is not None else []
        best_renderer_context = best_renderer_context_for_mesh(record, bundle_index, asset_graph, min_score=60) if bundle_index is not None else None
    except Exception:
        contexts = []
    if contexts:
        lines.append("")
        lines.append("🎯 Renderer / material contexts")
        lines.append(f"  This raw Mesh is used by {len(contexts)} likely renderer context(s) shown here.")
        lines.append("  A Mesh stores geometry/UVs; the GameObject/Renderer supplies the final Material and Texture.")
        lines.append("  Texture2D assets are the image files referenced by a Material; they are not the Material itself.")
        def _ctx_extra_lines(ctx: dict[str, Any]) -> list[str]:
            extras: list[str] = []
            seen_shaders: list[str] = []
            for x in (ctx.get("shader_names") or []):
                sx = str(x)
                if sx and sx not in seen_shaders:
                    seen_shaders.append(sx)
            shaders = ", ".join(seen_shaders) or "-"
            if shaders != "-":
                extras.append(f"     Shader/ref: {shaders}")
            flat_colours: list[str] = []
            for group in (ctx.get("colour_summaries") or []):
                for item in (group or []):
                    item = str(item)
                    if item not in flat_colours:
                        flat_colours.append(item)
            if flat_colours:
                extras.append("     Colours: " + "; ".join(flat_colours[:4]))
            flat_floats: list[str] = []
            for group in (ctx.get("float_summaries") or []):
                for item in (group or []):
                    item = str(item)
                    if item not in flat_floats:
                        flat_floats.append(item)
            if flat_floats:
                extras.append("     Key floats: " + "; ".join(flat_floats[:8]))
            return extras

        for i, ctx in enumerate(contexts[:6], 1):
            obj = ctx.get("object_record") or ctx.get("context_record")
            renderer = ctx.get("renderer_record")
            mats = ", ".join(ctx.get("material_names") or []) or "-"
            texs = ", ".join((ctx.get("texture_names") or [])[:3]) or "-"
            kind = ctx.get("kind", "")
            if kind == "semantic_material":
                lines.append(f"  {i}: Material/texture name match  | score {ctx.get('score', 0)}")
                lines.append(f"     Materials: {mats}")
                lines.append(f"     Texture2D assets: {texs}")
                lines.extend(_ctx_extra_lines(ctx))
                if texs == "-":
                    lines.append("     Note: material-name match only; no Texture2D slot was resolved from this Material.")
                lines.append(f"     Reason: {ctx.get('reason', '')}")
            elif kind == "mesh_texture_intersection":
                if ctx.get("authoritative_base_texture"):
                    signal = "exact renderer base-colour texture"
                else:
                    signal = "exact mesh+texture match" if ctx.get("material_signal") else "exact mesh renderer, auxiliary/weak texture"
                tex_ids = ", ".join(str(x) for x in (ctx.get("texture_path_ids") or []) if x is not None) or "-"
                prop = ctx.get("property") or "-"
                usage = str(ctx.get("texture_usage") or "").lower()
                prop_display = f"{prop} ({usage})" if usage else prop
                lines.append(
                    f"  {i}: {getattr(obj, 'name', '-')}  | Renderer: {getattr(renderer, 'name', '-')}  "
                    f"| score {ctx.get('score', 0)} ({signal})"
                )
                lines.append(f"     Materials: {mats}")
                lines.append(f"     Texture2D assets: {texs}  | PathID(s): {tex_ids}  | Property/slot: {prop_display}")
                scales = ctx.get("texture_scales") or []
                offsets = ctx.get("texture_offsets") or []
                if scales or offsets:
                    try:
                        sc = scales[0] if scales else (1.0, 1.0)
                        of = offsets[0] if offsets else (0.0, 0.0)
                        lines.append(f"     Texture UV transform: scale {float(sc[0]):.6g}, {float(sc[1]):.6g}; offset {float(of[0]):.6g}, {float(of[1]):.6g}")
                    except Exception:
                        pass
                lines.extend(_ctx_extra_lines(ctx))
                lines.append(f"     Reason: {ctx.get('reason', '')}")
            else:
                if kind == "collider_renderer":
                    signal = "MeshCollider/source mesh + renderer material"
                else:
                    signal = "material signal" if ctx.get("material_signal") else "object-name only"
                lines.append(
                    f"  {i}: {getattr(obj, 'name', '-')}  | Renderer: {getattr(renderer, 'name', '-')}  "
                    f"| score {ctx.get('score', 0)} ({signal})"
                )
                lines.append(f"     Materials: {mats}")
                lines.append(f"     Texture2D assets: {texs}")
                if kind == "collider_renderer":
                    lines.append("     Bridge: selected Mesh is used by MeshCollider; same GameObject renderer supplies these materials.")
                lines.extend(_ctx_extra_lines(ctx))
        # Keep the inspector statement aligned with the exact function used by
        # raw-Mesh preview and export.
        best_auto = best_renderer_context
        if best_auto is not None:
            if best_auto.get("kind") == "semantic_material":
                lines.append(
                    "  Auto preview/export: UBE will prefer the material/texture-name match "
                    f"({', '.join(best_auto.get('material_names') or [])}) for this raw Mesh."
                )
            elif best_auto.get("kind") == "mesh_texture_intersection":
                if best_auto.get("authoritative_base_texture"):
                    lines.append(
                        "  Auto preview/export: UBE will trust the exact renderer's base-colour assignment "
                        f"({', '.join(best_auto.get('material_names') or [])} → "
                        f"{', '.join(best_auto.get('texture_names') or [])}) for this raw Mesh."
                    )
                else:
                    lines.append(
                        "  Auto preview/export: UBE will prefer the exact Mesh→Renderer→Material→Texture match "
                        f"({', '.join(best_auto.get('texture_names') or [])}) for this raw Mesh."
                    )
            else:
                best_obj = best_auto.get("object_record") or best_auto.get("context_record")
                lines.append(
                    f"  Auto preview/export: UBE will prefer '{getattr(best_obj, 'name', '-')}' "
                    "as the renderer context for this raw Mesh."
                )
        elif contexts:
            top = contexts[0]
            if top.get("kind") == "semantic_material" and not (top.get("texture_names") or []):
                lines.append(
                    "  Auto preview/export: top match is material-name only but no Texture2D was resolved, "
                    "so UBE keeps raw Mesh preview/export conservative."
                )
            else:
                lines.append("  Auto preview/export: no confident material/texture context; raw Mesh preview stays conservative.")

    if isinstance(submeshes, list) and submeshes:
        lines.append("")
        lines.append("🧩 Submesh details")
        for i, sm in enumerate(submeshes[:20]):
            ic = _get(sm, "indexCount", "m_IndexCount", default=None)
            vc = _get(sm, "vertexCount", "m_VertexCount", default=None)
            topo = _get(sm, "topology", "m_Topology", default=None)
            tri = ""
            try:
                if ic is not None:
                    tri = f", ~{int(ic)//3:,} tris"
            except Exception:
                pass
            lines.append(f"  #{i}: indices {ic if ic is not None else '-'}{tri}, vertices {vc if vc is not None else '-'}, topology {topo if topo is not None else '-'}")
        if len(submeshes) > 20:
            lines.append(f"  ... {len(submeshes) - 20} more submeshes")

    shapes = _get(data, "m_Shapes", "shapes", default=None)
    if shapes is not None:
        lines.append(f"🎭 Blend shape data: {'present' if shapes else '-'}")
    bind_pose = _get(data, "m_BindPose", "bind_pose", default=None)
    if bind_pose is not None:
        lines.append(f"🦴 Bind poses: {len(bind_pose) if isinstance(bind_pose, list) else 'present'}")
    return lines




# =====================================================
# Shader inspector helpers
# =====================================================

SHADER_PROPERTY_TYPE_NAMES: dict[int, str] = {
    0: "Color",
    1: "Vector",
    2: "Float",
    3: "Range",
    4: "Texture",
    5: "Int",
}

TEXTURE_DIMENSION_NAMES: dict[int, str] = {
    -1: "Unknown",
    0: "None",
    1: "Any",
    2: "Texture2D",
    3: "Texture3D",
    4: "Cube",
    5: "Texture2DArray",
    6: "CubeArray",
    7: "Texture2DMS",
    8: "Texture2DMSArray",
}

# UnityPy exposes a compact program mask. In these bundles a value of 6
# corresponds to the normal vertex+fragment pair, so keep the labels practical.
SHADER_PROGRAM_MASK_HINTS: dict[int, str] = {
    2: "Vertex",
    4: "Fragment",
    8: "Geometry",
    16: "Hull",
    32: "Domain",
    64: "Ray tracing",
}


def _safe_len(value: Any) -> int | None:
    try:
        return len(value)
    except Exception:
        return None


def _flatten_numbers(value: Any) -> list[int]:
    out: list[int] = []
    if value is None:
        return out
    if isinstance(value, (list, tuple)):
        for item in value:
            out.extend(_flatten_numbers(item))
        return out
    try:
        out.append(int(value))
    except Exception:
        pass
    return out


def _shader_property_type_name(value: Any) -> str:
    try:
        iv = int(value)
        return SHADER_PROPERTY_TYPE_NAMES.get(iv, f"Unknown ({iv})")
    except Exception:
        return str(value) if value is not None else "-"


def _texture_dimension_name(value: Any) -> str:
    try:
        iv = int(value)
        return TEXTURE_DIMENSION_NAMES.get(iv, f"Dim {iv}")
    except Exception:
        return str(value) if value is not None else "-"


def _shader_program_mask_text(value: Any) -> str:
    try:
        mask = int(value)
    except Exception:
        return str(value) if value is not None else "-"
    parts = [name for bit, name in SHADER_PROGRAM_MASK_HINTS.items() if mask & bit]
    return f"{mask} ({', '.join(parts)})" if parts else str(mask)


def _shader_default_values(prop: Any) -> str:
    vals: list[float] = []
    for name in ("m_DefValue_0_", "m_DefValue_1_", "m_DefValue_2_", "m_DefValue_3_"):
        v = _get(prop, name, default=None)
        if v is None:
            continue
        try:
            vals.append(float(v))
        except Exception:
            return str(v)
    if not vals:
        return "-"
    # Keep this compact but useful.
    return ", ".join(f"{v:.4g}" for v in vals)


def _shader_texture_default(prop: Any) -> str:
    tex = _get(prop, "m_DefTexture", "def_texture", default=None)
    if tex is None:
        return "-"
    default_name = _get(tex, "m_DefaultName", "default_name", default="") or ""
    dim = _get(tex, "m_TexDim", "tex_dim", default=None)
    dim_text = _texture_dimension_name(dim)
    if default_name:
        return f"{default_name}, {dim_text}"
    return dim_text


def _shader_name(data: Any, record: Any) -> str:
    parsed = _get(data, "m_ParsedForm", "parsed_form", default=None)
    parsed_name = _get(parsed, "m_Name", "name", default="") if parsed is not None else ""
    direct_name = _get(data, "m_Name", "name", default="") or ""
    if parsed_name:
        return str(parsed_name)
    if direct_name:
        return str(direct_name)
    return record.name


def _shader_guid_text(guid: Any) -> str:
    if guid is None:
        return "-"
    # UnityPy GUID generated structs vary, so show the compact repr if no common raw form exists.
    for attr in ("data", "bytes", "hex"):
        value = _get(guid, attr, default=None)
        if value:
            return str(value)
    return str(guid)


def _shader_tag_lines(tag_map: Any, indent: str = "  ") -> list[str]:
    tags = _get(tag_map, "tags", "m_Tags", default=None)
    if not tags:
        return []
    lines: list[str] = []
    for item in list(tags)[:20]:
        key, value = _pair_key_value(item)
        if key is None and value is None:
            lines.append(f"{indent}{item}")
        else:
            lines.append(f"{indent}{key}: {value}")
    if _safe_len(tags) and _safe_len(tags) > 20:
        lines.append(f"{indent}... {_safe_len(tags) - 20} more tags")
    return lines


def _shader_constant_buffer_summary(program: Any) -> list[str]:
    params = _get(program, "m_CommonParameters", "common_parameters", default=None)
    if params is None:
        return []
    out: list[str] = []
    for label, attr in (
        ("constant buffers", "m_ConstantBuffers"),
        ("textures", "m_TextureParams"),
        ("samplers", "m_Samplers"),
        ("vectors", "m_VectorParams"),
        ("matrices", "m_MatrixParams"),
        ("buffers", "m_BufferParams"),
        ("UAVs", "m_UAVParams"),
    ):
        value = _get(params, attr, attr[2:].lower(), default=None)
        n = _safe_len(value)
        if n:
            out.append(f"{label}: {n}")
    return out


def _describe_shader(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["⚙ Shader"]
    if data is None:
        lines.append("Unable to read shader data.")
        return lines

    parsed = _get(data, "m_ParsedForm", "parsed_form", default=None)
    shader_name = _shader_name(data, record)
    lines.append(f"🏷 Shader name: {shader_name}")

    custom_editor = _get(parsed, "m_CustomEditorName", "custom_editor_name", default="") if parsed is not None else ""
    fallback = _get(parsed, "m_FallbackName", "fallback_name", default="") if parsed is not None else ""
    baked = _get(data, "m_ShaderIsBaked", "shader_is_baked", default=None)
    local_id = _get(data, "m_AssetLocalIdentifierInFile", "asset_local_identifier_in_file", default=None)
    guid = _get(data, "m_AssetGUID", "asset_guid", default=None)

    lines.append(f"🧩 Parsed form: {'yes' if parsed is not None else 'no'}")
    if custom_editor:
        lines.append(f"🛠 Custom editor: {custom_editor}")
    if fallback:
        lines.append(f"🧯 Fallback: {fallback}")
    if baked is not None:
        lines.append(f"📦 Baked / compiled in bundle: {baked}")
    if local_id is not None:
        lines.append(f"# Local shader asset id: {local_id}")
    if guid is not None:
        lines.append(f"🔑 Asset GUID: {_shader_guid_text(guid)}")

    platforms = _get(data, "platforms", "m_Platforms", default=None)
    stage_counts = _get(data, "stageCounts", "m_StageCounts", default=None)
    compressed_lengths = _flatten_numbers(_get(data, "compressedLengths", "m_CompressedLengths", default=None))
    decompressed_lengths = _flatten_numbers(_get(data, "decompressedLengths", "m_DecompressedLengths", default=None))
    compressed_blob = _get(data, "compressedBlob", "m_CompressedBlob", default=None)

    lines.append("")
    lines.append("💾 Compiled data")
    if platforms is not None:
        lines.append(f"  Platforms: {', '.join(str(x) for x in _as_list(platforms)) or platforms}")
    if stage_counts is not None:
        lines.append(f"  Stage counts: {', '.join(str(x) for x in _as_list(stage_counts)) or stage_counts}")
    if compressed_lengths:
        lines.append(f"  Compressed program size: {human_bytes(sum(compressed_lengths))}")
    elif compressed_blob is not None:
        n = _safe_len(compressed_blob)
        lines.append(f"  Compressed blob size: {human_bytes(n) if n is not None else '-'}")
    if decompressed_lengths:
        lines.append(f"  Decompressed program size: {human_bytes(sum(decompressed_lengths))}")

    dependencies = _as_list(_get(data, "m_Dependencies", "dependencies", default=None))
    if dependencies:
        lines.append("")
        lines.append(f"🔗 Shader dependencies ({len(dependencies)})")
        for dep in dependencies[:40]:
            pid = _pptr_path_id(dep)
            fid = _pptr_file_id(dep)
            lines.append(f"  file {fid if fid is not None else '-'}, PathID {pid if pid is not None else '-'}")
        if len(dependencies) > 40:
            lines.append(f"  ... {len(dependencies) - 40} more dependencies")

    props = []
    if parsed is not None:
        prop_info = _get(parsed, "m_PropInfo", "prop_info", default=None)
        props = _as_list(_get(prop_info, "m_Props", "props", default=None)) if prop_info is not None else []

    if props:
        texture_props = []
        color_props = []
        numeric_props = []
        toggles = []
        keyword_enums = []
        texture_arrays = []
        for prop in props:
            ptype = _get(prop, "m_Type", "type", default=None)
            ptype_name = _shader_property_type_name(ptype)
            attrs = _as_list(_get(prop, "m_Attributes", "attributes", default=None))
            tex = _get(prop, "m_DefTexture", "def_texture", default=None)
            tex_dim = _get(tex, "m_TexDim", "tex_dim", default=None) if tex is not None else None
            if ptype_name == "Texture":
                texture_props.append(prop)
                try:
                    if int(tex_dim) == 5 and not str(_get(prop, "m_Name", default="")).startswith("unity_"):
                        texture_arrays.append(prop)
                except Exception:
                    pass
            elif ptype_name == "Color":
                color_props.append(prop)
            elif ptype_name in ("Float", "Range", "Vector", "Int"):
                numeric_props.append(prop)
            if any("Toggle" in str(a) for a in attrs):
                toggles.append(prop)
            if any("KeywordEnum" in str(a) for a in attrs):
                keyword_enums.append(prop)

        lines.append("")
        lines.append("📊 Shader property summary")
        lines.append(f"  Total properties: {len(props)}")
        lines.append(f"  Textures: {len(texture_props)}")
        lines.append(f"  Colours: {len(color_props)}")
        lines.append(f"  Numeric/vector: {len(numeric_props)}")
        lines.append(f"  Toggles: {len(toggles)}")
        lines.append(f"  Keyword enums: {len(keyword_enums)}")
        if texture_arrays:
            lines.append(f"  Texture2DArray slots: {', '.join(_get(p, 'm_Name', default='?') for p in texture_arrays)}")

        lines.append("")
        lines.append("🧾 Shader properties")
        for prop in props[:80]:
            name = _get(prop, "m_Name", "name", default="") or "-"
            desc = _get(prop, "m_Description", "description", default="") or ""
            ptype = _shader_property_type_name(_get(prop, "m_Type", "type", default=None))
            default_values = _shader_default_values(prop)
            attrs = _as_list(_get(prop, "m_Attributes", "attributes", default=None))
            extra_parts = []
            if ptype == "Texture":
                extra_parts.append(f"default texture: {_shader_texture_default(prop)}")
            else:
                extra_parts.append(f"default: {default_values}")
            if attrs:
                extra_parts.append("attrs: " + "; ".join(str(a) for a in attrs[:4]))
            desc_text = f" — {desc}" if desc else ""
            lines.append(f"  {name}{desc_text} [{ptype}; {', '.join(extra_parts)}]")
        if len(props) > 80:
            lines.append(f"  ... {len(props) - 80} more properties")
    else:
        lines.append("")
        lines.append("🧾 Shader properties: none exposed")

    subshaders = _as_list(_get(parsed, "m_SubShaders", "sub_shaders", default=None)) if parsed is not None else []
    if subshaders:
        lines.append("")
        lines.append(f"🎛 SubShaders ({len(subshaders)})")
        for si, sub in enumerate(subshaders[:8]):
            lod = _get(sub, "m_LOD", "lod", default=None)
            passes = _as_list(_get(sub, "m_Passes", "passes", default=None))
            lines.append(f"  SubShader {si}: LOD {lod if lod is not None else '-'}, passes {len(passes)}")
            tag_lines = _shader_tag_lines(_get(sub, "m_Tags", "tags", default=None), indent="    ")
            if tag_lines:
                lines.append("    Tags:")
                lines.extend(tag_lines)
            for pi, pas in enumerate(passes[:12]):
                pname = _get(pas, "m_Name", "name", default="") or "<unnamed>"
                ptype = _get(pas, "m_Type", "type", default=None)
                mask = _shader_program_mask_text(_get(pas, "m_ProgramMask", "program_mask", default=None))
                inst = _get(pas, "m_HasInstancingVariant", "has_instancing_variant", default=None)
                proc_inst = _get(pas, "m_HasProceduralInstancingVariant", "has_procedural_instancing_variant", default=None)
                name_indices = _as_list(_get(pas, "m_NameIndices", "name_indices", default=None))
                lines.append(f"    Pass {pi}: {pname}, type {ptype if ptype is not None else '-'}, program mask {mask}, instancing {inst}, procedural {proc_inst}")
                if name_indices:
                    names = []
                    for item in name_indices[:18]:
                        key, value = _pair_key_value(item)
                        names.append(str(key if key is not None else item))
                    lines.append(f"      Name indices: {', '.join(names)}" + (f" ... +{len(name_indices)-18}" if len(name_indices) > 18 else ""))
                stage_summaries = []
                for stage_label, attr in (("vertex", "progVertex"), ("fragment", "progFragment"), ("geometry", "progGeometry"), ("hull", "progHull"), ("domain", "progDomain")):
                    program = _get(pas, attr, default=None)
                    summary = _shader_constant_buffer_summary(program)
                    if summary:
                        stage_summaries.append(f"{stage_label}: " + ", ".join(summary))
                for summary in stage_summaries[:4]:
                    lines.append(f"      {summary}")
            if len(passes) > 12:
                lines.append(f"    ... {len(passes) - 12} more passes")
        if len(subshaders) > 8:
            lines.append(f"  ... {len(subshaders) - 8} more subshaders")

    # A compact interpretation block; this is deliberately heuristic and helpful rather than pretending to decompile the shader.
    prop_names = {str(_get(p, "m_Name", default="")) for p in props}
    lower_name = shader_name.lower()
    hints: list[str] = []
    if any(n in prop_names for n in ("_BaseMap", "_ColorMap", "_ColourMap", "_BaseColorMap", "_MainTex", "_MainTexture", "_Albedo", "_BaseTex", "_Texture")):
        hints.append("uses one or more base colour texture inputs")
    if "_TextureIndex" in prop_names or any("textureindex" in n.lower() for n in prop_names):
        hints.append("has an index-style property for choosing a texture/slice")
    if any("caustic" in n.lower() for n in prop_names) or "caustic" in lower_name:
        hints.append("contains Atlantis caustics / water-light behaviour")
    if any("flap" in n.lower() for n in prop_names):
        hints.append("contains fish/creature flap animation parameters")
    if any("biolum" in n.lower() or "emis" in n.lower() or "emission" in n.lower() for n in prop_names):
        hints.append("contains glow/emission controls")
    if any("boost" in n.lower() for n in prop_names):
        hints.append("contains colour boosting controls")
    if any("shark" in n.lower() for n in prop_names):
        hints.append("contains shark-specific colour/shadow/glow controls")
    if any("deform" in n.lower() or "wind" in n.lower() for n in prop_names):
        hints.append("contains deformation/wind/noise controls")

    lines.append("")
    lines.append("🧠 Shader insight")
    if hints:
        lines.append("This shader likely " + "; ".join(hints) + ".")
    else:
        lines.append("This exposes the shader's material inputs and compiled pass structure, but not readable original shader source.")
    lines.append("Unity bundles usually contain compiled/serialized shader data. UBE is reading the property recipe and pass metadata, not decompiling the original Shader Graph/HLSL source.")

    lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _resolve_record(bundle_index: Any | None, pptr_or_path_id: Any) -> Any | None:
    if bundle_index is None:
        return None
    if isinstance(pptr_or_path_id, int):
        path_id = pptr_or_path_id
    else:
        target_key = _pptr_target_source_path_id(pptr_or_path_id)
        if target_key is not None:
            rec = getattr(bundle_index, "record_by_source_path_id", {}).get(target_key)
            if rec is not None:
                return rec
        path_id = _pptr_path_id(pptr_or_path_id)
    if path_id is None:
        return None
    local = getattr(bundle_index, "record_by_path_id", {}).get(path_id)
    if local is not None:
        return local
    return getattr(bundle_index, "external_record_by_path_id", {}).get(path_id)


def _external_bundle_name(bundle_index: Any | None, path_id: int | None) -> str:
    if bundle_index is None or path_id is None:
        return ""
    p = getattr(bundle_index, "external_bundle_by_path_id", {}).get(path_id)
    if p is None:
        return ""
    try:
        return p.name
    except Exception:
        return str(p)


def _pptr_text(pptr: Any, bundle_index: Any | None = None) -> str:
    path_id = _pptr_path_id(pptr)
    file_id = _pptr_file_id(pptr)
    rec = _resolve_record(bundle_index, pptr)
    if rec is not None:
        local = True
        try:
            target_key = _pptr_target_source_path_id(pptr)
            if target_key is not None:
                local = target_key in getattr(bundle_index, "record_by_source_path_id", {})
            else:
                local = bool(bundle_index is not None and path_id in getattr(bundle_index, "record_by_path_id", {}))
        except Exception:
            local = bool(bundle_index is not None and path_id in getattr(bundle_index, "record_by_path_id", {}))
        ext = "" if local else f"  (external: {_external_bundle_name(bundle_index, path_id)})"
        src = f" [{_record_source_name(rec)}]" if _record_source_name(rec) else ""
        return f"{friendly_type_name(rec.type_name)} - {rec.name}  (PathID {rec.path_id}{src}){ext}"
    if path_id in (None, 0):
        return "-"
    external = " external" if file_id not in (None, 0) else ""
    fid = f", FileID {file_id}" if file_id is not None else ""
    return f"PathID {path_id}{fid}{external}"



def _pptr_resolution_lines(label: str, pptr: Any, bundle_index: Any | None, indent: str = "  ") -> list[str]:
    """Small diagnostics block for external PPtr references."""
    lines: list[str] = []
    pid = _pptr_path_id(pptr)
    fid = _pptr_file_id(pptr)
    if pid in (None, 0):
        return lines
    rec = _resolve_record(bundle_index, pptr)
    local = bool(bundle_index is not None and pid in getattr(bundle_index, "record_by_path_id", {}))
    bundle = _external_bundle_name(bundle_index, pid)
    lines.append(f"{indent}{label} raw: PathID {pid}" + (f", FileID {fid}" if fid is not None else ""))
    if rec is not None:
        where = "local" if local else (f"external: {bundle}" if bundle else "external")
        object_state = "loaded" if getattr(rec, "object", None) is not None else "metadata only"
        lines.append(f"{indent}{label} resolved: {friendly_type_name(rec.type_name)} - {rec.name}  ({where}, {object_state})")
    else:
        lines.append(f"{indent}{label} resolved: not found in loaded bundles/index yet")
    return lines

def _component_pptr(item: Any) -> Any:
    return _get(item, "component", "m_Component", default=item)


def _records_with_gameobject(bundle_index: Any | None, type_name: str, go_pid: int | None) -> list[Any]:
    if bundle_index is None or go_pid is None:
        return []
    out: list[Any] = []
    for rec in getattr(bundle_index, "objects_by_type", {}).get(type_name, []):
        data = _read(rec)
        if data is None:
            continue
        if _pptr_path_id(_get(data, "m_GameObject", "game_object", default=None)) == go_pid:
            out.append(rec)
    return out


def _component_records_for_gameobject(record: Any, data: Any, bundle_index: Any | None) -> list[Any]:
    records: list[Any] = []
    for item in _as_list(_get(data, "m_Components", "m_Component", default=None)):
        rec = _resolve_record(bundle_index, _component_pptr(item))
        if rec is not None:
            records.append(rec)
    return records


_MOTION_PROPERTY_TOKENS = (
    "wind", "sway", "bend", "deform", "gust", "wave", "noise", "flutter",
    "flap", "ripple", "waterfall", "flowspeed", "flowmap", "_flow", "scroll", "vertexoffset", "vertex_offset",
    "displace", "wobble", "pulse", "speed", "frequency", "amplitude", "direction",
)


def _material_motion_clues(material_pptr_or_record: Any, bundle_index: Any | None) -> dict[str, Any] | None:
    rec = material_pptr_or_record
    if rec is None or getattr(rec, "type_name", "") != "Material":
        rec = _resolve_record(bundle_index, material_pptr_or_record)
    if rec is None or getattr(rec, "type_name", "") != "Material":
        return None
    data = _read(rec)
    if data is None:
        return None

    shader_pptr = _get_any(data, "m_Shader", "shader", default=None)
    shader_name = _record_name_from_pptr(shader_pptr, bundle_index)
    saved = _get_any(data, "m_SavedProperties", "savedProperties", default=None)
    property_names: list[str] = []
    for field in ("m_Floats", "floats", "m_Colors", "colors", "m_TexEnvs", "texEnvs"):
        for item in _as_list(_get_any(saved, field, default=None)):
            key, _value = _pair_key_value(item)
            if key not in (None, ""):
                property_names.append(str(key))

    haystack = " ".join([str(getattr(rec, "name", "") or ""), shader_name, *property_names]).lower()
    matched = sorted({token for token in _MOTION_PROPERTY_TOKENS if token in haystack})
    if not matched:
        return None

    categories: list[str] = []
    if any(token in haystack for token in ("wind", "sway", "bend", "deform", "gust", "flutter")):
        categories.append("vertex wind/deformation")
    if any(token in haystack for token in ("ripple", "waterfall", "flowspeed", "flowmap", "_flow", "wave")):
        categories.append("water/flow movement")
    if any(token in haystack for token in ("flap", "wobble", "pulse")):
        categories.append("procedural oscillation")
    if any(token in haystack for token in ("scroll", "speed", "frequency", "amplitude", "noise")):
        categories.append("time/noise-driven material motion")
    return {
        "record": rec,
        "shader_name": shader_name,
        "properties": property_names,
        "matched": matched,
        "categories": categories,
    }


def _renderer_material_motion_clues(renderer_rec: Any, bundle_index: Any | None) -> list[dict[str, Any]]:
    data = _read(renderer_rec)
    if data is None:
        return []
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for mat in _as_list(_get_any(data, "m_Materials", "materials", default=None)):
        clue = _material_motion_clues(mat, bundle_index)
        if clue is None:
            continue
        rec = clue.get("record")
        pid = int(getattr(rec, "path_id", 0) or 0)
        if pid in seen:
            continue
        seen.add(pid)
        out.append(clue)
    return out


def _gameobject_motion_source_lines(components: list[Any], bundle_index: Any | None) -> list[str]:
    lines: list[str] = ["", "🎞 Motion-source investigation"]
    animator = next((c for c in components if c.type_name == "Animator"), None)
    legacy = next((c for c in components if c.type_name == "Animation"), None)
    skinned = next((c for c in components if c.type_name == "SkinnedMeshRenderer"), None)
    particle = next((c for c in components if c.type_name == "ParticleSystem"), None)
    renderers = [c for c in components if c.type_name in ("MeshRenderer", "SkinnedMeshRenderer", "ParticleSystemRenderer", "LineRenderer", "TrailRenderer")]

    found = False
    if animator is not None:
        found = True
        adata = _read(animator)
        controller = _get_any(adata, "m_Controller", "controller", default=None) if adata is not None else None
        controller_rec = _resolve_record(bundle_index, controller)
        lines.append("  ✓ Modern Animator component")
        lines.append(f"    Controller: {_pptr_text(controller, bundle_index)}")
        if controller_rec is not None and getattr(controller_rec, "type_name", "") in ("AnimatorController", "AnimatorOverrideController"):
            cdata = _read(controller_rec)
            clips = _animctrl_unique_clip_refs(cdata, bundle_index) if cdata is not None else []
            if clips:
                shown = [clip_rec.name for _pptr, clip_rec in clips if clip_rec is not None]
                lines.append(f"    Clips: {', '.join(shown[:10])}" + (f" ... +{len(shown)-10}" if len(shown) > 10 else ""))
        elif _pptr_path_id(controller) not in (None, 0):
            lines.append("    Controller is external and not decoded in the currently loaded sibling set.")

    if legacy is not None:
        found = True
        ldata = _read(legacy)
        clip_refs = _animation_collect_clip_pptrs(ldata) if ldata is not None else []
        lines.append("  ✓ Legacy Animation component")
        if clip_refs:
            names = []
            for _role, pptr in clip_refs:
                rec = _resolve_record(bundle_index, pptr)
                shown = rec.name if rec is not None else f"PathID {_pptr_path_id(pptr)}"
                if shown not in names:
                    names.append(shown)
            lines.append(f"    Clips: {', '.join(names[:10])}" + (f" ... +{len(names)-10}" if len(names) > 10 else ""))

    if skinned is not None:
        found = True
        sdata = _read(skinned)
        bones = _as_list(_get_any(sdata, "m_Bones", "bones", default=None)) if sdata is not None else []
        lines.append(f"  ✓ Skinned mesh: {len(bones)} bone references")
        if animator is None and legacy is None:
            lines.append("    The renderer can deform through bones, but the driving Animator may be on a parent GameObject.")

    if particle is not None:
        found = True
        lines.append("  ✓ ParticleSystem simulation")
        lines.append("    Visible motion can come from emitted particles even when no AnimationClip exists.")

    material_clues: list[dict[str, Any]] = []
    for renderer in renderers:
        material_clues.extend(_renderer_material_motion_clues(renderer, bundle_index))
    unique_clues: list[dict[str, Any]] = []
    seen_materials: set[int] = set()
    for clue in material_clues:
        rec = clue.get("record")
        pid = int(getattr(rec, "path_id", 0) or 0)
        if pid in seen_materials:
            continue
        seen_materials.add(pid)
        unique_clues.append(clue)
    if unique_clues:
        found = True
        lines.append("  ✓ Shader/material motion clues")
        for clue in unique_clues[:8]:
            rec = clue["record"]
            categories = ", ".join(clue.get("categories") or ["procedural material motion"])
            lines.append(f"    {rec.name}: {categories}")
            lines.append(f"      Shader: {clue.get('shader_name') or '-'}")
            prop_hits = [p for p in clue.get("properties", []) if any(t in p.lower() for t in _MOTION_PROPERTY_TOKENS)]
            if prop_hits:
                lines.append(f"      Motion properties: {', '.join(prop_hits[:12])}" + (f" ... +{len(prop_hits)-12}" if len(prop_hits) > 12 else ""))

    if not found:
        lines.append("  No direct Animator, legacy Animation, skinned rig, ParticleSystem, or motion-style shader properties were detected on this GameObject.")
        lines.append("  It may still inherit movement from an animated parent or be moved procedurally by a MonoBehaviour/script at runtime.")
    return lines


def _is_visual_material_float(name: str) -> bool:
    lower = name.lower()
    tokens = (
        "textureindex", "index", "basemapintensity", "intensity", "boost",
        "emis", "emiss", "glow", "caustic", "flap", "speed", "scale",
        "alpha", "cutoff", "surface", "blend", "zwrite", "cull",
        "metal", "smooth", "rough", "gloss",
    )
    return any(t in lower for t in tokens)


def _is_visual_material_colour(name: str) -> bool:
    lower = name.lower()
    tokens = (
        "base", "color", "colour", "tint", "eye", "bio", "emis",
        "emiss", "glow", "ambient", "water", "glass", "spec",
    )
    return any(t in lower for t in tokens)


def _material_colour_line(name: str, value: Any) -> str:
    text = _format_material_value(value)
    hx = _colour_hex(value)
    if hx:
        text = f"{text} {hx}"
    return f"{name}: {text}"


def _first_texture_index(float_props: dict[str, Any]) -> tuple[str, Any] | None:
    for preferred in ("_TextureIndex", "TextureIndex", "_BaseMapIndex", "_Slice", "_SliceIndex"):
        if preferred in float_props:
            return preferred, float_props[preferred]
    for key, value in float_props.items():
        if "textureindex" in key.lower() or "sliceindex" in key.lower():
            return key, value
    return None


def _material_slot_detail_lines(mat: Any, bundle_index: Any | None, indent: str) -> list[str]:
    """Return readable material internals for an Object/Renderer chain.

    This deliberately shows only the visually useful material data: shader,
    non-empty texture slots, texture-array slice/index values, and key colour/
    float parameters.  The full raw Material inspector remains available by
    clicking/selecting the material itself.
    """
    mat_rec = _resolve_record(bundle_index, mat)
    if mat_rec is None:
        return []
    data = _read(mat_rec)
    if data is None:
        return []

    lines: list[str] = []
    shader = _get(data, "m_Shader", "shader", default=None)
    if shader is not None:
        lines.append(f"{indent}  Shader: {_pptr_text(shader, bundle_index)}")

    saved = _get(data, "m_SavedProperties", "saved_properties", default=None)
    if saved is None:
        return lines

    tex_envs = _as_list(_get(saved, "m_TexEnvs", "tex_envs", default=None))
    floats = _as_list(_get(saved, "m_Floats", "floats", default=None))
    colours = _as_list(_get(saved, "m_Colors", "colors", default=None))
    float_props = _pairs_to_dict(floats)

    texture_rows: list[tuple[str, Any, Any | None, str]] = []
    has_texture_array = False
    for item in tex_envs:
        key, value = _pair_key_value(item)
        key_text = _clean_prop_name(key) or "Texture"
        texture = _get(value, "m_Texture", "texture", default=value)
        target = _record_name_from_pptr(texture, bundle_index)
        if _is_empty_texture_ref(texture, target):
            continue
        tex_rec = _resolve_record(bundle_index, texture)
        if tex_rec is not None and tex_rec.type_name == "Texture2DArray":
            has_texture_array = True
        texture_rows.append((key_text, texture, tex_rec, _texture_env_transform_text(value)))

    if texture_rows:
        lines.append(f"{indent}  Texture slots ({len(texture_rows)}):")
        for key_text, texture, tex_rec, transform_text in texture_rows[:12]:
            role = material_texture_role(key_text)
            type_note = f" [{tex_rec.type_name}]" if tex_rec is not None else ""
            lines.append(f"{indent}    {role} {key_text}: {_pptr_text(texture, bundle_index)}{type_note}")
            if transform_text:
                lines.append(f"{indent}      {transform_text}")
        if len(texture_rows) > 12:
            lines.append(f"{indent}    ... {len(texture_rows) - 12} more texture slots")

    if has_texture_array:
        idx = _first_texture_index(float_props)
        if idx is not None:
            lines.append(f"{indent}  Texture array slice/index: {idx[0]} = {_format_material_value(idx[1])}")
        else:
            lines.append(f"{indent}  Texture array: present, but no obvious _TextureIndex-style float was found")

    key_floats: list[tuple[str, Any]] = []
    for key, value in float_props.items():
        if _is_visual_material_float(key):
            key_floats.append((key, value))
    if key_floats:
        lines.append(f"{indent}  Key floats:")
        for key, value in key_floats[:16]:
            lines.append(f"{indent}    {key}: {_format_material_value(value)}")
        if len(key_floats) > 16:
            lines.append(f"{indent}    ... {len(key_floats) - 16} more float values")

    colour_rows: list[tuple[str, Any]] = []
    for item in colours:
        key, value = _pair_key_value(item)
        key_text = _clean_prop_name(key)
        if key_text and _is_visual_material_colour(key_text):
            colour_rows.append((key_text, value))
    if colour_rows:
        lines.append(f"{indent}  Key colours:")
        for key, value in colour_rows[:12]:
            lines.append(f"{indent}    {_material_colour_line(key, value)}")
        if len(colour_rows) > 12:
            lines.append(f"{indent}    ... {len(colour_rows) - 12} more colours")

    return lines


def _material_slot_lines(materials: list[Any], bundle_index: Any | None, indent: str = "  ", detailed: bool = True) -> list[str]:
    lines: list[str] = []
    if not materials:
        lines.append(f"{indent}Materials: none")
        return lines
    lines.append(f"{indent}Materials: {len(materials)} slot(s)")
    for i, mat in enumerate(materials[:32]):
        lines.append(f"{indent}  Slot {i}: {_pptr_text(mat, bundle_index)}")
        if detailed:
            lines.extend(_material_slot_detail_lines(mat, bundle_index, indent))
    if len(materials) > 32:
        lines.append(f"{indent}  ... {len(materials) - 32} more slots")
    return lines


def _renderer_flags_lines(data: Any, indent: str = "  ") -> list[str]:
    lines: list[str] = []
    enabled = _get(data, "m_Enabled", "enabled", default=None)
    if enabled is not None:
        lines.append(f"{indent}Enabled: {enabled}")
    for label, attr in (("Cast shadows", "m_CastShadows"), ("Receive shadows", "m_ReceiveShadows"), ("Sorting layer", "m_SortingLayer"), ("Sorting order", "m_SortingOrder"), ("Lightmap index", "m_LightmapIndex")):
        value = _get(data, attr, default=None)
        if value is not None:
            lines.append(f"{indent}{label}: {value}")
    return lines


def _describe_game_object(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🎲 Object inspector"]
    if data is None:
        lines.append("Unable to read GameObject data.")
        return lines

    layer = _get(data, "m_Layer", "layer", default=None)
    tag = _get(data, "m_Tag", "tag", default=None)
    active = _get(data, "m_IsActive", "is_active", default=None)
    lines.append(f"Active: {active if active is not None else '-'}")
    lines.append(f"Layer: {layer if layer is not None else '-'}")
    lines.append(f"Tag index: {tag if tag is not None else '-'}")

    components = _component_records_for_gameobject(record, data, bundle_index)
    lines.append("")
    lines.append(f"🧩 Components ({len(components)})")
    if components:
        for i, comp in enumerate(components[:64]):
            lines.append(f"  {i}: {friendly_type_name(comp.type_name)} - {comp.name}  (PathID {comp.path_id})")
        if len(components) > 64:
            lines.append(f"  ... {len(components) - 64} more components")
    else:
        lines.append("  No component list found on this object.")

    transform = next((c for c in components if c.type_name == "Transform"), None)
    mesh_filter = next((c for c in components if c.type_name == "MeshFilter"), None)
    mesh_renderer = next((c for c in components if c.type_name == "MeshRenderer"), None)
    skinned = next((c for c in components if c.type_name == "SkinnedMeshRenderer"), None)

    if transform is not None:
        tr_data = _read(transform)
        if tr_data is not None:
            lines.append("")
            lines.append("↔ Transform")
            lines.append(f"  Position: {_vec3_text(_get(tr_data, 'm_LocalPosition', 'local_position', default=None))}")
            lines.append(f"  Rotation: {_get(tr_data, 'm_LocalRotation', 'local_rotation', default='-')}")
            lines.append(f"  Scale: {_vec3_text(_get(tr_data, 'm_LocalScale', 'local_scale', default=None))}")
            lines.append(f"  Parent: {_pptr_text(_get(tr_data, 'm_Father', 'father', default=None), bundle_index)}")
            children = _as_list(_get(tr_data, "m_Children", "children", default=None))
            lines.append(f"  Children: {len(children)}")

    lines.append("")
    lines.append("🧊 Render chain")
    object_mesh_rec = None
    if mesh_filter is not None:
        mf_data = _read(mesh_filter)
        mesh = _get(mf_data, "m_Mesh", "mesh", default=None) if mf_data is not None else None
        object_mesh_rec = _resolve_record(bundle_index, mesh)
        lines.append(f"  Mesh Link: {mesh_filter.name}  (PathID {mesh_filter.path_id})")
        lines.append(f"  Mesh: {_pptr_text(mesh, bundle_index)}")
    if mesh_renderer is not None:
        mr_data = _read(mesh_renderer)
        mats = _as_list(_get(mr_data, "m_Materials", "materials", default=None)) if mr_data is not None else []
        lines.append(f"  Renderer: {mesh_renderer.name}  (PathID {mesh_renderer.path_id})")
        lines.extend(_material_slot_lines(mats, bundle_index, indent="  "))
        lines.extend(_describe_attached_mesh_atlas(object_mesh_rec, mats, bundle_index, indent="  "))
        if mr_data is not None:
            lines.extend(_renderer_flags_lines(mr_data, indent="  "))
    if skinned is not None:
        sm_data = _read(skinned)
        mesh = _get(sm_data, "m_Mesh", "mesh", default=None) if sm_data is not None else None
        skinned_mesh_rec = _resolve_record(bundle_index, mesh)
        mats = _as_list(_get(sm_data, "m_Materials", "materials", default=None)) if sm_data is not None else []
        lines.append(f"  Skinned Renderer: {skinned.name}  (PathID {skinned.path_id})")
        lines.append(f"  Mesh: {_pptr_text(mesh, bundle_index)}")
        lines.extend(_material_slot_lines(mats, bundle_index, indent="  "))
        lines.extend(_describe_attached_mesh_atlas(skinned_mesh_rec, mats, bundle_index, indent="  "))
        bones = _as_list(_get(sm_data, "m_Bones", "bones", default=None)) if sm_data is not None else []
        lines.append(f"  Bones: {len(bones)}")
    if mesh_filter is None and mesh_renderer is None and skinned is None:
        lines.append("  This object has no direct mesh renderer component. It may be a parent, bone, locator, audio helper, script holder, or grouping object.")

    lines.extend(_gameobject_motion_source_lines(components, bundle_index))

    lines.append("")
    lines.append("🧠 Object insight")
    if mesh_filter is not None and mesh_renderer is not None:
        lines.append("This is the normal static render pattern: one GameObject owns a Mesh Link/MeshFilter and a Mesh Renderer. The mesh gives the shape; the renderer gives the material slots.")
    elif skinned is not None:
        lines.append("This object uses a Skinned Mesh Renderer, so the mesh, materials and bones are on one renderer component rather than split between MeshFilter and MeshRenderer.")
    elif transform is not None and len(components) == 1:
        lines.append("This looks like a transform-only object, commonly used as a parent, bone, locator or scene hierarchy node.")
    else:
        lines.append("This object is a container for Unity components. The component list is the important part of understanding what it does.")

    lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_transform(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["↔ Transform"]
    if data is None:
        lines.append("Unable to read Transform data.")
        return lines
    lines.append(f"Object: {_pptr_text(_get(data, 'm_GameObject', 'game_object', default=None), bundle_index)}")
    lines.append(f"Parent: {_pptr_text(_get(data, 'm_Father', 'father', default=None), bundle_index)}")
    children = _as_list(_get(data, "m_Children", "children", default=None))
    lines.append(f"Children: {len(children)}")
    lines.append("")
    lines.append("📐 Local transform")
    lines.append(f"  Position: {_vec3_text(_get(data, 'm_LocalPosition', 'local_position', default=None))}")
    lines.append(f"  Rotation: {_get(data, 'm_LocalRotation', 'local_rotation', default='-')}")
    lines.append(f"  Scale: {_vec3_text(_get(data, 'm_LocalScale', 'local_scale', default=None))}")
    if children:
        lines.append("")
        lines.append("🔁 Child transforms")
        for i, child in enumerate(children[:40]):
            lines.append(f"  {i}: {_pptr_text(child, bundle_index)}")
        if len(children) > 40:
            lines.append(f"  ... {len(children) - 40} more children")
    lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_mesh_filter(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧊 Mesh Link / MeshFilter"]
    if data is None:
        lines.append("Unable to read MeshFilter data.")
        return lines
    go = _get(data, "m_GameObject", "game_object", default=None)
    go_pid = _pptr_path_id(go)
    mesh = _get(data, "m_Mesh", "mesh", default=None)
    lines.append(f"Object: {_pptr_text(go, bundle_index)}")
    lines.append(f"Mesh: {_pptr_text(mesh, bundle_index)}")

    renderers = _records_with_gameobject(bundle_index, "MeshRenderer", go_pid)
    if renderers:
        lines.append("")
        lines.append("👁 Matching renderer on same object")
        for r in renderers[:8]:
            rdata = _read(r)
            lines.append(f"  Renderer: {r.name}  (PathID {r.path_id})")
            mats = _as_list(_get(rdata, "m_Materials", "materials", default=None)) if rdata is not None else []
            lines.extend(_material_slot_lines(mats, bundle_index, indent="    "))
    else:
        lines.append("")
        lines.append("👁 Matching renderer on same object: not found")
    lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_mesh_renderer(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["👁 Renderer / MeshRenderer"]
    if data is None:
        lines.append("Unable to read MeshRenderer data.")
        return lines
    go = _get(data, "m_GameObject", "game_object", default=None)
    go_pid = _pptr_path_id(go)
    mats = _as_list(_get(data, "m_Materials", "materials", default=None))
    lines.append(f"Object: {_pptr_text(go, bundle_index)}")
    lines.extend(_renderer_flags_lines(data))
    lines.extend(_material_slot_lines(mats, bundle_index))

    filters = _records_with_gameobject(bundle_index, "MeshFilter", go_pid)
    if filters:
        lines.append("")
        lines.append("🧊 Matching mesh link on same object")
        for mf in filters[:8]:
            mfdata = _read(mf)
            mesh = _get(mfdata, "m_Mesh", "mesh", default=None) if mfdata is not None else None
            lines.append(f"  MeshFilter: {mf.name}  (PathID {mf.path_id})")
            lines.append(f"  Mesh: {_pptr_text(mesh, bundle_index)}")
    else:
        lines.append("")
        lines.append("🧊 Matching mesh link on same object: not found")

    motion_clues = _renderer_material_motion_clues(record, bundle_index)
    lines.append("")
    lines.append("🎞 Renderer motion clues")
    if motion_clues:
        for clue in motion_clues[:8]:
            mat_rec = clue["record"]
            categories = ", ".join(clue.get("categories") or ["procedural material motion"])
            lines.append(f"  {mat_rec.name}: {categories}")
            lines.append(f"    Shader: {clue.get('shader_name') or '-'}")
        lines.append("  The Mesh itself may remain static while its vertex shader moves vertices every frame.")
    else:
        lines.append("  No obvious motion-style material/shader properties detected on this renderer.")
    lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_skinned_mesh_renderer(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧍 Skinned Renderer"]
    if data is None:
        lines.append("Unable to read SkinnedMeshRenderer data.")
        return lines
    lines.append(f"Object: {_pptr_text(_get(data, 'm_GameObject', 'game_object', default=None), bundle_index)}")
    lines.append(f"Mesh: {_pptr_text(_get(data, 'm_Mesh', 'mesh', default=None), bundle_index)}")
    lines.extend(_renderer_flags_lines(data))
    lines.extend(_material_slot_lines(_as_list(_get(data, "m_Materials", "materials", default=None)), bundle_index))
    bones = _as_list(_get(data, "m_Bones", "bones", default=None))
    lines.append("")
    lines.append(f"↔ Bones ({len(bones)})")
    lines.append(f"  Root bone: {_pptr_text(_get(data, 'm_RootBone', 'root_bone', default=None), bundle_index)}")
    for i, bone in enumerate(bones[:40]):
        lines.append(f"  {i}: {_pptr_text(bone, bundle_index)}")
    if len(bones) > 40:
        lines.append(f"  ... {len(bones) - 40} more bones")
    lines.append("")
    lines.append("🎞 Motion-source summary")
    if bones:
        lines.append("  This renderer is deformable through bone matrices. An Animator/Animation component—often on a parent object—supplies the changing bone transforms.")
    else:
        lines.append("  No bone list was exposed; this may be a special renderer setup or incomplete external data.")
    motion_clues = _renderer_material_motion_clues(record, bundle_index)
    if motion_clues:
        lines.append("  Its materials also contain procedural motion clues:")
        for clue in motion_clues[:6]:
            lines.append(f"    • {clue['record'].name}: {', '.join(clue.get('categories') or ['material motion'])}")
    lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _sprite_render_data(data: Any) -> Any | None:
    return _get_any(data, "m_RD", "rd", "render_data", "m_RenderData", "renderData", default=None)


def _sprite_texture_pptr(data: Any) -> Any:
    rd = _sprite_render_data(data)
    if rd is not None:
        tex = _get_any(rd, "texture", "m_Texture", "m_Texture2D", "m_AtlasTexture", default=None)
        if tex is not None:
            return tex
        texs = _as_list(_get_any(rd, "textures", "m_Textures", default=None))
        if texs:
            return texs[0]
    return _get_any(data, "m_Texture", "texture", "m_AtlasTexture", default=None)


def _sprite_alpha_texture_pptr(data: Any) -> Any:
    rd = _sprite_render_data(data)
    if rd is not None:
        tex = _get_any(rd, "alphaTexture", "m_AlphaTexture", default=None)
        if tex is not None:
            return tex
    return _get_any(data, "m_AlphaTexture", "alphaTexture", default=None)


def _sprite_rect(data: Any) -> tuple[float, float, float, float] | None:
    for attr in ("m_Rect", "rect", "m_TextureRect", "textureRect"):
        r = _rect_tuple(_get_any(data, attr, default=None))
        if r is not None:
            return r
    rd = _sprite_render_data(data)
    if rd is not None:
        for attr in ("textureRect", "m_TextureRect", "m_Rect", "rect"):
            r = _rect_tuple(_get_any(rd, attr, default=None))
            if r is not None:
                return r
    return None


def _sprite_vertices_and_indices(data: Any) -> tuple[int | None, int | None]:
    rd = _sprite_render_data(data)
    candidates = []
    if rd is not None:
        candidates.extend([
            _get_any(rd, "vertices", "m_Vertices", default=None),
            _get_any(rd, "m_VertexData", "vertexData", default=None),
        ])
    candidates.extend([
        _get_any(data, "vertices", "m_Vertices", default=None),
        _get_any(data, "m_VertexData", "vertexData", default=None),
    ])
    v_count = None
    for c in candidates:
        if c is None:
            continue
        direct = _list_len(c)
        if direct not in (None, 0):
            v_count = direct
            break
        vc = _get_any(c, "m_VertexCount", "vertexCount", default=None)
        if vc is not None:
            try:
                v_count = int(vc)
                break
            except Exception:
                pass

    idx_candidates = []
    if rd is not None:
        idx_candidates.extend([_get_any(rd, "indices", "m_Indices", "triangles", "m_Triangles", default=None)])
    idx_candidates.extend([_get_any(data, "indices", "m_Indices", "triangles", "m_Triangles", default=None)])
    i_count = None
    for c in idx_candidates:
        n = _list_len(c)
        if n not in (None, 0):
            i_count = n
            break
    return v_count, i_count


def _sprite_uv_summary(data: Any, texture_size: tuple[int | None, int | None] | None = None) -> list[str]:
    lines: list[str] = []
    rd = _sprite_render_data(data)
    candidates = []
    if rd is not None:
        candidates.extend([
            ("UVs", _get_any(rd, "uv", "m_UV", "uvs", "m_UVs", default=None)),
            ("UV transform", _get_any(rd, "uvTransform", "m_UVTransform", default=None)),
        ])
    candidates.extend([
        ("UVs", _get_any(data, "uv", "m_UV", "uvs", "m_UVs", default=None)),
        ("UV transform", _get_any(data, "uvTransform", "m_UVTransform", default=None)),
    ])

    for label, value in candidates:
        if value is None:
            continue
        if label == "UV transform":
            v = _vec4_tuple(value, None)
            if v is not None:
                lines.append(f"  {label}: {_fmt_vec4(value)}")
                return lines
        vals = _as_list(value)
        if vals:
            coords = []
            for item in vals:
                v = _vec2_tuple(item, None)
                if v is not None:
                    coords.append(v)
            if coords:
                u0 = min(u for u, _ in coords); u1 = max(u for u, _ in coords)
                v0 = min(v for _, v in coords); v1 = max(v for _, v in coords)
                lines.append(f"  {label}: U {u0:.6f} → {u1:.6f}, V {v0:.6f} → {v1:.6f}, {len(coords)} coords")
                if texture_size and texture_size[0] and texture_size[1]:
                    w, h = texture_size
                    # UBE inspector convention: image Y is top-origin, so use 1-V.
                    x0 = int(round(u0 * w)); x1 = int(round(u1 * w))
                    y0 = int(round((1.0 - v1) * h)); y1 = int(round((1.0 - v0) * h))
                    lines.append(f"    On texture: x {x0}–{x1}, y {y0}–{y1} ({max(0, x1-x0)}×{max(0, y1-y0)} px)")
                return lines
    return lines


def _describe_sprite(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🖼 Sprite inspector"]
    if data is None:
        lines.append("Unable to read Sprite data.")
        return lines

    rect = _sprite_rect(data)
    if rect is not None:
        x, y, w, h = rect
        lines.append(f"Texture rect: x {_fmt_float(x)}, y {_fmt_float(y)}, w {_fmt_float(w)}, h {_fmt_float(h)}")
    else:
        lines.append("Texture rect: not exposed by decoder")

    texture_pptr = _sprite_texture_pptr(data)
    alpha_pptr = _sprite_alpha_texture_pptr(data)
    lines.append(f"Texture: {_pptr_text(texture_pptr, bundle_index)}")
    if _pptr_path_id(texture_pptr) not in (None, 0):
        lines.extend(_pptr_resolution_lines("Texture", texture_pptr, bundle_index))
    if _pptr_path_id(alpha_pptr) not in (None, 0):
        lines.append(f"Alpha texture: {_pptr_text(alpha_pptr, bundle_index)}")
        lines.extend(_pptr_resolution_lines("Alpha texture", alpha_pptr, bundle_index))

    tex_rec = _resolve_record(bundle_index, texture_pptr)
    texture_size = None
    if tex_rec is not None:
        tex_data = _read(tex_rec)
        tw = _get_any(tex_data, "m_Width", "width", default=None) if tex_data is not None else None
        th = _get_any(tex_data, "m_Height", "height", default=None) if tex_data is not None else None
        try:
            texture_size = (int(tw), int(th)) if tw and th else None
        except Exception:
            texture_size = None
        if texture_size:
            lines.append(f"Texture size: {texture_size[0]}×{texture_size[1]}")

    pivot = _get_any(data, "m_Pivot", "pivot", default=None)
    if pivot is not None:
        lines.append(f"Pivot: {_fmt_vec2(pivot)}")
    border = _get_any(data, "m_Border", "border", default=None)
    if border is not None:
        lines.append(f"Border / 9-slice: {_fmt_vec4(border)}")
    offset = _get_any(data, "m_Offset", "offset", default=None)
    if offset is not None:
        lines.append(f"Offset: {_fmt_vec2(offset)}")

    ppu = _get_any(data, "m_PixelsToUnits", "m_PixelsPerUnit", "pixelsToUnits", "pixelsPerUnit", default=None)
    if ppu is not None:
        lines.append(f"Pixels-to-units / PPU: {_fmt_float(ppu)}")

    packing_tag = _get_any(data, "m_PackingTag", "packingTag", default=None)
    atlas_tags = _get_any(data, "m_AtlasTags", "atlasTags", default=None)
    packed = _get_any(data, "m_Packed", "packed", default=None)
    packing_mode = _get_any(data, "m_PackingMode", "packingMode", default=None)
    mesh_type = _get_any(data, "m_MeshType", "meshType", default=None)
    if any(v is not None for v in (packed, packing_mode, mesh_type, packing_tag, atlas_tags)):
        lines.append("")
        lines.append("📦 Packing / mesh")
        if packed is not None:
            lines.append(f"  Packed: {packed}")
        if packing_mode is not None:
            lines.append(f"  Packing mode: {packing_mode}")
        if mesh_type is not None:
            lines.append(f"  Mesh type: {mesh_type}")
        if packing_tag not in (None, ""):
            lines.append(f"  Packing tag: {packing_tag}")
        tags = _as_list(atlas_tags)
        if tags:
            lines.append("  Atlas tags: " + ", ".join(str(t) for t in tags[:12]) + (f" ... +{len(tags)-12}" if len(tags) > 12 else ""))

    v_count, i_count = _sprite_vertices_and_indices(data)
    if v_count is not None or i_count is not None:
        lines.append("")
        lines.append("🔺 Sprite geometry")
        if v_count is not None:
            lines.append(f"  Vertices: {v_count}")
        if i_count is not None:
            tri_text = f", ~{i_count // 3} tris" if isinstance(i_count, int) else ""
            lines.append(f"  Indices: {i_count}{tri_text}")
        if v_count == 4:
            lines.append("  Pattern: likely a simple full-rect quad")
        elif v_count and v_count > 4:
            lines.append("  Pattern: likely a tight/custom sprite mesh rather than a plain rectangle")

    uv_lines = _sprite_uv_summary(data, texture_size)
    if uv_lines:
        lines.append("")
        lines.append("🗺 Sprite UV insight")
        lines.extend(uv_lines)
    elif rect is not None and texture_size:
        x, y, w, h = rect
        tw, th = texture_size
        u0 = x / tw; u1 = (x + w) / tw
        # Unity sprite rect Y is usually bottom-origin; show both because this is exactly what we are investigating.
        v0_bottom = y / th; v1_bottom = (y + h) / th
        v0_top = 1.0 - ((y + h) / th); v1_top = 1.0 - (y / th)
        lines.append("")
        lines.append("🗺 Sprite UV insight")
        lines.append(f"  Rect-derived UV: U {u0:.6f} → {u1:.6f}")
        lines.append(f"  V if rect Y is bottom-origin: {v0_bottom:.6f} → {v1_bottom:.6f}")
        lines.append(f"  V if image Y is top-origin: {v0_top:.6f} → {v1_top:.6f}")

    physics_shapes = _as_list(_get_any(data, "m_PhysicsShape", "physicsShape", default=None))
    if physics_shapes:
        lines.append("")
        lines.append(f"🧲 Physics shapes: {len(physics_shapes)}")

    lines.append("")
    lines.append("🧠 Sprite insight")
    if rect is not None:
        lines.append("This sprite is an atlas/window definition: the Sprite points at a Texture2D and defines the rectangle/UV area to display.")
    else:
        lines.append("This Sprite references texture/render data, but the decoder did not expose a clean rect field. Raw render data may still contain the usable UVs.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_sprite_renderer(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🖼 Sprite Renderer"]
    if data is None:
        lines.append("Unable to read SpriteRenderer data.")
        return lines

    go = _get_any(data, "m_GameObject", "game_object", default=None)
    sprite = _get_any(data, "m_Sprite", "sprite", default=None)
    lines.append(f"Object: {_pptr_text(go, bundle_index)}")
    lines.append(f"Sprite: {_pptr_text(sprite, bundle_index)}")
    lines.extend(_pptr_resolution_lines("Sprite", sprite, bundle_index))

    colour = _get_any(data, "m_Color", "color", "colour", default=None)
    if colour is not None:
        lines.append(f"Colour tint: {_colour_line(colour)}")
    flip_x = _get_any(data, "m_FlipX", "flipX", default=None)
    flip_y = _get_any(data, "m_FlipY", "flipY", default=None)
    if flip_x is not None or flip_y is not None:
        lines.append(f"Flip X/Y: {flip_x if flip_x is not None else '-'} / {flip_y if flip_y is not None else '-'}")

    draw_mode = _get_any(data, "m_DrawMode", "drawMode", default=None)
    size = _get_any(data, "m_Size", "size", default=None)
    tile_mode = _get_any(data, "m_SpriteTileMode", "spriteTileMode", default=None)
    adaptive = _get_any(data, "m_AdaptiveModeThreshold", "adaptiveModeThreshold", default=None)
    if any(v is not None for v in (draw_mode, size, tile_mode, adaptive)):
        lines.append("")
        lines.append("📐 Draw mode")
        if draw_mode is not None:
            lines.append(f"  Draw mode: {draw_mode}")
        if size is not None:
            lines.append(f"  Size: {_fmt_vec2(size)}")
        if tile_mode is not None:
            lines.append(f"  Tile mode: {tile_mode}")
        if adaptive is not None:
            lines.append(f"  Adaptive threshold: {_fmt_float(adaptive)}")

    lines.append("")
    lines.extend(_renderer_flags_lines(data, indent="  "))
    lines.extend(_material_slot_lines(_as_list(_get_any(data, "m_Materials", "materials", default=None)), bundle_index))

    sprite_rec = _resolve_record(bundle_index, sprite)
    if sprite_rec is not None:
        lines.append("")
        lines.append("🧩 Resolved Sprite summary")
        lines.append(f"  Sprite: {friendly_type_name(sprite_rec.type_name)} - {sprite_rec.name}  (PathID {sprite_rec.path_id})")
        ext_bundle = _external_bundle_name(bundle_index, getattr(sprite_rec, "path_id", None))
        if ext_bundle:
            lines.append(f"  Bundle: {ext_bundle}")
        if getattr(sprite_rec, "object", None) is None:
            lines.append("  Data: metadata only. Open/click the external Sprite or enable project PathID hydration to read rect/texture details.")
        sdata = _read(sprite_rec)
        if sdata is not None:
            tex = _sprite_texture_pptr(sdata)
            lines.append(f"  Texture: {_pptr_text(tex, bundle_index)}")
            lines.extend(_pptr_resolution_lines("Texture", tex, bundle_index, indent="  "))
            tex_rec = _resolve_record(bundle_index, tex)
            if tex_rec is not None:
                tdata = _read(tex_rec)
                if tdata is not None:
                    tw = _get_any(tdata, "m_Width", "width", default=None)
                    th = _get_any(tdata, "m_Height", "height", default=None)
                    if tw and th:
                        lines.append(f"  Texture size: {tw}×{th}")
            rect = _sprite_rect(sdata)
            if rect is not None:
                x, y, w, h = rect
                lines.append(f"  Rect: x {_fmt_float(x)}, y {_fmt_float(y)}, w {_fmt_float(w)}, h {_fmt_float(h)}")
            pivot = _get_any(sdata, "m_Pivot", "pivot", default=None)
            if pivot is not None:
                lines.append(f"  Pivot: {_fmt_vec2(pivot)}")
            ppu = _get_any(sdata, "m_PixelsToUnits", "m_PixelsPerUnit", "pixelsToUnits", "pixelsPerUnit", default=None)
            if ppu is not None:
                lines.append(f"  PPU: {_fmt_float(ppu)}")
            v_count, i_count = _sprite_vertices_and_indices(sdata)
            if v_count is not None or i_count is not None:
                lines.append(f"  Geometry: {v_count if v_count is not None else '-'} vertices" + (f", {i_count} indices" if i_count is not None else ""))

    lines.append("")
    lines.append("🧠 SpriteRenderer insight")
    lines.append("This is the component that draws a Sprite in the scene: the Sprite gives the atlas rectangle/mesh, while the renderer gives colour tint, flip, sorting and material behaviour.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _anim_safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _anim_object_fields(obj: Any) -> list[str]:
    if obj is None:
        return []
    if isinstance(obj, dict):
        return [str(k) for k in obj.keys()]
    fields: list[str] = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        if callable(value):
            continue
        fields.append(name)
    return fields


def _anim_child_values(obj: Any) -> list[Any]:
    if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
        return []
    if isinstance(obj, dict):
        return list(obj.values())
    if isinstance(obj, (list, tuple)):
        return list(obj)
    values: list[Any] = []
    for name in (
        "m_Curve", "curve", "Curve",
        "m_X", "m_Y", "m_Z", "m_W", "x", "y", "z", "w",
        "m_Keys", "keys", "Keyframes", "keyframes",
        "data", "value", "m_Value",
    ):
        value = _get_any(obj, name, default=None)
        if value is not None:
            values.append(value)
    return values


def _anim_key_time_value(item: Any) -> tuple[float | None, float | None]:
    t = _anim_safe_float(_get_any(item, "time", "m_Time", "Time", default=None))
    v = _anim_safe_float(_get_any(item, "value", "m_Value", "Value", default=None))
    return t, v


def _anim_collect_keyframes(obj: Any, max_depth: int = 5, _seen: set[int] | None = None) -> list[Any]:
    """Find Unity keyframe-like objects in decoded AnimationClip structures."""
    if obj is None:
        return []
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return []
    _seen.add(oid)

    if isinstance(obj, (str, bytes, int, float, bool)):
        return []

    if isinstance(obj, (list, tuple)):
        out: list[Any] = []
        for item in obj:
            t, _v = _anim_key_time_value(item)
            if t is not None:
                out.append(item)
            elif max_depth > 0:
                out.extend(_anim_collect_keyframes(item, max_depth - 1, _seen))
        return out

    t, _v = _anim_key_time_value(obj)
    if t is not None:
        return [obj]

    if max_depth <= 0:
        return []

    out: list[Any] = []
    for child in _anim_child_values(obj):
        out.extend(_anim_collect_keyframes(child, max_depth - 1, _seen))
    return out


def _anim_time_value_summary(keys: list[Any]) -> tuple[str, str]:
    times: list[float] = []
    values: list[float] = []
    for k in keys:
        t, v = _anim_key_time_value(k)
        if t is not None:
            times.append(t)
        if v is not None:
            values.append(v)
    if times:
        time_text = f"{min(times):.3f}s → {max(times):.3f}s"
    else:
        time_text = "-"
    if values:
        value_text = f"{min(values):.3f} → {max(values):.3f}"
    else:
        value_text = "-"
    return time_text, value_text


def _anim_target_path(item: Any) -> str:
    for name in ("m_Path", "path", "Path", "m_TransformPath", "transformPath"):
        value = _get_any(item, name, default=None)
        if value not in (None, ""):
            return str(value)
    binding = _get_any(item, "binding", "m_Binding", default=None)
    if binding is not None:
        for name in ("path", "m_Path", "Path"):
            value = _get_any(binding, name, default=None)
            if value not in (None, ""):
                return str(value)
    return "<root>"


def _anim_property_name(item: Any, fallback: str = "") -> str:
    for name in (
        "m_Attribute", "attribute", "Attribute",
        "m_PropertyName", "propertyName", "property", "name",
        "m_Name",
    ):
        value = _get_any(item, name, default=None)
        if value not in (None, ""):
            return str(value)
    binding = _get_any(item, "binding", "m_Binding", default=None)
    if binding is not None:
        for name in ("attribute", "m_Attribute", "propertyName", "m_PropertyName"):
            value = _get_any(binding, name, default=None)
            if value not in (None, ""):
                return str(value)
    return fallback or "-"


def _anim_class_text(item: Any) -> str:
    bits: list[str] = []
    for label, names in (
        ("class", ("m_ClassID", "classID", "class_id", "typeID", "m_TypeID")),
        ("script", ("m_Script", "script")),
    ):
        for name in names:
            value = _get_any(item, name, default=None)
            if value not in (None, "", 0):
                bits.append(f"{label} {value}")
                break
    return ", ".join(bits)


def _anim_curve_collection(data: Any, *names: str) -> list[Any]:
    for name in names:
        value = _get_any(data, name, default=None)
        items = _as_list(value)
        if items:
            return items
    return []


def _anim_collection_summary(lines: list[str], title: str, items: list[Any], limit: int = 16) -> float | None:
    if not items:
        return None
    lines.append(f"  {title}: {len(items)}")
    max_time: float | None = None
    for i, item in enumerate(items[:limit]):
        keys = _anim_collect_keyframes(item)
        t_text, v_text = _anim_time_value_summary(keys)
        for k in keys:
            t, _v = _anim_key_time_value(k)
            if t is not None:
                max_time = t if max_time is None else max(max_time, t)
        path = _anim_target_path(item)
        prop = _anim_property_name(item, title)
        class_text = _anim_class_text(item)
        suffix = f" [{class_text}]" if class_text else ""
        lines.append(f"    {i}: {path} :: {prop}{suffix}")
        lines.append(f"       keys: {len(keys)}, time: {t_text}, value: {v_text}")
    if len(items) > limit:
        lines.append(f"    ... {len(items) - limit} more {title.lower()}")
    return max_time


# Unity animation bindings store the target Transform path as Unity's 32-bit
# string hash.  In current Unity data this matches CRC32 of the UTF-8 hierarchy
# path.  UBE can therefore reverse the hash when the matching GameObject/
# Transform hierarchy is present in the opened bundle or one of its loaded
# course siblings.
_ANIM_PATH_CACHE: dict[int, tuple[tuple[int, ...], dict[int, list[tuple[str, str, str]]]]] = {}
_ANIM_PATH_RECORD_CACHE: dict[int, tuple[tuple[int, ...], dict[str, list[Any]]]] = {}


# v2.2r: bounded diagnostics for AnimationClips whose Transform motion is
# present but whose visible geometry is not directly serialized beneath the
# animated target.  This deliberately reports the gap instead of guessing a
# runtime/culling/script relationship.
_ANIM_RUNTIME_GRAPH_CACHE: dict[int, tuple[tuple[int, ...], dict[str, Any]]] = {}
_ANIM_RUNTIME_DIAG_CACHE: dict[tuple[int, tuple[str, str, int, str]], tuple[tuple[int, ...], dict[str, Any]]] = {}


def _anim_key3(rec: Any) -> tuple[str, str, int]:
    sf, sn, pid, _typ = _anim_record_identity(rec)
    return sf, sn, pid


def _anim_normalized_name(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value or "") if ch.isalnum())


def _anim_runtime_graph(bundle_index: Any | None) -> dict[str, Any]:
    """Build a small source-aware Transform graph once per loaded bundle.

    The graph is intentionally limited to GameObject/Transform identity and
    parent-child links.  Component payloads are read lazily only for the few
    candidate branches used by the diagnostic.
    """
    if bundle_index is None:
        return {}
    cache_key = id(bundle_index)
    signature = _anim_path_cache_signature(bundle_index)
    cached = _ANIM_RUNTIME_GRAPH_CACHE.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1]

    game_objects = _anim_loaded_records(bundle_index, ("GameObject",))
    transforms = _anim_loaded_records(bundle_index, ("Transform", "RectTransform"))
    go_by_key: dict[tuple[str, str, int], Any] = {_anim_key3(rec): rec for rec in game_objects}
    tr_by_key: dict[tuple[str, str, int], Any] = {_anim_key3(rec): rec for rec in transforms}
    go_to_tr: dict[tuple[str, str, int], tuple[str, str, int]] = {}
    tr_to_go: dict[tuple[str, str, int], tuple[str, str, int]] = {}
    parent_by_tr: dict[tuple[str, str, int], tuple[str, str, int] | None] = {}
    children_by_tr: dict[tuple[str, str, int], list[tuple[str, str, int]]] = {}

    for rec in transforms:
        data = _read(rec)
        if data is None:
            continue
        tr_key = _anim_key3(rec)
        go_key = _anim_owner_target_key(rec, _get_any(data, "m_GameObject", "gameObject", default=None))
        parent_key = _anim_owner_target_key(rec, _get_any(data, "m_Father", "father", default=None))
        if go_key is not None:
            go_to_tr[go_key] = tr_key
            tr_to_go[tr_key] = go_key
        parent_by_tr[tr_key] = parent_key if parent_key in tr_by_key else None
        if parent_key in tr_by_key:
            children_by_tr.setdefault(parent_key, []).append(tr_key)

    graph = {
        "game_objects": game_objects,
        "go_by_key": go_by_key,
        "tr_by_key": tr_by_key,
        "go_to_tr": go_to_tr,
        "tr_to_go": tr_to_go,
        "parent_by_tr": parent_by_tr,
        "children_by_tr": children_by_tr,
    }
    _ANIM_RUNTIME_GRAPH_CACHE[cache_key] = (signature, graph)
    return graph


def _anim_runtime_target_paths(data: Any, bundle_index: Any | None) -> list[str]:
    paths: list[str] = []
    for names in (
        ("m_PositionCurves", "positionCurves", "position_curves"),
        ("m_RotationCurves", "rotationCurves", "rotation_curves"),
        ("m_EulerCurves", "eulerCurves", "euler_curves"),
        ("m_ScaleCurves", "scaleCurves", "scale_curves"),
    ):
        for item in _anim_curve_collection(data, *names):
            path = str(_anim_target_path(item) or "").strip("/")
            if path and path != "<root>" and path not in paths:
                paths.append(path)

    # Streamed clips expose only binding hashes.  Add a path only when its hash
    # resolves unambiguously by text; ambiguous duplicate instances remain a
    # preview-level concern and are not used to invent a diagnostic owner.
    binding_const = _get_any(data, "m_ClipBindingConstant", "clipBindingConstant", default=None)
    generic = _as_list(_get_any(binding_const, "genericBindings", "m_GenericBindings", default=None)) if binding_const is not None else []
    hash_index = _anim_build_path_hash_index(bundle_index) if generic else {}
    for binding in generic:
        if _anim_binding_type_id(binding) != 4:
            continue
        try:
            path_hash = int(_get_any(binding, "path", "m_Path", default=0) or 0) & 0xFFFFFFFF
        except Exception:
            continue
        distinct = []
        for candidate, _bundle_label, _source_name in hash_index.get(path_hash, []):
            candidate = str(candidate or "").strip("/")
            if candidate and candidate != "<root>" and candidate not in distinct:
                distinct.append(candidate)
        if len(distinct) == 1 and distinct[0] not in paths:
            paths.append(distinct[0])
    return paths[:24]


def _anim_runtime_walk(graph: dict[str, Any], root_key: tuple[str, str, int], *, max_nodes: int = 192, max_depth: int = 16) -> list[tuple[tuple[str, str, int], int]]:
    out: list[tuple[tuple[str, str, int], int]] = []
    queue: list[tuple[tuple[str, str, int], int]] = [(root_key, 0)]
    seen: set[tuple[str, str, int]] = set()
    children = graph.get("children_by_tr", {})
    while queue and len(out) < max_nodes:
        key, depth = queue.pop(0)
        if key in seen or depth > max_depth:
            continue
        seen.add(key)
        out.append((key, depth))
        if depth < max_depth:
            for child in children.get(key, [])[:96]:
                if child not in seen:
                    queue.append((child, depth + 1))
    return out


def _anim_runtime_resolve_local_path(graph: dict[str, Any], owner_tr_key: tuple[str, str, int], path: str) -> list[tuple[str, str, int]]:
    segments = [part for part in str(path or "").split("/") if part]
    if not segments:
        return [owner_tr_key]
    go_by_key = graph.get("go_by_key", {})
    tr_to_go = graph.get("tr_to_go", {})
    children = graph.get("children_by_tr", {})

    owner_go = go_by_key.get(tr_to_go.get(owner_tr_key))
    owner_name = str(getattr(owner_go, "name", "") or "")
    if segments and segments[0] == owner_name:
        segments = segments[1:]
    current = [owner_tr_key]
    for segment in segments:
        next_keys: list[tuple[str, str, int]] = []
        for parent_key in current:
            for child_key in children.get(parent_key, []):
                go_rec = go_by_key.get(tr_to_go.get(child_key))
                if str(getattr(go_rec, "name", "") or "") == segment:
                    next_keys.append(child_key)
        current = next_keys
        if not current:
            break
    return current


def _anim_runtime_visual_state(bundle_index: Any | None, graph: dict[str, Any], root_keys: list[tuple[str, str, int]]) -> dict[str, Any]:
    valid: list[str] = []
    missing: list[str] = []
    visited_go: set[tuple[str, str, int]] = set()
    go_by_key = graph.get("go_by_key", {})
    tr_to_go = graph.get("tr_to_go", {})

    for root_key in root_keys[:12]:
        for tr_key, _depth in _anim_runtime_walk(graph, root_key, max_nodes=128, max_depth=12):
            go_key = tr_to_go.get(tr_key)
            if go_key is None or go_key in visited_go:
                continue
            visited_go.add(go_key)
            go_rec = go_by_key.get(go_key)
            if go_rec is None:
                continue
            go_data = _read(go_rec)
            if go_data is None:
                continue
            go_name = str(getattr(go_rec, "name", "") or f"GameObject_{getattr(go_rec, 'path_id', 0)}")
            components = _component_records_for_gameobject(go_rec, go_data, bundle_index)
            component_types = {str(getattr(comp, "type_name", "") or "") for comp in components}
            mesh_filter_seen = False
            mesh_filter_valid = False
            for comp in components:
                comp_type = str(getattr(comp, "type_name", "") or "")
                comp_data = _read(comp)
                if comp_data is None:
                    continue
                if comp_type == "MeshFilter":
                    mesh_filter_seen = True
                    mesh_pptr = _get_any(comp_data, "m_Mesh", "mesh", default=None)
                    if _pptr_path_id(mesh_pptr) not in (None, 0):
                        mesh_filter_valid = True
                        valid.append(f"{go_name} → MeshFilter mesh")
                    else:
                        missing.append(f"{go_name} → MeshFilter m_Mesh is null")
                elif comp_type == "SkinnedMeshRenderer":
                    mesh_pptr = _get_any(comp_data, "m_Mesh", "mesh", default=None)
                    if _pptr_path_id(mesh_pptr) not in (None, 0):
                        valid.append(f"{go_name} → SkinnedMeshRenderer mesh")
                    else:
                        missing.append(f"{go_name} → SkinnedMeshRenderer m_Mesh is null")
                elif comp_type == "SpriteRenderer":
                    sprite_pptr = _get_any(comp_data, "m_Sprite", "sprite", default=None)
                    if _pptr_path_id(sprite_pptr) not in (None, 0):
                        valid.append(f"{go_name} → SpriteRenderer sprite")
                    else:
                        missing.append(f"{go_name} → SpriteRenderer m_Sprite is null")
                elif comp_type in ("LineRenderer", "TrailRenderer", "ParticleSystemRenderer"):
                    # These render procedurally at runtime and are valid visible
                    # components even though they do not reference a normal Mesh.
                    valid.append(f"{go_name} → {comp_type} runtime geometry")
            if "MeshRenderer" in component_types and not mesh_filter_seen:
                missing.append(f"{go_name} → MeshRenderer has no MeshFilter on the same object")
            elif "MeshRenderer" in component_types and mesh_filter_seen and not mesh_filter_valid:
                # The precise null MeshFilter line above is already included.
                pass

    # Stable de-duplication while preserving hierarchy order.
    return {
        "valid": list(dict.fromkeys(valid)),
        "missing": list(dict.fromkeys(missing)),
        "visited_go": visited_go,
    }


def _animation_runtime_linkage_diagnostic(record: Any, data: Any | None, bundle_index: Any | None) -> dict[str, Any]:
    """Explain a decoded-motion / missing-visible-link edge case.

    This function never changes the preview.  It performs a bounded check and
    only returns a warning when the clip name identifies a coherent owner, the
    animation paths resolve below it, and those animated branches lack a normal
    visible mesh/sprite relationship.
    """
    if data is None or bundle_index is None:
        return finish({})
    signature = _anim_path_cache_signature(bundle_index)
    diagnostic_cache_key = (id(bundle_index), _anim_record_identity(record))
    cached = _ANIM_RUNTIME_DIAG_CACHE.get(diagnostic_cache_key)
    if cached is not None and cached[0] == signature:
        return dict(cached[1])

    def finish(value: dict[str, Any]) -> dict[str, Any]:
        _ANIM_RUNTIME_DIAG_CACHE[diagnostic_cache_key] = (signature, dict(value))
        return value
    paths = _anim_runtime_target_paths(data, bundle_index)
    if not paths:
        return finish({})
    graph = _anim_runtime_graph(bundle_index)
    if not graph:
        return finish({})

    clip_name = str(getattr(record, "name", "") or "")
    clip_key = _anim_normalized_name(clip_name)
    if not clip_key:
        return finish({})

    ranked: list[tuple[tuple[int, int], Any, tuple[str, str, int], dict[str, list[tuple[str, str, int]]]]] = []
    for owner_go in graph.get("game_objects", [])[:5000]:
        owner_name = str(getattr(owner_go, "name", "") or "").strip()
        owner_key = _anim_normalized_name(owner_name)
        if len(owner_key) < 5 or not clip_key.startswith(owner_key):
            continue
        owner_tr_key = graph.get("go_to_tr", {}).get(_anim_key3(owner_go))
        if owner_tr_key is None:
            continue
        resolved: dict[str, list[tuple[str, str, int]]] = {}
        all_hit = True
        for path in paths:
            matches = _anim_runtime_resolve_local_path(graph, owner_tr_key, path)
            if not matches:
                all_hit = False
                break
            resolved[path] = matches
        if not all_hit:
            continue
        subtree_size = len(_anim_runtime_walk(graph, owner_tr_key, max_nodes=160, max_depth=16))
        ranked.append(((len(owner_key), -subtree_size), owner_go, owner_tr_key, resolved))

    if not ranked:
        return finish({})
    ranked.sort(key=lambda row: row[0], reverse=True)
    _score, owner_go, owner_tr_key, resolved = ranked[0]
    target_keys = [key for rows in resolved.values() for key in rows]
    target_state = _anim_runtime_visual_state(bundle_index, graph, target_keys)
    if target_state.get("valid"):
        return finish({})

    # Look for culling/runtime/proxy branches elsewhere below the same owner.
    target_descendants: set[tuple[str, str, int]] = set()
    for key in target_keys:
        target_descendants.update(k for k, _depth in _anim_runtime_walk(graph, key, max_nodes=160, max_depth=16))
    runtime_tokens = ("perfectculling", "culling", "runtime", "proxy", "generated", "instanc")
    runtime_branches: list[str] = []
    go_by_key = graph.get("go_by_key", {})
    tr_to_go = graph.get("tr_to_go", {})
    for tr_key, _depth in _anim_runtime_walk(graph, owner_tr_key, max_nodes=192, max_depth=18):
        if tr_key in target_descendants:
            continue
        go_rec = go_by_key.get(tr_to_go.get(tr_key))
        go_name = str(getattr(go_rec, "name", "") or "") if go_rec is not None else ""
        if not go_name or not any(token in go_name.lower() for token in runtime_tokens):
            continue
        branch_state = _anim_runtime_visual_state(bundle_index, graph, [tr_key])
        if branch_state.get("valid"):
            runtime_branches.append(go_name)

    missing = list(target_state.get("missing") or [])
    if not missing and not runtime_branches:
        return finish({})

    owner_name = str(getattr(owner_go, "name", "") or "named animation owner")
    return finish({
        "warning": True,
        "owner": owner_name,
        "paths": paths,
        "missing": missing[:12],
        "runtime_branches": list(dict.fromkeys(runtime_branches))[:8],
        "status": "motion decoded; visible runtime linkage incomplete",
    })


def _animation_runtime_linkage_lines(record: Any, data: Any | None, bundle_index: Any | None) -> list[str]:
    diagnostic = _animation_runtime_linkage_diagnostic(record, data, bundle_index)
    if not diagnostic.get("warning"):
        return []
    lines = ["", "⚠ Runtime visual linkage"]
    lines.append("  The motion curves and target Transform path are present, but the animated branch has no normal serialized visible mesh/sprite relationship that UBE can safely follow.")
    lines.append(f"  Named owner: {diagnostic.get('owner')}")
    paths = diagnostic.get("paths") or []
    if paths:
        lines.append("  Animated target(s): " + ", ".join(str(path) for path in paths[:8]))
    missing = diagnostic.get("missing") or []
    if missing:
        lines.append("  Missing/null visual references:")
        for row in missing:
            lines.append(f"    • {row}")
    runtime_branches = diagnostic.get("runtime_branches") or []
    if runtime_branches:
        lines.append("  Separate runtime/culling branch(es) with visible geometry:")
        for name in runtime_branches:
            lines.append(f"    • {name}")
    lines.append("  Likely result: Unity, a culling system, constraint, or game script completes the visible linkage at runtime. UBE reports the gap rather than attaching unrelated geometry by guesswork.")
    return lines


def _anim_record_identity(rec: Any) -> tuple[str, str, int, str]:
    try:
        source_file = str(getattr(rec, "source_file", "") or "")
    except Exception:
        source_file = ""
    try:
        source_name = str(getattr(rec, "source_name", "") or "")
    except Exception:
        source_name = ""
    try:
        path_id = int(getattr(rec, "path_id", 0) or 0)
    except Exception:
        path_id = 0
    return source_file, source_name, path_id, str(getattr(rec, "type_name", "") or "")


def _anim_loaded_records(bundle_index: Any | None, type_names: tuple[str, ...]) -> list[Any]:
    if bundle_index is None:
        return []
    out: list[Any] = []
    seen: set[tuple[str, str, int, str]] = set()

    for type_name in type_names:
        for rec in getattr(bundle_index, "objects_by_type", {}).get(type_name, []):
            key = _anim_record_identity(rec)
            if key not in seen:
                out.append(rec)
                seen.add(key)
        for rec in getattr(bundle_index, "external_records_by_type", {}).get(type_name, []):
            key = _anim_record_identity(rec)
            if key not in seen:
                out.append(rec)
                seen.add(key)

    # Compatibility with indexes created before external_records_by_type was
    # added.  This flat map may omit PathID collisions, but is still better than
    # showing no external names at all.
    if not getattr(bundle_index, "external_records_by_type", None):
        for rec in getattr(bundle_index, "external_record_by_path_id", {}).values():
            if str(getattr(rec, "type_name", "") or "") not in type_names:
                continue
            key = _anim_record_identity(rec)
            if key not in seen:
                out.append(rec)
                seen.add(key)
    return out


def _anim_owner_target_key(owner_rec: Any, pptr: Any) -> tuple[str, str, int] | None:
    pid = _pptr_path_id(pptr)
    if pid in (None, 0):
        return None
    source_file = str(getattr(owner_rec, "source_file", "") or "")
    source_name = str(getattr(owner_rec, "source_name", "") or "")
    target = _pptr_target_source_path_id(pptr)
    if target is not None:
        target_source, target_pid = target
        return source_file, str(target_source or source_name), int(target_pid)
    return source_file, source_name, int(pid)


def _anim_path_cache_signature(bundle_index: Any | None) -> tuple[int, ...]:
    if bundle_index is None:
        return (0,)
    local = getattr(bundle_index, "objects_by_type", {}) or {}
    external = getattr(bundle_index, "external_records_by_type", {}) or {}
    return (
        len(local.get("GameObject", [])),
        len(local.get("Transform", [])),
        len(local.get("RectTransform", [])),
        len(external.get("GameObject", [])),
        len(external.get("Transform", [])),
        len(external.get("RectTransform", [])),
        int(getattr(bundle_index, "external_object_count", 0) or 0),
    )


def _anim_build_path_hash_index(bundle_index: Any | None) -> dict[int, list[tuple[str, str, str]]]:
    if bundle_index is None:
        return {}
    cache_key = id(bundle_index)
    signature = _anim_path_cache_signature(bundle_index)
    cached = _ANIM_PATH_CACHE.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1]

    game_objects = _anim_loaded_records(bundle_index, ("GameObject",))
    transforms = _anim_loaded_records(bundle_index, ("Transform", "RectTransform"))

    go_names: dict[tuple[str, str, int], str] = {}
    go_records: dict[tuple[str, str, int], Any] = {}
    for rec in game_objects:
        sf, sn, pid, _type = _anim_record_identity(rec)
        go_names[(sf, sn, pid)] = str(getattr(rec, "name", "") or f"GameObject_{pid}")
        go_records[(sf, sn, pid)] = rec

    nodes: dict[tuple[str, str, int], tuple[str, tuple[str, str, int] | None, Any, Any]] = {}
    for rec in transforms:
        data = _read(rec)
        if data is None:
            continue
        sf, sn, pid, _type = _anim_record_identity(rec)
        key = (sf, sn, pid)
        go_key = _anim_owner_target_key(rec, _get_any(data, "m_GameObject", "gameObject", default=None))
        name = go_names.get(go_key, str(getattr(rec, "name", "") or f"Transform_{pid}"))
        parent_key = _anim_owner_target_key(rec, _get_any(data, "m_Father", "father", default=None))
        nodes[key] = (name, parent_key, go_records.get(go_key) or rec, rec)

    full_cache: dict[tuple[str, str, int], str] = {}

    def full_path(key: tuple[str, str, int], stack: set[tuple[str, str, int]] | None = None) -> str:
        if key in full_cache:
            return full_cache[key]
        node = nodes.get(key)
        if node is None:
            return ""
        name, parent_key, _target_rec, _transform_rec = node
        if stack is None:
            stack = set()
        if key in stack:
            full_cache[key] = name
            return name
        stack = set(stack)
        stack.add(key)
        parent_path = full_path(parent_key, stack) if parent_key in nodes else ""
        path = f"{parent_path}/{name}" if parent_path else name
        full_cache[key] = path
        return path

    result: dict[int, list[tuple[str, str, str]]] = {0: [("<root>", "", "")]}
    record_result: dict[str, list[Any]] = {}
    seen_rows: set[tuple[int, str, str, str]] = set()
    seen_record_rows: set[tuple[str, tuple[str, str, int, str]]] = set()
    for key, (_name, _parent, target_rec, rec) in nodes.items():
        path = full_path(key)
        if not path:
            continue
        parts = [part for part in path.split("/") if part]
        try:
            bundle_label = Path(str(getattr(rec, "source_file", "") or "")).name
        except Exception:
            bundle_label = str(getattr(rec, "source_file", "") or "")
        source_name = str(getattr(rec, "source_name", "") or "")
        # Animation paths are relative to the Animator/Animation root, so every
        # suffix of the absolute scene hierarchy is a legitimate candidate.
        for start in range(len(parts)):
            candidate = "/".join(parts[start:])
            path_hash = zlib.crc32(candidate.encode("utf-8")) & 0xFFFFFFFF
            row_key = (path_hash, candidate, bundle_label, source_name)
            if row_key in seen_rows:
                pass
            else:
                result.setdefault(path_hash, []).append((candidate, bundle_label, source_name))
                seen_rows.add(row_key)

            target_identity = _anim_record_identity(target_rec)
            record_key = (candidate, target_identity)
            if record_key not in seen_record_rows:
                record_result.setdefault(candidate, []).append(target_rec)
                seen_record_rows.add(record_key)

    _ANIM_PATH_CACHE[cache_key] = (signature, result)
    _ANIM_PATH_RECORD_CACHE[cache_key] = (signature, record_result)
    return result


def _anim_build_path_record_index(bundle_index: Any | None) -> dict[str, list[Any]]:
    """Return animation-relative hierarchy suffixes mapped to scene records.

    The hash resolver and relationship-flow preview share one hierarchy walk so
    a large scene is not decoded twice merely to make target boxes clickable.
    """
    if bundle_index is None:
        return {}
    cache_key = id(bundle_index)
    signature = _anim_path_cache_signature(bundle_index)
    cached = _ANIM_PATH_RECORD_CACHE.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1]
    # Build/rebuild both the hash and record maps in one pass.
    _ANIM_PATH_CACHE.pop(cache_key, None)
    _anim_build_path_hash_index(bundle_index)
    cached = _ANIM_PATH_RECORD_CACHE.get(cache_key)
    return cached[1] if cached is not None and cached[0] == signature else {}


ANIMATION_BINDING_TYPE_NAMES: dict[int, str] = {
    1: "GameObject",
    4: "Transform",
    21: "Material",
    23: "MeshRenderer",
    95: "Animator",
    111: "Animation",
    120: "LineRenderer",
    137: "SkinnedMeshRenderer",
    198: "ParticleSystem",
    199: "ParticleSystemRenderer",
    212: "SpriteRenderer",
}

ANIMATION_TRANSFORM_ATTRIBUTES: dict[int, str] = {
    1: "Local position",
    2: "Local rotation (quaternion)",
    3: "Local scale",
    4: "Local Euler rotation",
}

_ANIMATION_PROPERTY_HASH_NAMES: dict[int, str] = {
    zlib.crc32(name.encode("utf-8")) & 0xFFFFFFFF: name
    for name in (
        "m_IsActive", "m_Enabled", "m_LocalPosition", "m_LocalRotation", "m_LocalScale",
        "m_Color", "m_Materials", "m_Sprite", "m_Intensity", "m_Range", "m_SpotAngle",
        "_Color", "_BaseColor", "_EmissionColor", "_MainTex_ST", "_BaseMap_ST",
    )
}


def _anim_binding_type_id(binding: Any) -> int | None:
    value = _get_any(binding, "typeID", "m_TypeID", "classID", "m_ClassID", default=None)
    try:
        return int(value) if value is not None else None
    except Exception:
        return None


def _anim_binding_property_text(binding: Any) -> str:
    attr = _get_any(binding, "attribute", "m_Attribute", default=None)
    try:
        attr_int = int(attr)
    except Exception:
        return str(attr) if attr is not None else "Unknown property"
    type_id = _anim_binding_type_id(binding)
    if type_id == 4 and attr_int in ANIMATION_TRANSFORM_ATTRIBUTES:
        return ANIMATION_TRANSFORM_ATTRIBUTES[attr_int]
    known = _ANIMATION_PROPERTY_HASH_NAMES.get(attr_int)
    if known:
        if known == "m_IsActive":
            return "GameObject active/inactive (m_IsActive)"
        if known == "m_Enabled":
            return "Component enabled (m_Enabled)"
        return known
    return f"Property hash {attr_int} (0x{attr_int & 0xFFFFFFFF:08X})"


def _anim_resolved_binding_lines(data: Any, bundle_index: Any | None, limit_paths: int = 80) -> list[str]:
    binding_const = _get_any(data, "m_ClipBindingConstant", "clipBindingConstant", default=None)
    generic = _as_list(_get_any(binding_const, "genericBindings", "m_GenericBindings", default=None)) if binding_const is not None else []
    if not generic:
        return []

    hash_index = _anim_build_path_hash_index(bundle_index)
    grouped: dict[str, dict[str, Any]] = {}
    unresolved: dict[int, list[str]] = {}
    unique_hashes: set[int] = set()
    resolved_hashes: set[int] = set()
    type_counts: dict[str, int] = {}

    for binding in generic:
        try:
            path_hash = int(_get_any(binding, "path", "m_Path", default=0) or 0) & 0xFFFFFFFF
        except Exception:
            path_hash = 0
        unique_hashes.add(path_hash)
        type_id = _anim_binding_type_id(binding)
        type_name = ANIMATION_BINDING_TYPE_NAMES.get(type_id, f"TypeID {type_id}" if type_id is not None else "Unknown type")
        type_counts[type_name] = type_counts.get(type_name, 0) + 1
        property_text = _anim_binding_property_text(binding)
        flags: list[str] = []
        if _get_any(binding, "isPPtrCurve", "m_IsPPtrCurve", default=0):
            flags.append("object-reference curve")
        if _get_any(binding, "isIntCurve", "m_IsIntCurve", default=0):
            flags.append("integer curve")
        suffix = f" [{type_name}" + (f"; {', '.join(flags)}" if flags else "") + "]"
        candidates = hash_index.get(path_hash, [])
        if candidates:
            resolved_hashes.add(path_hash)
            for path, bundle_label, source_name in candidates:
                entry = grouped.setdefault(path, {"properties": [], "sources": []})
                row = property_text + suffix
                if row not in entry["properties"]:
                    entry["properties"].append(row)
                source = (bundle_label, source_name)
                if source not in entry["sources"]:
                    entry["sources"].append(source)
        else:
            row = property_text + suffix
            if row not in unresolved.setdefault(path_hash, []):
                unresolved[path_hash].append(row)

    lines: list[str] = ["", "🧭 Resolved animation wiring"]
    lines.append(f"  Target path hashes resolved: {len(resolved_hashes)} / {len(unique_hashes)}")
    lines.append(f"  Binding channels: {len(generic)}")
    if type_counts:
        lines.append("  Target types: " + ", ".join(f"{name} {count}" for name, count in sorted(type_counts.items())))

    paths = list(grouped.items())
    bone_like = sum(1 for path, _entry in paths if _anim_likely_bone_path(path))
    transform_channels = type_counts.get("Transform", 0)
    if transform_channels and len(paths) >= 8 and bone_like >= max(4, len(paths) // 2):
        lines.append("  Likely motion system: skeletal/rig animation (many nested bone-style Transform paths)")
    elif transform_channels and type_counts.get("GameObject", 0):
        lines.append("  Likely motion system: Transform animation plus object visibility switching")
    elif transform_channels:
        lines.append("  Likely motion system: Transform hierarchy animation")
    elif type_counts.get("GameObject", 0):
        lines.append("  Likely motion system: object activation/visibility animation")
    else:
        lines.append("  Likely motion system: component/material property animation")

    if paths:
        lines.append("")
        lines.append(f"  Resolved targets ({len(paths)})")
        for i, (path, entry) in enumerate(paths[:limit_paths]):
            properties = entry["properties"]
            sources = entry["sources"]
            source_text = ""
            if sources:
                bundle_label, source_name = sources[0]
                source_bits = [x for x in (bundle_label, source_name) if x]
                source_text = f"  ({' / '.join(source_bits)})" if source_bits else ""
                if len(sources) > 1:
                    source_text += f"  [+{len(sources)-1} matching hierarchy instance(s)]"
            lines.append(f"    {i}: {path}{source_text}")
            for prop in properties:
                lines.append(f"       • {prop}")
        if len(paths) > limit_paths:
            lines.append(f"    ... {len(paths) - limit_paths} more resolved targets")

    if unresolved:
        lines.append("")
        lines.append(f"  Unresolved target hashes ({len(unresolved)})")
        for path_hash, properties in list(unresolved.items())[:20]:
            lines.append(f"    {path_hash} (0x{path_hash:08X})")
            for prop in properties:
                lines.append(f"       • {prop}")
        if len(unresolved) > 20:
            lines.append(f"    ... {len(unresolved) - 20} more unresolved hashes")
        lines.append("  A hash normally resolves when the matching scene/prefab hierarchy is loaded as a sibling bundle.")
    return lines


def _anim_clip_motion_kind(data: Any, bundle_index: Any | None) -> str:
    binding_const = _get_any(data, "m_ClipBindingConstant", "clipBindingConstant", default=None)
    generic = _as_list(_get_any(binding_const, "genericBindings", "m_GenericBindings", default=None)) if binding_const is not None else []
    if not generic:
        return "unknown"
    hash_index = _anim_build_path_hash_index(bundle_index)
    paths: set[str] = set()
    transform_channels = 0
    active_channels = 0
    other_channels = 0
    for binding in generic:
        type_id = _anim_binding_type_id(binding)
        if type_id == 4:
            transform_channels += 1
        elif type_id == 1 and _anim_binding_property_text(binding).startswith("GameObject active"):
            active_channels += 1
        else:
            other_channels += 1
        try:
            path_hash = int(_get_any(binding, "path", "m_Path", default=0) or 0) & 0xFFFFFFFF
        except Exception:
            path_hash = 0
        for path, _bundle, _source in hash_index.get(path_hash, []):
            paths.add(path)
    bone_like = sum(1 for path in paths if _anim_likely_bone_path(path))
    if transform_channels and len(paths) >= 8 and bone_like >= max(4, len(paths) // 2):
        return "skeletal"
    if transform_channels and active_channels:
        return "transform+visibility"
    if transform_channels:
        return "transform"
    if active_channels:
        return "visibility"
    if other_channels:
        return "property"
    return "unknown"


def _anim_offset_data(value: Any) -> Any:
    return _get_any(value, "data", default=value) if value is not None else None


def _anim_muscle_storage(data: Any) -> tuple[Any, Any, Any, Any]:
    muscle = _get_any(data, "m_MuscleClip", "muscleClip", default=None)
    clip_ptr = _get_any(muscle, "m_Clip", "clip", default=None) if muscle is not None else None
    clip = _anim_offset_data(clip_ptr)
    dense = _get_any(clip, "m_DenseClip", "denseClip", default=None) if clip is not None else None
    constant = _get_any(clip, "m_ConstantClip", "constantClip", default=None) if clip is not None else None
    stream = _get_any(clip, "m_StreamedClip", "streamedClip", default=None) if clip is not None else None
    return muscle, dense, constant, stream


def _anim_muscle_duration(data: Any) -> tuple[float | None, float | None, bool | None]:
    muscle, _dense, _constant, _stream = _anim_muscle_storage(data)
    if muscle is None:
        return None, None, None
    start = _anim_safe_float(_get_any(muscle, "m_StartTime", "startTime", default=None))
    stop = _anim_safe_float(_get_any(muscle, "m_StopTime", "stopTime", default=None))
    loop = _get_any(muscle, "m_LoopTime", "loopTime", default=None)
    return start, stop, bool(loop) if loop is not None else None



def _anim_path_depth(path: str) -> int:
    if not path or path == "<root>":
        return 0
    return len([part for part in str(path).split("/") if part])


def _anim_root_name(path: str) -> str:
    if not path or path == "<root>":
        return "<root>"
    return str(path).split("/", 1)[0] or "<root>"


def _anim_likely_bone_path(path: str) -> bool:
    low = str(path).lower()
    hints = (
        "armature", "bone", "spine", "neck", "head", "jaw", "tail",
        "leg", "knee", "foot", "toe", "arm", "hand", "finger", "wing",
        "pelvis", "hip", "shoulder", "elbow", "pole", "master",
    )
    return any(h in low for h in hints) or _anim_path_depth(path) >= 4


def _anim_motion_summary_lines(data: Any, curve_groups: list[tuple[str, list[Any]]], sample_rate: Any, duration_hint: float | None) -> list[str]:
    """Create a learner-friendly summary before dumping individual animation curves."""
    rows: list[dict[str, Any]] = []
    path_stats: dict[str, dict[str, Any]] = {}
    total_curve_channels = 0
    total_keys = 0

    for group_name, items in curve_groups:
        if not items:
            continue
        total_curve_channels += len(items)
        for item in items:
            keys = _anim_collect_keyframes(item)
            key_count = len(keys)
            total_keys += key_count
            path = _anim_target_path(item)
            prop = _anim_property_name(item, group_name)
            rows.append({"group": group_name, "path": path, "prop": prop, "keys": key_count})
            stat = path_stats.setdefault(path, {"keys": 0, "curves": 0, "groups": set(), "props": set()})
            stat["keys"] += key_count
            stat["curves"] += 1
            stat["groups"].add(group_name)
            if prop not in (None, "", "-"):
                stat["props"].add(str(prop))

    if not rows:
        return []

    paths = sorted(path_stats)
    root_counts: dict[str, int] = {}
    for path in paths:
        root = _anim_root_name(path)
        root_counts[root] = root_counts.get(root, 0) + 1

    transform_curve_count = sum(1 for r in rows if str(r["group"]).startswith(("Position", "Rotation", "Euler", "Scale")))
    pptr_count = len(_anim_curve_collection(data, "m_PPtrCurves", "pptrCurves", "pptr_curves"))
    float_count = len(_anim_curve_collection(data, "m_FloatCurves", "floatCurves", "float_curves"))
    bone_like = sum(1 for path in paths if _anim_likely_bone_path(path))

    likely_type = "transform/object animation"
    if bone_like >= max(3, len(paths) // 3):
        likely_type = "skeletal / armature animation"
    elif pptr_count:
        likely_type = "object-reference / swap animation"
    elif float_count and not transform_curve_count:
        likely_type = "property/material/script-field animation"

    density = "sparse keyframes / tweened motion"
    if duration_hint and sample_rate:
        try:
            frames = float(duration_hint) * float(sample_rate)
            keys_per_frame = total_keys / max(frames, 1.0)
            if keys_per_frame > 1.0:
                density = "dense baked motion"
            elif keys_per_frame > 0.25:
                density = "moderately keyed motion"
        except Exception:
            pass
    elif total_keys > total_curve_channels * 20:
        density = "dense baked motion"

    lines: list[str] = []
    lines.append("")
    lines.append("🧭 Motion summary")
    lines.append(f"  Likely clip role: {likely_type}")
    lines.append(f"  Animated target paths: {len(paths)}")
    lines.append(f"  Curve channels: {total_curve_channels}")
    lines.append(f"  Total exposed keyframes: {total_keys}")
    lines.append(f"  Motion style: {density}")
    if root_counts:
        roots = sorted(root_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        lines.append("  Main root target(s): " + ", ".join(f"{name} ({count})" for name, count in roots))
    if bone_like:
        lines.append(f"  Bone/armature-like paths: {bone_like}")

    busiest = sorted(path_stats.items(), key=lambda kv: (-kv[1]["keys"], kv[0]))[:8]
    if busiest:
        lines.append("  Busiest animated paths:")
        for path, stat in busiest:
            groups = ", ".join(sorted(str(g).replace(" curves", "") for g in stat["groups"]))
            lines.append(f"    {path}: {stat['keys']} keys across {stat['curves']} curve(s) [{groups}]")

    lines.append("")
    lines.append("🧠 How to read this")
    if likely_type.startswith("skeletal"):
        lines.append("  This looks like a skeleton/armature clip: the mesh is the visible skin, while hidden bones such as legs, knees, feet, neck or tail are keyframed over time.")
    else:
        lines.append("  This clip stores keyframes for objects or properties. Unity interpolates between those values at runtime, similar to tweening.")
    lines.append("  Paths with only 2 keys usually hold a start/end or constant value. Paths with hundreds of keys are often baked motion exported from a DCC tool such as Blender/Maya.")
    return lines

def _anim_event_lines(data: Any, limit: int = 24) -> list[str]:
    events = _anim_curve_collection(data, "m_Events", "events")
    lines: list[str] = []
    if not events:
        return lines
    lines.append("")
    lines.append(f"🔔 Animation events ({len(events)})")
    for i, ev in enumerate(events[:limit]):
        time = _get_any(ev, "time", "m_Time", default=None)
        fn = _get_any(ev, "functionName", "m_FunctionName", "function_name", default="")
        string_param = _get_any(ev, "stringParameter", "m_StringParameter", default=None)
        float_param = _get_any(ev, "floatParameter", "m_FloatParameter", default=None)
        int_param = _get_any(ev, "intParameter", "m_IntParameter", default=None)
        params = []
        if string_param not in (None, ""):
            params.append(f"string={string_param}")
        if float_param not in (None, 0, 0.0):
            params.append(f"float={float_param}")
        if int_param not in (None, 0):
            params.append(f"int={int_param}")
        param_text = " (" + ", ".join(params) + ")" if params else ""
        lines.append(f"  {i}: t={_fmt_float(time)}s  {fn or '<function>'}{param_text}")
    if len(events) > limit:
        lines.append(f"  ... {len(events) - limit} more events")
    return lines




def _anim_component_bool_text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    try:
        iv = int(value)
        if iv in (0, 1):
            return "Yes" if iv else "No"
    except Exception:
        pass
    return str(value)


ANIMATION_WRAP_MODE_NAMES = {
    0: "Default",
    1: "Once",
    2: "Loop",
    4: "PingPong",
    8: "ClampForever",
}

ANIMATION_CULLING_TYPE_NAMES = {
    0: "Always animate",
    1: "Based on renderers",
    2: "Based on clip bounds",
    3: "Based on user bounds",
}


def _enum_name(value: Any, names: dict[int, str]) -> str:
    if value is None:
        return "-"
    try:
        iv = int(value)
    except Exception:
        return str(value)
    label = names.get(iv)
    return f"{label} ({iv})" if label else str(iv)


def _animation_clip_brief(rec: Any | None) -> tuple[str, str, str, str]:
    """Return duration, fps, legacy, wrap for a resolved AnimationClip record."""
    if rec is None or getattr(rec, "type_name", "") != "AnimationClip":
        return "-", "-", "-", "-"
    data = _read(rec)
    if data is None:
        return "-", "-", "-", "-"
    fps = _get_any(data, "m_SampleRate", "sampleRate", "sample_rate", default=None)
    legacy = _get_any(data, "m_Legacy", "legacy", default=None)
    wrap = _get_any(data, "m_WrapMode", "wrapMode", default=None)

    max_t = None
    for names in (
        ("m_PositionCurves", "positionCurves", "position_curves"),
        ("m_RotationCurves", "rotationCurves", "rotation_curves"),
        ("m_EulerCurves", "eulerCurves", "euler_curves"),
        ("m_ScaleCurves", "scaleCurves", "scale_curves"),
        ("m_FloatCurves", "floatCurves", "float_curves"),
        ("m_PPtrCurves", "pptrCurves", "pptr_curves"),
        ("m_CompressedRotationCurves", "compressedRotationCurves"),
    ):
        for item in _anim_curve_collection(data, *names):
            for key in _anim_collect_keyframes(item):
                t, _v = _anim_key_time_value(key)
                if t is not None:
                    max_t = t if max_t is None else max(max_t, t)
    for line in _anim_event_lines(data):
        if "t=" in line:
            try:
                part = line.split("t=", 1)[1].split("s", 1)[0]
                val = float(part)
                max_t = val if max_t is None else max(max_t, val)
            except Exception:
                pass

    _start, stop, _loop = _anim_muscle_duration(data)
    if stop is not None:
        max_t = stop if max_t is None else max(max_t, stop)
    duration = f"{max_t:.3f}s" if max_t is not None else "-"
    fps_text = f"{_fmt_float(fps)} fps" if fps is not None else "-"
    legacy_text = _anim_component_bool_text(legacy) if legacy is not None else "-"
    wrap_text = _enum_name(wrap, ANIMATION_WRAP_MODE_NAMES) if wrap is not None else "-"
    return duration, fps_text, legacy_text, wrap_text


def _animation_collect_clip_pptrs(data: Any) -> list[tuple[str, Any]]:
    """Collect default/list clip PPtrs exposed by the legacy Animation component."""
    out: list[tuple[str, Any]] = []
    default_clip = _get_any(data, "m_Animation", "animation", "m_Clip", "clip", default=None)
    if default_clip is not None:
        out.append(("Default", default_clip))

    for field_name in ("m_Animations", "animations", "m_Clips", "clips"):
        items = _as_list(_get_any(data, field_name, default=None))
        for i, item in enumerate(items):
            # Some decoders expose the PPtr directly; others wrap it in fields.
            pptr = _get_any(item, "m_Clip", "clip", "animation", "m_Animation", default=item)
            out.append((f"List {i}", pptr))

    seen: set[tuple[int | None, int | None, str]] = set()
    unique: list[tuple[str, Any]] = []
    for role, pptr in out:
        key = (_pptr_file_id(pptr), _pptr_path_id(pptr), role)
        # Keep Default and List rows separate if Unity exposed both, but avoid exact duplicates.
        if key in seen:
            continue
        seen.add(key)
        unique.append((role, pptr))
    return unique


def _describe_animation_component(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🎬 Animation component inspector"]
    if data is None:
        lines.append("Unable to read Animation component data.")
        return lines

    go = _get_any(data, "m_GameObject", "game_object", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    play_auto = _get_any(data, "m_PlayAutomatically", "playAutomatically", "play_automatically", default=None)
    animate_physics = _get_any(data, "m_AnimatePhysics", "animatePhysics", "animate_physics", default=None)
    wrap_mode = _get_any(data, "m_WrapMode", "wrapMode", "wrap_mode", default=None)
    culling = _get_any(data, "m_CullingType", "cullingType", "culling_type", default=None)
    bounds = _get_any(data, "m_UserAABB", "userAABB", "user_aabb", default=None)

    lines.append("This is the legacy Unity Animation component on a GameObject. It chooses which AnimationClip(s) can play on this object.")
    lines.append("The AnimationClip stores the keyframes; this component stores playback settings and the clip list.")
    lines.append("")
    lines.append("🎛 Playback settings")
    lines.append(f"  Enabled: {_anim_component_bool_text(enabled)}")
    lines.append(f"  Play automatically: {_anim_component_bool_text(play_auto)}")
    lines.append(f"  Animate physics: {_anim_component_bool_text(animate_physics)}")
    lines.append(f"  Wrap mode: {_enum_name(wrap_mode, ANIMATION_WRAP_MODE_NAMES)}")
    lines.append(f"  Culling type: {_enum_name(culling, ANIMATION_CULLING_TYPE_NAMES)}")

    if bounds is not None:
        centre = _get_any(bounds, "m_Center", "center", default=None)
        extent = _get_any(bounds, "m_Extent", "extent", "m_Extents", "extents", default=None)
        if centre is not None or extent is not None:
            lines.append(f"  User bounds centre: {_fmt_vec3(centre)}")
            lines.append(f"  User bounds extent: {_fmt_vec3(extent)}")

    lines.append("")
    lines.append("🎲 Owner object")
    lines.append(f"  GameObject: {_pptr_text(go, bundle_index)}")
    lines.extend(_pptr_resolution_lines("GameObject", go, bundle_index, indent="  "))

    clip_refs = _animation_collect_clip_pptrs(data)
    lines.append("")
    lines.append(f"🎞 Animation clips ({len(clip_refs)})")
    if clip_refs:
        for i, (role, pptr) in enumerate(clip_refs[:80]):
            rec = _resolve_record(bundle_index, pptr)
            duration, fps, legacy, clip_wrap = _animation_clip_brief(rec)
            target = _pptr_text(pptr, bundle_index)
            bits = []
            if duration != "-":
                bits.append(f"duration {duration}")
            if fps != "-":
                bits.append(fps)
            if legacy != "-":
                bits.append(f"legacy {legacy}")
            if clip_wrap != "-":
                bits.append(f"clip wrap {clip_wrap}")
            suffix = f"  ({', '.join(bits)})" if bits else ""
            lines.append(f"  {i}: {role}: {target}{suffix}")
        if len(clip_refs) > 80:
            lines.append(f"  ... {len(clip_refs) - 80} more clips")
    else:
        lines.append("  No AnimationClip references were exposed by the decoder.")

    # Helpful quick classification.
    clip_count = len(clip_refs)
    default_pid = _pptr_path_id(_get_any(data, "m_Animation", "animation", "m_Clip", "clip", default=None))
    lines.append("")
    lines.append("🧭 Animation role summary")
    if clip_count == 0:
        lines.append("  This component exposes playback settings, but no clip list was decoded here.")
    elif clip_count == 1:
        lines.append("  Single-clip legacy animation setup. The GameObject probably plays one default motion or ambient action.")
    else:
        lines.append("  Multi-clip legacy animation setup. Scripts or old Unity animation calls can select clips from this list by name.")
    if default_pid not in (None, 0):
        lines.append(f"  Default clip PathID: {default_pid}")
    if play_auto in (True, 1):
        lines.append("  Play automatically is enabled, so Unity may start the default clip when this object becomes active.")
    elif play_auto in (False, 0):
        lines.append("  Play automatically is disabled, so a script/controller probably starts clips manually.")

    fields = _anim_object_fields(data)
    interesting = [f for f in fields if f.startswith("m_")][:28]
    if interesting:
        lines.append("")
        lines.append("🧾 Exposed fields")
        lines.append("  " + ", ".join(interesting) + (" ..." if len([f for f in fields if f.startswith('m_')]) > 28 else ""))

    lines.append("")
    lines.append("🧠 Animation component insight")
    lines.append("This is Unity's older/legacy Animation component, commonly seen on simple animated props, creatures, course objects and older assets.")
    lines.append("For modern Mecanim setups, an Animator component plus AnimatorController usually performs this role. For legacy setups, Animation directly owns the clip list and playback flags.")
    lines.append("So the chain is: GameObject → Animation component → AnimationClip keyframes → animated transforms/bones/material properties.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def _describe_animation_clip(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🎬 Animation Clip inspector"]
    if data is None:
        lines.append("Unable to read AnimationClip data.")
        return lines

    sample_rate = _get_any(data, "m_SampleRate", "sampleRate", "sample_rate", default=None)
    wrap_mode = _get_any(data, "m_WrapMode", "wrapMode", default=None)
    legacy = _get_any(data, "m_Legacy", "legacy", default=None)
    compressed = _get_any(data, "m_Compressed", "compressed", default=None)
    high_quality = _get_any(data, "m_UseHighQualityCurve", "useHighQualityCurve", default=None)

    if sample_rate is not None:
        lines.append(f"Sample rate: {_fmt_float(sample_rate)} fps")
    if wrap_mode is not None:
        lines.append(f"Wrap mode: {wrap_mode}")
    if legacy is not None:
        lines.append(f"Legacy clip: {legacy}")
    if compressed is not None:
        lines.append(f"Compressed: {compressed}")
    if high_quality is not None:
        lines.append(f"High quality curves: {high_quality}")

    muscle_start, muscle_stop, loop_time = _anim_muscle_duration(data)
    if muscle_start is not None or muscle_stop is not None or loop_time is not None:
        lines.append("")
        lines.append("⏱ Timeline")
        if muscle_start is not None:
            lines.append(f"  Start: {muscle_start:.3f}s")
        if muscle_stop is not None:
            lines.append(f"  Stop / duration: {muscle_stop:.3f}s")
        if loop_time is not None:
            lines.append(f"  Loop time: {loop_time}")

    durations: list[float] = []

    curve_groups = [
        ("Position curves", _anim_curve_collection(data, "m_PositionCurves", "positionCurves", "position_curves")),
        ("Rotation curves", _anim_curve_collection(data, "m_RotationCurves", "rotationCurves", "rotation_curves")),
        ("Euler curves", _anim_curve_collection(data, "m_EulerCurves", "eulerCurves", "euler_curves")),
        ("Scale curves", _anim_curve_collection(data, "m_ScaleCurves", "scaleCurves", "scale_curves")),
        ("Float/property curves", _anim_curve_collection(data, "m_FloatCurves", "floatCurves", "float_curves")),
        ("Object reference / PPtr curves", _anim_curve_collection(data, "m_PPtrCurves", "pptrCurves", "pptr_curves")),
        ("Compressed rotation curves", _anim_curve_collection(data, "m_CompressedRotationCurves", "compressedRotationCurves")),
    ]

    # Estimate duration before the verbose curve dump so the summary can mention motion density.
    for _title, _items in curve_groups:
        for _item in _items:
            for _key in _anim_collect_keyframes(_item):
                _t, _v = _anim_key_time_value(_key)
                if _t is not None:
                    durations.append(_t)
    duration_hint = max(durations) if durations else None
    lines.extend(_anim_motion_summary_lines(data, curve_groups, sample_rate, duration_hint))

    lines.append("")
    lines.append("📈 Curves / animated properties")

    any_curves = False
    for title, items in curve_groups:
        mt = _anim_collection_summary(lines, title, items)
        if items:
            any_curves = True
        if mt is not None:
            durations.append(mt)

    if not any_curves:
        lines.append("  No ordinary curve arrays are stored in this clip.")
        lines.append("  Generic Transform channels may instead be stored in StreamedClip data; UBE v2.2f can decode those for preview.")
        lines.append("  Dense/constant, humanoid muscle, blend-shape, material, or other property curves may still require later support.")

    binding_const = _get_any(data, "m_ClipBindingConstant", "clipBindingConstant", default=None)
    if binding_const is not None:
        generic = _as_list(_get_any(binding_const, "genericBindings", "m_GenericBindings", default=None))
        pptr_mapping = _as_list(_get_any(binding_const, "pptrCurveMapping", "m_PPtrCurveMapping", default=None))
        if generic or pptr_mapping:
            lines.append("")
            lines.append("🔗 Binding constant")
            if generic:
                lines.append(f"  Generic bindings: {len(generic)}")
                for i, b in enumerate(generic[:16]):
                    path = _get_any(b, "path", "m_Path", default=None)
                    attr = _get_any(b, "attribute", "m_Attribute", default=None)
                    class_id = _anim_binding_type_id(b)
                    flags = _get_any(b, "flags", "m_Flags", default=None)
                    type_name = ANIMATION_BINDING_TYPE_NAMES.get(class_id, f"TypeID {class_id}" if class_id is not None else "-")
                    lines.append(f"    {i}: path/hash {path}, attr {attr} ({_anim_binding_property_text(b)}), target {type_name}, flags {flags}")
                if len(generic) > 16:
                    lines.append(f"    ... {len(generic) - 16} more generic bindings")
            if pptr_mapping:
                lines.append(f"  PPtr curve mappings: {len(pptr_mapping)}")

    lines.extend(_anim_resolved_binding_lines(data, bundle_index))

    muscle_clip, dense, constant, stream = _anim_muscle_storage(data)
    if muscle_clip is not None:
        if any(v is not None for v in (dense, constant, stream)):
            lines.append("")
            lines.append("🧱 Streamed / dense clip storage")
            if dense is not None:
                sample_array = _as_list(_get_any(dense, "m_SampleArray", "sampleArray", default=None))
                frame_count = _get_any(dense, "m_FrameCount", "frameCount", default=None)
                curve_count = _get_any(dense, "m_CurveCount", "curveCount", default=None)
                dense_rate = _get_any(dense, "m_SampleRate", "sampleRate", default=None)
                lines.append(f"  Dense clip: frames {frame_count if frame_count is not None else '-'}, curves {curve_count if curve_count is not None else '-'}, samples {len(sample_array) if sample_array else 0}" + (f", rate {_fmt_float(dense_rate)} fps" if dense_rate is not None else ""))
            if constant is not None:
                consts = _as_list(_get_any(constant, "m_Data", "data", default=None))
                lines.append(f"  Constant clip values: {len(consts)}")
            if stream is not None:
                stream_data = _as_list(_get_any(stream, "m_Data", "data", default=None))
                curve_count = _get_any(stream, "curveCount", "m_CurveCount", default=None)
                lines.append(f"  Streamed clip data words: {len(stream_data)}" + (f", curves {curve_count}" if curve_count is not None else ""))

    event_lines = _anim_event_lines(data)
    lines.extend(event_lines)
    for line in event_lines:
        if "t=" in line:
            try:
                part = line.split("t=", 1)[1].split("s", 1)[0]
                durations.append(float(part))
            except Exception:
                pass

    if muscle_stop is not None:
        durations.append(muscle_stop)
    if durations:
        lines.insert(1, f"Estimated duration: {max(durations):.3f}s")

    # v2.2r: explain clips such as the orange/purple flag variants where
    # Transform animation is intact but the animated branch's MeshFilter is
    # null and visible geometry lives in a separate runtime/culling branch.
    lines.extend(_animation_runtime_linkage_lines(record, data, bundle_index))

    fields = _anim_object_fields(data)
    interesting = [f for f in fields if f.startswith("m_")][:24]
    if interesting:
        lines.append("")
        lines.append("🧾 Exposed fields")
        lines.append("  " + ", ".join(interesting) + (" ..." if len([f for f in fields if f.startswith('m_')]) > 24 else ""))

    lines.append("")
    lines.append("🧠 AnimationClip insight")
    lines.append("An AnimationClip is a timeline of keyframes. It is not script code, but it can drive transforms, materials, sprites, blend shapes, lights, or animatable script fields.")
    if _anim_curve_collection(data, "m_PPtrCurves", "pptrCurves", "pptr_curves"):
        lines.append("This clip includes object-reference curves, so it may swap sprites/materials/textures over time.")
    if _anim_event_lines(data):
        lines.append("This clip has animation events. Those are the script-like calls fired at specific times.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _animctrl_pptr_rec(pptr: Any, bundle_index: Any | None) -> Any | None:
    try:
        return _resolve_record(bundle_index, pptr)
    except Exception:
        return None


def _animctrl_collect_pptrs(obj: Any, max_depth: int = 7, _seen: set[int] | None = None) -> list[Any]:
    """Collect likely Unity PPtr objects from nested controller data."""
    if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
        return []
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return []
    _seen.add(oid)

    if _pptr_path_id(obj) is not None and any(_get_any(obj, n, default=None) is not None for n in ("file_id", "fileID", "m_FileID", "FileID", "path_id", "pathID", "m_PathID", "PathID")):
        return [obj]

    if max_depth <= 0:
        return []

    out: list[Any] = []
    if isinstance(obj, dict):
        values = list(obj.values())
    elif isinstance(obj, (list, tuple)):
        values = list(obj)
    else:
        fields = [
            "m_AnimationClips", "animationClips", "animation_clips",
            "m_AnimatorParameters", "m_Parameters", "parameters",
            "m_Controller", "controller",
            "m_LayerArray", "m_Layers", "layers",
            "m_StateMachineArray", "stateMachineArray", "state_machines",
            "m_StateConstantArray", "stateConstantArray",
            "m_TransitionConstantArray", "transitionConstantArray",
            "m_BlendTreeConstantArray", "blendTreeConstantArray",
            "m_Values", "m_DefaultValues", "values", "defaultValues",
            "m_Motions", "motions", "m_MotionArray", "motionArray",
        ]
        values = []
        for name in fields:
            v = _get_any(obj, name, default=None)
            if v is not None:
                values.append(v)

    for child in values:
        out.extend(_animctrl_collect_pptrs(child, max_depth - 1, _seen))
    return out


def _animctrl_unique_clip_refs(data: Any, bundle_index: Any | None) -> list[tuple[Any, Any | None]]:
    clips: list[Any] = []
    explicit_keys: set[int] = set()
    for holder in (data, _get_any(data, "m_Controller", "controller", default=None)):
        if holder is None:
            continue
        for name in ("m_AnimationClips", "animationClips", "animation_clips", "m_Motions", "motions"):
            items = _as_list(_get_any(holder, name, default=None))
            clips.extend(items)
            for item in items:
                explicit_keys.add(id(item))
    clips.extend(_animctrl_collect_pptrs(data))

    out: list[tuple[Any, Any | None]] = []
    seen: set[tuple[int | None, int | None]] = set()
    for pptr in clips:
        pid = _pptr_path_id(pptr)
        fid = _pptr_file_id(pptr)
        key = (fid, pid)
        if pid in (None, 0) or key in seen:
            continue
        rec = _animctrl_pptr_rec(pptr, bundle_index)
        if rec is not None and getattr(rec, "type_name", "") != "AnimationClip":
            continue
        if rec is None and id(pptr) not in explicit_keys:
            continue
        seen.add(key)
        out.append((pptr, rec))
    return out


def _animctrl_tos_map(data: Any) -> dict[int, str]:
    out: dict[int, str] = {}
    for holder in (data, _get_any(data, "m_Controller", "controller", default=None)):
        if holder is None:
            continue
        for name in ("m_TOS", "tos", "TOS"):
            items = _as_list(_get_any(holder, name, default=None))
            for item in items:
                k, v = _pair_key_value(item)
                try:
                    kk = int(k)
                except Exception:
                    continue
                if v not in (None, ""):
                    out[kk] = str(v)
    return out


def _animctrl_hash_text(value: Any, tos: dict[int, str]) -> str:
    if value in (None, ""):
        return "-"
    try:
        i = int(value)
    except Exception:
        return str(value)
    if i in tos:
        return f"{i} → {tos[i]}"
    return str(i)


def _animctrl_parameter_lines(data: Any, tos: dict[int, str], limit: int = 32) -> list[str]:
    lines: list[str] = []
    holders = [data, _get_any(data, "m_Controller", "controller", default=None)]
    params: list[Any] = []
    for holder in holders:
        if holder is None:
            continue
        for name in ("m_AnimatorParameters", "m_Parameters", "parameters", "animatorParameters"):
            params.extend(_as_list(_get_any(holder, name, default=None)))
    if not params:
        return lines
    lines.append("")
    lines.append(f"🎚 Parameters ({len(params)})")
    for i, p in enumerate(params[:limit]):
        name = _get_any(p, "m_Name", "name", "Name", default=None)
        name_id = _get_any(p, "m_NameID", "nameID", "name_id", default=None)
        typ = _get_any(p, "m_Type", "type", "Type", default=None)
        default_float = _get_any(p, "m_DefaultFloat", "defaultFloat", default=None)
        default_int = _get_any(p, "m_DefaultInt", "defaultInt", default=None)
        default_bool = _get_any(p, "m_DefaultBool", "defaultBool", default=None)
        shown_name = str(name) if name not in (None, "") else _animctrl_hash_text(name_id, tos)
        bits = [f"type {typ}" if typ is not None else "type -"]
        if default_float not in (None, 0, 0.0):
            bits.append(f"float {_fmt_float(default_float)}")
        if default_int not in (None, 0):
            bits.append(f"int {default_int}")
        if default_bool not in (None, False):
            bits.append(f"bool {default_bool}")
        lines.append(f"  {i}: {shown_name}  ({', '.join(bits)})")
    if len(params) > limit:
        lines.append(f"  ... {len(params) - limit} more parameters")
    return lines


def _animctrl_layer_state_lines(data: Any, tos: dict[int, str], limit: int = 16) -> list[str]:
    lines: list[str] = []
    ctrl = _get_any(data, "m_Controller", "controller", default=None)
    if ctrl is None:
        return lines

    layers = _as_list(_get_any(ctrl, "m_LayerArray", "layerArray", "m_Layers", "layers", default=None))
    state_machines = _as_list(_get_any(ctrl, "m_StateMachineArray", "stateMachineArray", "stateMachines", default=None))
    if layers:
        lines.append("")
        lines.append(f"🧱 Layers ({len(layers)})")
        for i, layer in enumerate(layers[:limit]):
            sm_index = _get_any(layer, "m_StateMachineIndex", "stateMachineIndex", default=None)
            weight = _get_any(layer, "m_DefaultWeight", "defaultWeight", default=None)
            blend = _get_any(layer, "m_LayerBlendingMode", "layerBlendingMode", default=None)
            ik = _get_any(layer, "m_IKPass", "ikPass", default=None)
            synced = _get_any(layer, "m_SyncedLayerIndex", "syncedLayerIndex", default=None)
            name = _get_any(layer, "m_Name", "name", default=None)
            label = str(name) if name not in (None, "") else f"Layer {i}"
            bits = []
            if sm_index is not None:
                bits.append(f"state machine {sm_index}")
            if weight is not None:
                bits.append(f"weight {_fmt_float(weight)}")
            if blend is not None:
                bits.append(f"blend {blend}")
            if ik is not None:
                bits.append(f"IK {ik}")
            if synced not in (None, -1):
                bits.append(f"synced {synced}")
            lines.append(f"  {i}: {label}" + (f"  ({', '.join(bits)})" if bits else ""))
        if len(layers) > limit:
            lines.append(f"  ... {len(layers) - limit} more layers")

    if state_machines:
        lines.append("")
        lines.append(f"🔀 State machines ({len(state_machines)})")
        for i, sm in enumerate(state_machines[:limit]):
            states = _as_list(_get_any(sm, "m_StateConstantArray", "stateConstantArray", "states", default=None))
            any_trans = _as_list(_get_any(sm, "m_AnyStateTransitionConstantArray", "anyStateTransitionConstantArray", default=None))
            entry_trans = _as_list(_get_any(sm, "m_EntryTransitions", "entryTransitions", default=None))
            default_state = _get_any(sm, "m_DefaultState", "defaultState", default=None)
            lines.append(f"  {i}: states {len(states)}, any-state transitions {len(any_trans)}, entry transitions {len(entry_trans)}, default {_animctrl_hash_text(default_state, tos)}")
            for j, st in enumerate(states[:8]):
                name_id = _get_any(st, "m_NameID", "nameID", "name_id", default=None)
                path_id = _get_any(st, "m_PathID", "pathID", "path_id", default=None)
                tag_id = _get_any(st, "m_TagID", "tagID", "tag_id", default=None)
                speed = _get_any(st, "m_Speed", "speed", default=None)
                blend_index = _get_any(st, "m_BlendTreeConstantIndex", "blendTreeConstantIndex", default=None)
                trans = _as_list(_get_any(st, "m_TransitionConstantArray", "transitionConstantArray", default=None))
                state_name = _animctrl_hash_text(name_id, tos)
                bits = []
                if path_id not in (None, 0):
                    bits.append(f"path {_animctrl_hash_text(path_id, tos)}")
                if tag_id not in (None, 0):
                    bits.append(f"tag {_animctrl_hash_text(tag_id, tos)}")
                if speed not in (None, 1, 1.0):
                    bits.append(f"speed {_fmt_float(speed)}")
                if blend_index not in (None, -1):
                    bits.append(f"motion/blend {blend_index}")
                if trans:
                    bits.append(f"transitions {len(trans)}")
                lines.append(f"      state {j}: {state_name}" + (f"  ({', '.join(bits)})" if bits else ""))
            if len(states) > 8:
                lines.append(f"      ... {len(states) - 8} more states")
        if len(state_machines) > limit:
            lines.append(f"  ... {len(state_machines) - limit} more state machines")
    return lines


def _animctrl_clip_lines(data: Any, bundle_index: Any | None, limit: int = 48) -> list[str]:
    clip_refs = _animctrl_unique_clip_refs(data, bundle_index)
    lines: list[str] = [""]
    if clip_refs:
        lines.append(f"🎞 Animation clips / motions ({len(clip_refs)})")
        for i, (pptr, rec) in enumerate(clip_refs[:limit]):
            if rec is not None:
                where = _external_bundle_name(bundle_index, getattr(rec, "path_id", None))
                suffix = f"  (external: {where})" if where else ""
                lines.append(f"  {i}: Animation Clip - {rec.name}  (PathID {rec.path_id}){suffix}")
            else:
                lines.append(f"  {i}: {_pptr_text(pptr, bundle_index)}")
        if len(clip_refs) > limit:
            lines.append(f"  ... {len(clip_refs) - limit} more clips/motions")
    else:
        lines.append("🎞 Animation clips / motions")
        lines.append("  No direct AnimationClip references were exposed by the decoder.")
    return lines


def _animctrl_exposed_fields_lines(data: Any) -> list[str]:
    fields = _anim_object_fields(data)
    interesting = [f for f in fields if f.startswith("m_")][:28]
    if not interesting:
        return []
    lines = ["", "🧾 Exposed fields"]
    lines.append("  " + ", ".join(interesting) + (" ..." if len([f for f in fields if f.startswith('m_')]) > 28 else ""))
    return lines


ANIMATOR_CULLING_MODE_NAMES = {
    0: "Always animate",
    1: "Cull update transforms",
    2: "Cull completely",
}

ANIMATOR_UPDATE_MODE_NAMES = {
    0: "Normal",
    1: "Animate physics / fixed update",
    2: "Unscaled time",
}


def _describe_animator(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🎛 Animator component inspector"]
    if data is None:
        lines.append("Unable to read Animator data.")
        return lines

    go = _get_any(data, "m_GameObject", "gameObject", default=None)
    controller = _get_any(data, "m_Controller", "controller", default=None)
    avatar = _get_any(data, "m_Avatar", "avatar", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    apply_root = _get_any(data, "m_ApplyRootMotion", "applyRootMotion", default=None)
    has_hierarchy = _get_any(data, "m_HasTransformHierarchy", "hasTransformHierarchy", default=None)
    culling = _get_any(data, "m_CullingMode", "cullingMode", default=None)
    update = _get_any(data, "m_UpdateMode", "updateMode", default=None)
    animate_physics = _get_any(data, "m_AnimatePhysics", "animatePhysics", default=None)
    const_opt = _get_any(data, "m_AllowConstantClipSamplingOptimization", "allowConstantClipSamplingOptimization", default=None)

    lines.append("This is the modern Unity/Mecanim playback component attached to a GameObject.")
    lines.append("")
    lines.append("🎲 Owner and animation assets")
    lines.append(f"  GameObject: {_pptr_text(go, bundle_index)}")
    lines.append(f"  Controller: {_pptr_text(controller, bundle_index)}")
    lines.extend(_pptr_resolution_lines("Controller", controller, bundle_index, indent="  "))
    lines.append(f"  Avatar: {_pptr_text(avatar, bundle_index)}")

    lines.append("")
    lines.append("⚙ Playback settings")
    lines.append(f"  Enabled: {_anim_component_bool_text(enabled)}")
    lines.append(f"  Apply root motion: {_anim_component_bool_text(apply_root)}")
    lines.append(f"  Has Transform hierarchy: {_anim_component_bool_text(has_hierarchy)}")
    lines.append(f"  Culling: {_enum_name(culling, ANIMATOR_CULLING_MODE_NAMES)}")
    lines.append(f"  Update mode: {_enum_name(update, ANIMATOR_UPDATE_MODE_NAMES)}")
    if animate_physics is not None:
        lines.append(f"  Animate physics: {_anim_component_bool_text(animate_physics)}")
    if const_opt is not None:
        lines.append(f"  Constant-clip sampling optimisation: {_anim_component_bool_text(const_opt)}")

    controller_rec = _resolve_record(bundle_index, controller)
    clip_refs: list[tuple[Any, Any | None]] = []
    if controller_rec is not None and getattr(controller_rec, "type_name", "") in ("AnimatorController", "AnimatorOverrideController"):
        controller_data = _read(controller_rec)
        if controller_data is not None:
            clip_refs = _animctrl_unique_clip_refs(controller_data, bundle_index)

    lines.append("")
    lines.append("🎞 Controller motions")
    if clip_refs:
        lines.append(f"  Resolved AnimationClips: {len(clip_refs)}")
        for i, (pptr, clip_rec) in enumerate(clip_refs[:40]):
            if clip_rec is None:
                lines.append(f"  {i}: {_pptr_text(pptr, bundle_index)}")
                continue
            duration, fps, legacy, wrap = _animation_clip_brief(clip_rec)
            bits = []
            if duration != "-":
                bits.append(duration)
            if fps != "-":
                bits.append(fps)
            if wrap != "-":
                bits.append(wrap)
            lines.append(f"  {i}: {clip_rec.name}  (PathID {clip_rec.path_id})" + (f" — {', '.join(bits)}" if bits else ""))
        if len(clip_refs) > 40:
            lines.append(f"  ... {len(clip_refs) - 40} more clips")
    elif _pptr_path_id(controller) in (None, 0):
        lines.append("  No controller assigned. The Animator exists, but it cannot play a controller state machine in this serialized setup.")
    elif controller_rec is None:
        lines.append("  Controller is external but not present in the currently loaded sibling bundles.")
    else:
        lines.append("  Controller resolved, but no direct clip references were exposed by the decoder.")

    lines.append("")
    lines.append("🧭 Motion-source summary")
    clip_kinds: set[str] = set()
    for _pptr, clip_rec in clip_refs:
        if clip_rec is None:
            continue
        clip_data = _read(clip_rec)
        if clip_data is not None:
            clip_kinds.add(_anim_clip_motion_kind(clip_data, bundle_index))
    if "skeletal" in clip_kinds:
        lines.append("  Controller clips target many nested bone-style Transform paths: skeletal/rig animation.")
    elif "transform+visibility" in clip_kinds:
        lines.append("  Controller clips combine Transform curves with GameObject activation/visibility switching.")
    elif "transform" in clip_kinds:
        lines.append("  Controller clips animate a Transform hierarchy.")
    elif clip_refs and _pptr_path_id(avatar) not in (None, 0):
        lines.append("  Modern Animator + Avatar + controller clips: likely skeletal/humanoid or generic rig animation.")
    elif clip_refs:
        lines.append("  Modern Animator + controller clips: likely generic Transform, UI, or property animation.")
    elif _pptr_path_id(controller) not in (None, 0):
        lines.append("  Modern Animator with an external controller; load the matching common/global bundle to expose its states and clips.")
    else:
        lines.append("  Animator component present without a controller. Motion may be assigned at runtime, overridden by script, or unused.")

    fields = _anim_object_fields(data)
    interesting = [f for f in fields if f.startswith("m_")][:28]
    if interesting:
        lines.append("")
        lines.append("🧾 Exposed fields")
        lines.append("  " + ", ".join(interesting) + (" ..." if len([f for f in fields if f.startswith('m_')]) > 28 else ""))

    lines.append("")
    lines.append("🧠 Animator insight")
    lines.append("The Animator chooses states from an AnimatorController. The controller chooses AnimationClips; the clips contain the actual curves that move transforms, bones, UI or other properties.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_animator_controller(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🎛 Animator Controller inspector"]
    if data is None:
        lines.append("Unable to read AnimatorController data.")
        return lines

    ctrl = _get_any(data, "m_Controller", "controller", default=None)
    tos = _animctrl_tos_map(data)

    lines.append("This asset is the state machine that decides when AnimationClips play.")
    lines.append("AnimationClips contain the keyframes; this controller wires clips into states, layers, parameters and transitions.")

    if ctrl is not None:
        size = _get_any(data, "m_ControllerSize", "controllerSize", default=None)
        if size is not None:
            lines.append(f"Controller size: {size}")

    if tos:
        lines.append("")
        lines.append(f"🗂 String/hash table (TOS): {len(tos)} entries")
        for k, v in list(tos.items())[:18]:
            lines.append(f"  {k}: {v}")
        if len(tos) > 18:
            lines.append(f"  ... {len(tos) - 18} more entries")

    lines.extend(_animctrl_parameter_lines(data, tos))
    lines.extend(_animctrl_layer_state_lines(data, tos))
    lines.extend(_animctrl_clip_lines(data, bundle_index))
    lines.extend(_animctrl_exposed_fields_lines(data))

    lines.append("")
    lines.append("🧠 AnimatorController insight")
    lines.append("Think of this as the animation logic board: parameters and transitions choose states; states play AnimationClips as motions.")
    lines.append("If the detailed state names are hashed, the clip list is still useful because it shows the real animations this controller can play.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _bool_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return "True" if bool(value) else "False"
    except Exception:
        return str(value)


def _layer_mask_text(value: Any) -> str:
    if value is None:
        return "-"
    bits = _get_any(value, "m_Bits", "bits", "value", default=None)
    if bits is None:
        bits = value
    try:
        n = int(bits)
        # Unity all-layers masks often show as -1 or 0xFFFFFFFF.
        if n == -1 or n == 0xFFFFFFFF:
            return "all layers (-1 / 0xFFFFFFFF)"
        return f"{n} (0x{n & 0xFFFFFFFF:08X})"
    except Exception:
        return str(value)


def _rect_text(value: Any) -> str:
    r = _rect_tuple(value)
    if r is None:
        return "-"
    return f"x {_fmt_float(r[0])}, y {_fmt_float(r[1])}, w {_fmt_float(r[2])}, h {_fmt_float(r[3])}"


def _describe_box_collider(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["▭ BoxCollider inspector"]
    if data is None:
        lines.append("Unable to read BoxCollider data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    material = _get_any(data, "m_Material", "material", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    is_trigger = _get_any(data, "m_IsTrigger", "isTrigger", default=None)
    provides_contacts = _get_any(data, "m_ProvidesContacts", "providesContacts", default=None)
    center = _vec3_tuple(_get_any(data, "m_Center", "center", default=None), None)
    size = _vec3_tuple(_get_any(data, "m_Size", "size", default=None), None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Is trigger: {_bool_text(is_trigger)}")
    if provides_contacts is not None:
        lines.append(f"Provides contacts: {_bool_text(provides_contacts)}")
    lines.append(f"Physics material: {_pptr_text(material, bundle_index)}")

    lines.append("")
    lines.append("📐 Local box shape")
    if center is not None:
        lines.append(f"  Center: {_fmt_vec3(center)}")
    else:
        lines.append("  Center: -")
    if size is not None:
        sx, sy, sz = size
        lines.append(f"  Size: {_fmt_vec3(size)}")
        try:
            volume = sx * sy * sz
            lines.append(f"  Local volume estimate: {_fmt_float(volume)}")
        except Exception:
            pass
    else:
        lines.append("  Size: -")
    if center is not None and size is not None:
        mn = (center[0] - size[0] / 2.0, center[1] - size[1] / 2.0, center[2] - size[2] / 2.0)
        mx = (center[0] + size[0] / 2.0, center[1] + size[1] / 2.0, center[2] + size[2] / 2.0)
        lines.append(f"  Local min: {_fmt_vec3(mn)}")
        lines.append(f"  Local max: {_fmt_vec3(mx)}")

    # Unity 6 / newer collider layer override fields. Keep these optional and visible when present.
    layer_priority = _get_any(data, "m_LayerOverridePriority", "layerOverridePriority", default=None)
    include_layers = _get_any(data, "m_IncludeLayers", "includeLayers", default=None)
    exclude_layers = _get_any(data, "m_ExcludeLayers", "excludeLayers", default=None)
    if layer_priority is not None or include_layers is not None or exclude_layers is not None:
        lines.append("")
        lines.append("🧱 Layer overrides")
        if layer_priority is not None:
            lines.append(f"  Priority: {layer_priority}")
        if include_layers is not None:
            lines.append(f"  Include layers: {_layer_mask_text(include_layers)}")
        if exclude_layers is not None:
            lines.append(f"  Exclude layers: {_layer_mask_text(exclude_layers)}")

    fields = [f for f in _anim_object_fields(data) if f.startswith("m_")]
    interesting = [f for f in fields if f not in {"m_GameObject", "m_Enabled", "m_IsTrigger", "m_Material", "m_Center", "m_Size"}]
    if interesting:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(interesting[:24]) + (" ..." if len(interesting) > 24 else ""))

    lines.append("")
    lines.append("🧠 BoxCollider insight")
    lines.append("A BoxCollider is an invisible local-space physics/interaction box. It does not draw the visible mesh; it defines where the object can be clicked, hit, blocked, triggered, or detected.")
    lines.append("The final world-space collider also depends on the GameObject Transform position, rotation and scale.")
    if is_trigger:
        lines.append("Because this is marked as a trigger, it is probably used for detection/events rather than solid collision blocking.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines



# ---------------------------------------------------------------------------
# v1.8t small inspector pack: SpriteMask, line/trail renderers, physics, text,
# and PlayableDirector/Timeline.
# ---------------------------------------------------------------------------

def _enum_number_text(value: Any, names: dict[int, str] | None = None) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
    except Exception:
        return str(value)
    if names and n in names:
        return f"{n} ({names[n]})"
    return str(n)


def _short_field_list(data: Any, skip: set[str] | None = None, limit: int = 28) -> list[str]:
    skip = skip or set()
    fields = [f for f in _anim_object_fields(data) if f.startswith("m_") and f not in skip]
    return fields[:limit] + (["..."] if len(fields) > limit else [])


def _pptr_list_lines(label: str, values: Any, bundle_index: Any | None, limit: int = 12) -> list[str]:
    items = _as_list(values)
    lines = [f"{label}: {len(items)}"]
    for i, item in enumerate(items[:limit]):
        pptr = item
        # Renderer materials often expose dict-like or m_Material entries.
        for key in ("m_Material", "material", "asset", "m_Asset", "m_Source", "source"):
            cand = _get_any(item, key, default=None)
            if cand is not None:
                pptr = cand
                break
        lines.append(f"  {i}: {_pptr_text(pptr, bundle_index)}")
    if len(items) > limit:
        lines.append(f"  ... {len(items) - limit} more")
    return lines


def _describe_sprite_mask(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧩 SpriteMask inspector"]
    if data is None:
        lines.append("Unable to read SpriteMask data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    sprite = _get_any(data, "m_Sprite", "sprite", default=None)
    alpha_cutoff = _get_any(data, "m_AlphaCutoff", "alphaCutoff", default=None)
    custom_range = _get_any(data, "m_IsCustomRangeActive", "isCustomRangeActive", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Sprite used as mask shape: {_pptr_text(sprite, bundle_index)}")
    if alpha_cutoff is not None:
        lines.append(f"Alpha cutoff: {_fmt_float(alpha_cutoff)}")
    if custom_range is not None:
        lines.append(f"Custom sorting range active: {_bool_text(custom_range)}")

    lines.append("")
    lines.append("📊 Sorting / mask range")
    for label, names in (
        ("Front sorting layer", ("m_FrontSortingLayerID", "frontSortingLayerID")),
        ("Front sorting order", ("m_FrontSortingOrder", "frontSortingOrder")),
        ("Back sorting layer", ("m_BackSortingLayerID", "backSortingLayerID")),
        ("Back sorting order", ("m_BackSortingOrder", "backSortingOrder")),
    ):
        value = _get_any(data, *names, default=None)
        if value is not None:
            lines.append(f"  {label}: {value}")

    fields = _short_field_list(data, {
        "m_GameObject", "m_Enabled", "m_Sprite", "m_AlphaCutoff", "m_IsCustomRangeActive",
        "m_FrontSortingLayerID", "m_FrontSortingOrder", "m_BackSortingLayerID", "m_BackSortingOrder"
    })
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 SpriteMask insight")
    lines.append("A SpriteMask is an invisible 2D stencil. It does not draw a visible sprite by itself; it controls which SpriteRenderers are allowed to show through.")
    lines.append("The linked Sprite is the mask shape. UBE previews that Sprite image where it can resolve the reference.")
    lines.append("Artists often use this for UI cut-outs, reveals, soft holes, circular windows, or hiding parts of a 2D sprite layer.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_line_or_trail_renderer(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    is_trail = record.type_name == "TrailRenderer"
    lines: list[str] = ["🧩 TrailRenderer inspector" if is_trail else "🧩 LineRenderer inspector"]
    if data is None:
        lines.append(f"Unable to read {record.type_name} data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    cast = _get_any(data, "m_CastShadows", "castShadows", default=None)
    receive = _get_any(data, "m_ReceiveShadows", "receiveShadows", default=None)
    materials = _get_any(data, "m_Materials", "materials", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    lines.append(f"Enabled: {_bool_text(enabled)}")
    if cast is not None:
        lines.append(f"Cast shadows: {cast}")
    if receive is not None:
        lines.append(f"Receive shadows: {_bool_text(receive)}")

    lines.append("")
    lines.append("🎨 Materials")
    lines.extend(_pptr_list_lines("  Material slots", materials, bundle_index, limit=10))

    lines.append("")
    lines.append("📐 Line / trail shape")
    width_multiplier = _get_any(data, "m_WidthMultiplier", "widthMultiplier", default=None)
    start_width = _get_any(data, "m_StartWidth", "startWidth", default=None)
    end_width = _get_any(data, "m_EndWidth", "endWidth", default=None)
    num_positions = _get_any(data, "m_NumPositions", "numPositions", default=None)
    positions = _get_any(data, "m_Positions", "positions", default=None)
    time = _get_any(data, "m_Time", "time", default=None)
    min_vertex_dist = _get_any(data, "m_MinVertexDistance", "minVertexDistance", default=None)
    autodestruct = _get_any(data, "m_Autodestruct", "autodestruct", default=None)
    alignment = _get_any(data, "m_Alignment", "alignment", default=None)
    texture_mode = _get_any(data, "m_TextureMode", "textureMode", default=None)
    generate_lighting = _get_any(data, "m_GenerateLightingData", "generateLightingData", default=None)

    if width_multiplier is not None:
        lines.append(f"  Width multiplier: {_fmt_float(width_multiplier)}")
    if start_width is not None or end_width is not None:
        lines.append(f"  Start/end width: {_fmt_float(start_width)} / {_fmt_float(end_width)}")
    if num_positions is not None:
        lines.append(f"  Saved position count: {num_positions}")
    elif positions is not None:
        lines.append(f"  Saved position count: {_list_len(positions) or 0}")
    if positions is not None and _as_list(positions):
        for i, pos in enumerate(_as_list(positions)[:6]):
            lines.append(f"    p{i}: {_fmt_vec3(pos)}")
        if len(_as_list(positions)) > 6:
            lines.append(f"    ... {len(_as_list(positions)) - 6} more positions")
    if is_trail:
        if time is not None:
            lines.append(f"  Trail lifetime/time: {_fmt_float(time)}")
        if min_vertex_dist is not None:
            lines.append(f"  Minimum vertex distance: {_fmt_float(min_vertex_dist)}")
        if autodestruct is not None:
            lines.append(f"  Autodestruct: {_bool_text(autodestruct)}")
    if alignment is not None:
        lines.append(f"  Alignment: {_enum_number_text(alignment, {0:'view', 1:'transform Z'})}")
    if texture_mode is not None:
        lines.append(f"  Texture mode: {_enum_number_text(texture_mode, {0:'stretch', 1:'tile', 2:'distribute per segment', 3:'repeat per segment'})}")
    if generate_lighting is not None:
        lines.append(f"  Generate lighting data: {_bool_text(generate_lighting)}")

    fields = _short_field_list(data, {
        "m_GameObject", "m_Enabled", "m_Materials", "m_CastShadows", "m_ReceiveShadows",
        "m_WidthMultiplier", "m_StartWidth", "m_EndWidth", "m_NumPositions", "m_Positions",
        "m_Time", "m_MinVertexDistance", "m_Autodestruct", "m_Alignment", "m_TextureMode", "m_GenerateLightingData"
    })
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 Renderer insight")
    if is_trail:
        lines.append("A TrailRenderer draws a fading ribbon behind a moving object. It is not a normal mesh asset; Unity creates the ribbon geometry at runtime from the object's movement.")
    else:
        lines.append("A LineRenderer draws a strip/ribbon through points. It is often used for lasers, ropes, paths, debug guides, aim lines, lightning, or UI/VR pointers.")
    lines.append("The material provides the colour/texture; width, alignment and texture mode define how the generated strip is drawn.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_rigidbody(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧩 Rigidbody inspector"]
    if data is None:
        lines.append("Unable to read Rigidbody data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    for label, names in (
        ("Mass", ("m_Mass", "mass")),
        ("Drag / linear damping", ("m_Drag", "m_LinearDamping", "drag", "linearDamping")),
        ("Angular drag / damping", ("m_AngularDrag", "m_AngularDamping", "angularDrag", "angularDamping")),
        ("Use gravity", ("m_UseGravity", "useGravity")),
        ("Is kinematic", ("m_IsKinematic", "isKinematic")),
        ("Interpolate", ("m_Interpolate", "interpolate")),
        ("Collision detection", ("m_CollisionDetection", "collisionDetection")),
        ("Constraints", ("m_Constraints", "constraints")),
    ):
        value = _get_any(data, *names, default=None)
        if value is not None:
            if isinstance(value, bool):
                lines.append(f"{label}: {_bool_text(value)}")
            else:
                lines.append(f"{label}: {value}")

    center = _vec3_tuple(_get_any(data, "m_CenterOfMass", "centerOfMass", default=None), None)
    inertia = _vec3_tuple(_get_any(data, "m_InertiaTensor", "inertiaTensor", default=None), None)
    if center is not None or inertia is not None:
        lines.append("")
        lines.append("📐 Mass properties")
        if center is not None:
            lines.append(f"  Center of mass: {_fmt_vec3(center)}")
        if inertia is not None:
            lines.append(f"  Inertia tensor: {_fmt_vec3(inertia)}")

    fields = _short_field_list(data, {"m_GameObject", "m_Mass", "m_Drag", "m_LinearDamping", "m_AngularDrag", "m_AngularDamping",
                                      "m_UseGravity", "m_IsKinematic", "m_Interpolate", "m_CollisionDetection", "m_Constraints",
                                      "m_CenterOfMass", "m_InertiaTensor"})
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 Rigidbody insight")
    lines.append("A Rigidbody makes a GameObject participate in Unity physics. Colliders define the shape; the Rigidbody defines mass, gravity, movement mode and collision behaviour.")
    lines.append("Kinematic bodies are usually controlled by animation/script and push/detect physics without being fully simulated by forces.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_physics_collider(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = [f"🧩 {friendly_type_name(record.type_name)} inspector"]
    if data is None:
        lines.append(f"Unable to read {record.type_name} data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    material = _get_any(data, "m_Material", "material", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    is_trigger = _get_any(data, "m_IsTrigger", "isTrigger", default=None)
    center = _vec3_tuple(_get_any(data, "m_Center", "center", default=None), None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Is trigger: {_bool_text(is_trigger)}")
    lines.append(f"Physics material: {_pptr_text(material, bundle_index)}")

    lines.append("")
    lines.append("📐 Collider shape")
    if center is not None:
        lines.append(f"  Center: {_fmt_vec3(center)}")

    if record.type_name == "SphereCollider":
        radius = _get_any(data, "m_Radius", "radius", default=None)
        lines.append(f"  Radius: {_fmt_float(radius)}")
        try:
            if radius is not None:
                lines.append(f"  Local diameter: {_fmt_float(float(radius) * 2.0)}")
        except Exception:
            pass
    elif record.type_name == "CapsuleCollider":
        radius = _get_any(data, "m_Radius", "radius", default=None)
        height = _get_any(data, "m_Height", "height", default=None)
        direction = _get_any(data, "m_Direction", "direction", default=None)
        dir_names = {0: "X axis", 1: "Y axis", 2: "Z axis"}
        lines.append(f"  Radius: {_fmt_float(radius)}")
        lines.append(f"  Height: {_fmt_float(height)}")
        lines.append(f"  Direction: {_enum_number_text(direction, dir_names)}")
    elif record.type_name == "MeshCollider":
        mesh = _get_any(data, "m_Mesh", "mesh", default=None)
        convex = _get_any(data, "m_Convex", "convex", default=None)
        cooking = _get_any(data, "m_CookingOptions", "cookingOptions", default=None)
        lines.append(f"  Mesh: {_pptr_text(mesh, bundle_index)}")
        lines.append(f"  Convex: {_bool_text(convex)}")
        if cooking is not None:
            lines.append(f"  Cooking options: {cooking}")

    # Common newer layer override fields.
    layer_priority = _get_any(data, "m_LayerOverridePriority", "layerOverridePriority", default=None)
    include_layers = _get_any(data, "m_IncludeLayers", "includeLayers", default=None)
    exclude_layers = _get_any(data, "m_ExcludeLayers", "excludeLayers", default=None)
    if layer_priority is not None or include_layers is not None or exclude_layers is not None:
        lines.append("")
        lines.append("🧾 Layer overrides")
        if layer_priority is not None:
            lines.append(f"  Priority: {layer_priority}")
        if include_layers is not None:
            lines.append(f"  Include layers: {_layer_mask_text(include_layers)}")
        if exclude_layers is not None:
            lines.append(f"  Exclude layers: {_layer_mask_text(exclude_layers)}")

    fields = _short_field_list(data, {"m_GameObject", "m_Material", "m_Enabled", "m_IsTrigger", "m_Center", "m_Radius",
                                      "m_Height", "m_Direction", "m_Mesh", "m_Convex", "m_CookingOptions",
                                      "m_LayerOverridePriority", "m_IncludeLayers", "m_ExcludeLayers"})
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 Collider insight")
    if record.type_name == "MeshCollider":
        lines.append("A MeshCollider uses mesh geometry as the collision shape. It is more accurate but usually heavier than primitive colliders.")
        lines.append("Convex MeshColliders can participate in more dynamic physics interactions; non-convex mesh colliders are often static level collision.")
    elif record.type_name == "SphereCollider":
        lines.append("A SphereCollider is an invisible local-space ball. It is often used for simple physical contact, pickup/detection radius, proximity zones, hit zones or cheap rounded collision.")
        lines.append("UBE previews the sphere from its Center and Radius so you can see the detection/collision volume relative to the owner origin.")
    elif record.type_name == "CapsuleCollider":
        lines.append("A CapsuleCollider is an invisible pill-shaped local-space volume. It is common for characters, hands/controllers, soft rounded hit zones and standing bodies.")
        lines.append("UBE previews the capsule from its Center, Radius, Height and Direction fields.")
    else:
        lines.append("Primitive colliders are invisible physics shapes. They are cheap and often used even when the visible mesh is much more detailed.")
    if is_trigger:
        lines.append("This collider is marked as a trigger, so it is probably used for detection/events rather than solid blocking.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_physic_material(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧩 Physics Material inspector"]
    if data is None:
        lines.append("Unable to read PhysicMaterial data.")
        return lines

    for label, names in (
        ("Dynamic friction", ("dynamicFriction", "m_DynamicFriction")),
        ("Static friction", ("staticFriction", "m_StaticFriction")),
        ("Bounciness", ("bounciness", "m_Bounciness")),
        ("Friction combine", ("frictionCombine", "m_FrictionCombine")),
        ("Bounce combine", ("bounceCombine", "m_BounceCombine")),
    ):
        value = _get_any(data, *names, default=None)
        if value is not None:
            lines.append(f"{label}: {_fmt_float(value) if 'friction' in label.lower() or label == 'Bounciness' else value}")

    fields = _short_field_list(data, set())
    if fields:
        lines.append("")
        lines.append("🧾 Exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 Physics Material insight")
    lines.append("A PhysicMaterial changes how colliders slide and bounce. It is referenced by Collider components; it is not visible by itself.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _textasset_bytes_and_text(data: Any) -> tuple[bytes | None, str | None]:
    raw = _get_any(data, "m_Script", "script", "m_Data", "data", "bytes", default=None)
    if raw is None:
        return None, None
    if isinstance(raw, str):
        return raw.encode("utf-8", "replace"), raw
    if isinstance(raw, (bytes, bytearray)):
        b = bytes(raw)
        # Try UTF-8 first, then a permissive single-byte fallback.
        for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
            try:
                text = b.decode(enc)
                # Avoid presenting mostly binary decode noise as text.
                printable = sum(1 for ch in text[:2000] if ch == "\n" or ch == "\r" or ch == "\t" or ord(ch) >= 32)
                if text and printable / max(1, len(text[:2000])) > 0.85:
                    return b, text
            except Exception:
                pass
        return b, None
    try:
        s = str(raw)
        return s.encode("utf-8", "replace"), s
    except Exception:
        return None, None


def _bytes_from_possible_blob(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, list):
        try:
            if all(isinstance(x, int) for x in value[:32]):
                return bytes(max(0, min(255, int(x))) for x in value)
        except Exception:
            pass
    try:
        # UnityPy sometimes exposes byte arrays through .data or .bytes-like
        # objects.  Keep this conservative so we do not stringify huge objects.
        data = getattr(value, "data", None)
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
    except Exception:
        pass
    return None


def _font_blob_from_data(data: Any) -> bytes | None:
    for name in ("m_FontData", "font_data", "fontData", "m_Data", "data"):
        blob = _bytes_from_possible_blob(_get(data, name, default=None))
        if blob:
            return blob
    return None


def _char_from_code(value: Any) -> str:
    try:
        code = int(value)
    except Exception:
        return "-"
    if 32 <= code <= 126:
        return f"{code} '{chr(code)}'"
    if code:
        return str(code)
    return "-"


def _avatar_role_guess(name: str) -> str:
    low = (name or "").lower()
    if "oculustouch" in low or "quest" in low or "rift" in low or "controller" in low:
        return "VR controller / tracked-hand rig"
    if "hand" in low or "glove" in low or "skeletal" in low:
        return "hand skeleton / glove rig"
    if "humanoid" in low:
        return "humanoid retargeting rig"
    if "avatar" in low and any(k in low for k in ("mario", "luigi", "yoshi", "kong", "robot", "character", "player", "talking")):
        return "character animation rig"
    return "animation rig mapping asset"


def _first_nonempty_list(value: Any, field_names: tuple[str, ...]) -> list[Any]:
    for name in field_names:
        try:
            items = _as_list(_get(value, name, default=None))
            if items:
                return items
        except Exception:
            pass
    return []


def _describe_avatar(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🦴 Avatar inspector"]
    if data is None:
        lines.append("Unable to read Avatar data.")
        return lines

    name = str(_get(data, "m_Name", "name", default=record.name) or record.name or "")
    lines.append(f"Avatar name: {name}")
    lines.append(f"Likely role: {_avatar_role_guess(name)}")

    lines.append("")
    lines.append("🧠 What this asset is")
    lines.append("  Avatar is not the visible character mesh.")
    lines.append("  It is Unity's animation-rig mapping: how bones/transforms are interpreted by Animator, Mecanim retargeting, hand rigs and skinned characters.")

    avatar_obj = _get(data, "m_Avatar", "avatar", default=None)
    human = _get(data, "m_Human", "human", "m_HumanDescription", "humanDescription", default=None)
    skeleton = _get(data, "m_Skeleton", "skeleton", default=None)
    root_motion = _get(data, "m_RootMotionBoneName", "rootMotionBoneName", default=None)
    tos = _get(data, "m_TOS", "tos", default=None)

    lines.append("")
    lines.append("📦 Exposed rig data")
    shown = False
    if root_motion:
        lines.append(f"  Root motion bone: {root_motion}")
        shown = True
    tos_items = _as_list(tos)
    if tos_items:
        lines.append(f"  Transform/name table entries: {len(tos_items):,}")
        shown = True

    skeleton_items = _first_nonempty_list(skeleton, ("m_Node", "m_Nodes", "nodes", "m_Bone", "bones", "m_ID", "ids"))
    if skeleton_items:
        lines.append(f"  Skeleton entries exposed: {len(skeleton_items):,}")
        shown = True
    human_bones = _first_nonempty_list(human, ("m_Human", "human", "m_HumanBone", "humanBones", "m_Bones", "bones"))
    skeleton_bones = _first_nonempty_list(human, ("m_Skeleton", "skeleton", "m_SkeletonBone", "skeletonBones"))
    if human_bones:
        lines.append(f"  Human bone mappings exposed: {len(human_bones):,}")
        shown = True
    if skeleton_bones:
        lines.append(f"  Human skeleton bones exposed: {len(skeleton_bones):,}")
        shown = True

    for label, value in (("Avatar object", avatar_obj), ("Human description", human), ("Skeleton block", skeleton)):
        if value is not None and value not in ("", [], {}):
            if isinstance(value, (str, int, float, bool)):
                lines.append(f"  {label}: {value}")
            else:
                lines.append(f"  {label}: present")
            shown = True

    if not shown:
        lines.append("  UnityPy exposes this Avatar only partially; no detailed bone table was decoded.")
        lines.append("  It is still useful as a relationship target for Animator / SkinnedMeshRenderer debugging.")

    if tos_items:
        lines.append("")
        lines.append("🔤 Transform/name table sample")
        for i, item in enumerate(tos_items[:16], 1):
            lines.append(f"  {i:>2}: {item}")
        if len(tos_items) > 16:
            lines.append(f"  ... {len(tos_items) - 16:,} more entries")

    if human_bones:
        lines.append("")
        lines.append("🧍 Human bone mapping sample")
        for i, bone in enumerate(human_bones[:20], 1):
            bname = _get(bone, "m_BoneName", "boneName", "bone", "name", default=None)
            hname = _get(bone, "m_HumanName", "humanName", "human", default=None)
            limit = _get(bone, "m_Limit", "limit", default=None)
            bits = []
            if hname: bits.append(f"human {hname}")
            if bname: bits.append(f"bone {bname}")
            if limit is not None: bits.append("limits present")
            lines.append(f"  {i:>2}: " + (" | ".join(bits) if bits else str(bone)))
        if len(human_bones) > 20:
            lines.append(f"  ... {len(human_bones) - 20:,} more mappings")

    fields = _short_field_list(data, {"m_Name", "m_Avatar", "m_Human", "m_HumanDescription", "m_Skeleton", "m_TOS"})
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🔎 Debugging notes")
    lines.append("  If a skinned character animates strangely, inspect this Avatar together with Animator, SkinnedMeshRenderer, bind poses and bone Transforms.")
    lines.append("  VR hand/controller rigs often use Avatar assets for left/right skeletal or controller mappings.")
    lines.append("  A render preview would be misleading because Avatar contains rig metadata, not geometry or texture data.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def _describe_font(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🔠 Font inspector"]
    if data is None:
        lines.append("Unable to read Font data.")
        return lines

    font_name = _get(data, "m_Name", "name", default=record.name) or record.name
    lines.append(f"Font name: {font_name}")

    font_data = _font_blob_from_data(data)
    lines.append(f"Embedded font data: {human_bytes(len(font_data)) if font_data else '-'}")
    if font_data:
        sig = font_data[:4]
        if sig == b"OTTO":
            lines.append("Font file signature: OpenType/CFF (OTTO)")
        elif sig == b"\\x00\\x01\\x00\\x00":
            lines.append("Font file signature: TrueType")
        elif sig == b"ttcf":
            lines.append("Font file signature: TrueType Collection")
        elif sig == b"wOFF":
            lines.append("Font file signature: WOFF")
        elif sig == b"wOF2":
            lines.append("Font file signature: WOFF2")
        else:
            lines.append("Font file signature: " + " ".join(f"{x:02X}" for x in sig))

    # Common Unity Font fields.  Different Unity versions expose different subsets.
    simple_fields = [
        ("Font size", ("m_FontSize", "fontSize", "font_size")),
        ("Ascent", ("m_Ascent", "ascent")),
        ("Descent", ("m_Descent", "descent")),
        ("Line spacing", ("m_LineSpacing", "lineSpacing", "line_spacing")),
        ("Default style", ("m_DefaultStyle", "defaultStyle", "default_style")),
        ("Tracking", ("m_Tracking", "tracking")),
        ("Dynamic", ("m_Dynamic", "dynamic")),
    ]
    shown_any = False
    for label, names in simple_fields:
        value = _get(data, *names, default=None)
        if value is not None:
            if not shown_any:
                lines.append("")
                lines.append("📏 Font metrics")
                shown_any = True
            lines.append(f"  {label}: {value}")

    # Unity Font may reference a material/atlas texture.
    material_pptr = _get(data, "m_Material", "material", "m_DefaultMaterial", "defaultMaterial", default=None)
    texture_pptr = _get(data, "m_Texture", "texture", "m_Atlas", "atlas", default=None)
    if material_pptr is not None or texture_pptr is not None:
        lines.append("")
        lines.append("🎨 Material / atlas links")
        if material_pptr is not None:
            name, typ, pid = _resolve_pptr_name_type(material_pptr, bundle_index)
            lines.append(f"  Material: {display_name_with_icon(name, typ) if typ else name}")
        if texture_pptr is not None:
            name, typ, pid = _resolve_pptr_name_type(texture_pptr, bundle_index)
            lines.append(f"  Atlas/texture: {display_name_with_icon(name, typ) if typ else name}")

    char_rects = _as_list(_get(data, "m_CharacterRects", "characterRects", "character_rects", default=None))
    kerning = _as_list(_get(data, "m_KerningValues", "kerningValues", "kerning_values", default=None))
    if char_rects or kerning:
        lines.append("")
        lines.append("🔡 Glyph table")
        lines.append(f"  Character rects: {len(char_rects):,}" if char_rects else "  Character rects: -")
        lines.append(f"  Kerning pairs: {len(kerning):,}" if kerning else "  Kerning pairs: -")
        if char_rects:
            lines.append("  Sample glyphs:")
            for i, glyph in enumerate(char_rects[:24], 1):
                idx = _get(glyph, "index", "m_Index", "character", "m_Character", default=None)
                uv = _get(glyph, "uv", "m_Uv", "m_UV", default=None)
                vert = _get(glyph, "vert", "m_Vert", default=None)
                width = _get(glyph, "width", "m_Width", default=None)
                flipped = _get(glyph, "flipped", "m_Flipped", default=None)
                bits = [f"{i:>2}: {_char_from_code(idx)}"]
                if width is not None:
                    bits.append(f"width {width}")
                uv_rect = _rect_tuple(uv)
                if uv_rect is not None:
                    bits.append(f"uv {_fmt_float(uv_rect[0])},{_fmt_float(uv_rect[1])},{_fmt_float(uv_rect[2])},{_fmt_float(uv_rect[3])}")
                vert_rect = _rect_tuple(vert)
                if vert_rect is not None:
                    bits.append(f"vert {_fmt_float(vert_rect[0])},{_fmt_float(vert_rect[1])},{_fmt_float(vert_rect[2])},{_fmt_float(vert_rect[3])}")
                if flipped is not None:
                    bits.append(f"flipped {flipped}")
                lines.append("    " + " | ".join(bits))
            if len(char_rects) > 24:
                lines.append(f"    ... {len(char_rects) - 24:,} more glyph rects")

    fields = _short_field_list(data, {"m_Name", "m_FontData", "m_Data", "m_CharacterRects", "m_KerningValues", "m_Material", "m_Texture", "m_Atlas"})
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 Font insight")
    lines.append("Unity Font assets can be dynamic TrueType/OpenType fonts, or bitmap-style font assets with a material/atlas and glyph rectangles.")
    lines.append("The preview is a practical sample render: when embedded font bytes are exposed, UBE tries to load them; otherwise it falls back to a system font with the same family name.")
    lines.append("TextMeshPro fonts may store more complex atlas/glyph data than a normal Unity Font, so UBE treats this as an educational first pass.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_text_asset(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🔤 TextAsset inspector"]
    if data is None:
        lines.append("Unable to read TextAsset data.")
        return lines

    b, text = _textasset_bytes_and_text(data)
    lines.append(f"Byte size: {human_bytes(len(b)) if b is not None else '-'}")
    if text is not None:
        lines.append(f"Text characters: {len(text):,}")
        stripped = text.lstrip()
        if stripped.startswith("{") or stripped.startswith("["):
            lines.append("Looks like: JSON or JSON-like text")
        elif "\n" in text:
            lines.append("Looks like: multiline text/config")
        else:
            lines.append("Looks like: short text/string")
    else:
        lines.append("Looks like: binary or non-text data")

    fields = _short_field_list(data, {"m_Script", "m_Data"})
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🔤 Text preview")
    if text is None:
        if b is not None:
            preview = " ".join(f"{x:02X}" for x in b[:128])
            lines.append("  Binary preview:")
            lines.append("  " + preview + (" ..." if len(b) > 128 else ""))
        else:
            lines.append("  No text/data field exposed by the decoder.")
    else:
        sample = text.replace("\r\n", "\n").replace("\r", "\n")
        max_chars = 3500
        if len(sample) > max_chars:
            sample = sample[:max_chars] + "\n... [truncated]"
        for ln in sample.split("\n"):
            lines.append("  " + ln)

    lines.append("")
    lines.append("🧠 TextAsset insight")
    lines.append("TextAssets are general data blobs Unity stores as assets: JSON, CSV, shader snippets, dialogue, settings, localization, or binary tables.")
    lines.append("They are often very useful when learning how a game organises levels, UI, language strings, tuning values or config data.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_playable_director(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧩 PlayableDirector inspector"]
    if data is None:
        lines.append("Unable to read PlayableDirector data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    playable_asset = _get_any(data, "m_PlayableAsset", "playableAsset", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    initial_state = _get_any(data, "m_InitialState", "initialState", default=None)
    wrap_mode = _get_any(data, "m_WrapMode", "wrapMode", default=None)
    update_mode = _get_any(data, "m_DirectorUpdateMode", "directorUpdateMode", default=None)
    initial_time = _get_any(data, "m_InitialTime", "initialTime", default=None)
    scene_bindings = _get_any(data, "m_SceneBindings", "sceneBindings", default=None)
    exposed_refs = _get_any(data, "m_ExposedReferences", "exposedReferences", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Playable/Timeline asset: {_pptr_text(playable_asset, bundle_index)}")
    if initial_state is not None:
        lines.append(f"Initial state: {_enum_number_text(initial_state, {0:'stopped', 1:'playing'})}")
    if wrap_mode is not None:
        lines.append(f"Wrap mode: {_enum_number_text(wrap_mode, {0:'hold', 1:'loop', 2:'none'})}")
    if update_mode is not None:
        lines.append(f"Update mode: {_enum_number_text(update_mode, {0:'DSP/game time', 1:'game time', 2:'unscaled game time', 3:'manual'})}")
    if initial_time is not None:
        lines.append(f"Initial time: {_fmt_float(initial_time)}")

    lines.append("")
    lines.append("🔗 Scene bindings / exposed references")
    bindings = _as_list(scene_bindings)
    refs = _as_list(exposed_refs)
    if bindings:
        lines.append(f"  Scene bindings: {len(bindings)}")
        for i, bnd in enumerate(bindings[:12]):
            key = _get_any(bnd, "key", "m_Key", default=None)
            value = _get_any(bnd, "value", "m_Value", default=None)
            lines.append(f"    {i}: key {_pptr_text(key, bundle_index)} -> {_pptr_text(value, bundle_index)}")
        if len(bindings) > 12:
            lines.append(f"    ... {len(bindings) - 12} more bindings")
    elif refs:
        lines.append(f"  Exposed references: {len(refs)}")
        for i, item in enumerate(refs[:12]):
            lines.append(f"    {i}: {item}")
        if len(refs) > 12:
            lines.append(f"    ... {len(refs) - 12} more references")
    else:
        lines.append("  No binding list exposed by the decoder.")

    fields = _short_field_list(data, {"m_GameObject", "m_Enabled", "m_PlayableAsset", "m_InitialState", "m_WrapMode",
                                      "m_DirectorUpdateMode", "m_InitialTime", "m_SceneBindings", "m_ExposedReferences"})
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 PlayableDirector insight")
    lines.append("A PlayableDirector is Unity's runtime controller for Timeline/Playable assets. It can drive cutscenes, camera moves, scripted animation sequences, audio cues and object activation.")
    lines.append("Think of it as a higher-level sequencer: AnimationClip moves bones/properties; PlayableDirector decides when timeline tracks and bound scene objects play.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _camera_clear_flags_text(value: Any) -> str:
    try:
        n = int(value)
    except Exception:
        return str(value) if value is not None else "-"
    names = {
        1: "Skybox",
        2: "Solid Color",
        3: "Depth Only",
        4: "Don't Clear",
    }
    return f"{n} ({names.get(n, 'unknown')})"





def _reflection_probe_mode_text(value: Any) -> str:
    try:
        n = int(value)
    except Exception:
        return str(value) if value is not None else "-"
    names = {
        0: "baked",
        1: "custom cubemap",
        2: "realtime",
    }
    return f"{n} ({names.get(n, 'unknown')})"


def _reflection_probe_refresh_text(value: Any) -> str:
    try:
        n = int(value)
    except Exception:
        return str(value) if value is not None else "-"
    names = {
        0: "on awake",
        1: "every frame",
        2: "via scripting",
    }
    return f"{n} ({names.get(n, 'unknown')})"


def _reflection_probe_timeslice_text(value: Any) -> str:
    try:
        n = int(value)
    except Exception:
        return str(value) if value is not None else "-"
    names = {
        0: "all faces at once",
        1: "individual faces",
        2: "no time slicing",
    }
    return f"{n} ({names.get(n, 'unknown')})"


def _describe_reflection_probe(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🪞 Reflection Probe inspector"]
    if data is None:
        lines.append("Unable to read ReflectionProbe data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    mode = _get_any(data, "m_Mode", "mode", "m_Type", "type", default=None)
    refresh = _get_any(data, "m_RefreshMode", "refreshMode", default=None)
    time_slice = _get_any(data, "m_TimeSlicingMode", "timeSlicingMode", default=None)
    resolution = _get_any(data, "m_Resolution", "resolution", default=None)
    update_frequency = _get_any(data, "m_UpdateFrequency", "updateFrequency", default=None)
    box_projection = _get_any(data, "m_BoxProjection", "boxProjection", default=None)
    hdr = _get_any(data, "m_HDR", "hdr", default=None)
    render_dynamic = _get_any(data, "m_RenderDynamicObjects", "renderDynamicObjects", default=None)
    occlusion = _get_any(data, "m_UseOcclusionCulling", "useOcclusionCulling", default=None)
    intensity = _get_any(data, "m_IntensityMultiplier", "intensityMultiplier", "m_Intensity", default=None)
    blend = _get_any(data, "m_BlendDistance", "blendDistance", default=None)
    importance = _get_any(data, "m_Importance", "importance", default=None)
    box_size = _get_any(data, "m_BoxSize", "boxSize", "m_Size", "size", default=None)
    box_offset = _get_any(data, "m_BoxOffset", "boxOffset", "m_Center", "center", default=None)
    near_clip = _get_any(data, "m_NearClip", "nearClip", "nearClipPlane", default=None)
    far_clip = _get_any(data, "m_FarClip", "farClip", "farClipPlane", default=None)
    shadow_distance = _get_any(data, "m_ShadowDistance", "shadowDistance", default=None)
    clear_flags = _get_any(data, "m_ClearFlags", "clearFlags", default=None)
    background = _get_any(data, "m_BackGroundColor", "m_BackgroundColor", "backgroundColor", default=None)
    culling_mask = _get_any(data, "m_CullingMask", "cullingMask", default=None)
    custom_tex = _get_any(data, "m_CustomBakedTexture", "customBakedTexture", "m_CustomTexture", default=None)
    baked_tex = _get_any(data, "m_BakedTexture", "bakedTexture", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    if enabled is not None:
        lines.append(f"Enabled: {_bool_text(enabled)}")
    if mode is not None:
        lines.append(f"Probe mode/type: {_reflection_probe_mode_text(mode)}")
    if refresh is not None:
        lines.append(f"Refresh mode: {_reflection_probe_refresh_text(refresh)}")
    if time_slice is not None:
        lines.append(f"Time slicing: {_reflection_probe_timeslice_text(time_slice)}")
    if resolution is not None:
        lines.append(f"Resolution: {resolution} px cubemap faces")
    if update_frequency is not None:
        lines.append(f"Update frequency: {update_frequency}")

    lines.append("")
    lines.append("📦 Probe volume / blending")
    if box_size is not None:
        lines.append(f"  Box size: {_fmt_vec3(box_size)}")
    if box_offset is not None:
        lines.append(f"  Box offset / center: {_fmt_vec3(box_offset)}")
    if box_projection is not None:
        lines.append(f"  Box projection: {_bool_text(box_projection)}")
    if blend is not None:
        lines.append(f"  Blend distance: {_fmt_float(blend)}")
    if importance is not None:
        lines.append(f"  Importance: {importance}")
    if intensity is not None:
        lines.append(f"  Intensity multiplier: {_fmt_float(intensity)}")

    lines.append("")
    lines.append("🖼 Capture / rendering")
    if hdr is not None:
        lines.append(f"  HDR: {_bool_text(hdr)}")
    if render_dynamic is not None:
        lines.append(f"  Render dynamic objects: {_bool_text(render_dynamic)}")
    if occlusion is not None:
        lines.append(f"  Occlusion culling: {_bool_text(occlusion)}")
    if clear_flags is not None:
        lines.append(f"  Clear flags: {_camera_clear_flags_text(clear_flags)}")
    if background is not None:
        lines.append(f"  Background colour: {_colour_line(background)}")
    if culling_mask is not None:
        lines.append(f"  Culling mask: {_layer_mask_text(culling_mask)}")
    if near_clip is not None:
        lines.append(f"  Near clip: {_fmt_float(near_clip)}")
    if far_clip is not None:
        lines.append(f"  Far clip: {_fmt_float(far_clip)}")
    if shadow_distance is not None:
        lines.append(f"  Shadow distance: {_fmt_float(shadow_distance)}")

    tex_lines = []
    if custom_tex is not None and _pptr_path_id(custom_tex) not in (None, 0):
        tex_lines.append(f"  Custom baked texture: {_pptr_text(custom_tex, bundle_index)}")
    if baked_tex is not None and _pptr_path_id(baked_tex) not in (None, 0):
        tex_lines.append(f"  Baked texture: {_pptr_text(baked_tex, bundle_index)}")
    if tex_lines:
        lines.append("")
        lines.append("🧊 Cubemap references")
        lines.extend(tex_lines)

    known = {
        "m_GameObject", "m_Enabled", "m_Mode", "m_Type", "m_RefreshMode", "m_TimeSlicingMode",
        "m_Resolution", "m_UpdateFrequency", "m_BoxProjection", "m_HDR", "m_RenderDynamicObjects",
        "m_UseOcclusionCulling", "m_IntensityMultiplier", "m_Intensity", "m_BlendDistance", "m_Importance",
        "m_BoxSize", "m_BoxOffset", "m_Size", "m_Center", "m_NearClip", "m_FarClip", "m_ShadowDistance",
        "m_ClearFlags", "m_BackGroundColor", "m_BackgroundColor", "m_CullingMask", "m_CustomBakedTexture",
        "m_CustomTexture", "m_BakedTexture",
    }
    fields = [f for f in _field_names(data) if f.startswith("m_") and f not in known]
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        for name in fields[:24]:
            value = _get_any(data, name, default=None)
            lines.append(f"  {name}: {_light_setting_value_text(value, bundle_index)}")
        if len(fields) > 24:
            lines.append(f"  ... {len(fields) - 24} more field(s)")

    lines.append("")
    lines.append("🎞 Reflection volume visual")
    lines.append("  Preview: a symbolic cubemap/box volume is shown in the top preview panel. It does not render true Unity reflections.")

    lines.append("")
    lines.append("🧠 Reflection probe insight")
    lines.append("A Reflection Probe captures or references a cubemap of the surrounding scene. Shiny materials can sample that cubemap to fake reflections much more cheaply than realtime ray tracing.")
    lines.append("Box projection and blend distance are especially useful indoors: Unity can make the reflected environment feel as if it belongs to a room, glass case, metal object or polished floor area.")
    lines.append("In mobile/VR projects these probes are often baked or custom cubemaps, so they add believable shine without a large per-frame lighting cost.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def _camera_float(value: Any) -> float | None:
    try:
        v = float(value)
    except Exception:
        return None
    if not math.isfinite(v):
        return None
    return v


def _camera_vec2(value: Any) -> tuple[float, float] | None:
    parsed = _vec2_tuple(value, None)
    if parsed is None:
        return None
    try:
        x = float(parsed[0])
        y = float(parsed[1])
    except Exception:
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return (x, y)


def _camera_fov_from_focal(sensor_mm: float, focal_mm: float) -> float | None:
    if sensor_mm <= 0 or focal_mm <= 0:
        return None
    try:
        return math.degrees(2.0 * math.atan(sensor_mm / (2.0 * focal_mm)))
    except Exception:
        return None


def _camera_lens_class(full_frame_focal: float | None, h_fov: float | None) -> str:
    f = full_frame_focal
    if f is not None:
        if f < 20:
            return "ultra-wide"
        if f < 35:
            return "wide-angle"
        if f < 70:
            return "normal / natural"
        if f < 135:
            return "short telephoto / narrow"
        return "telephoto / very narrow"
    if h_fov is not None:
        if h_fov > 80:
            return "wide-angle"
        if h_fov > 40:
            return "normal / natural"
        return "telephoto / narrow"
    return "unknown"


def _camera_lens_visual_lines(
    focal_length: Any,
    sensor_size: Any,
    fov: Any,
    ortho: Any,
    ortho_size: Any,
    lens_shift: Any = None,
) -> list[str]:
    """Small educational camera diagram for the text inspector.

    This is deliberately approximate.  It is meant to help a user understand
    focal length/sensor/FOV relationships, not replace Unity's exact projection
    matrix/gate-fit behaviour.
    """
    lines: list[str] = []

    is_ortho = bool(ortho)
    if is_ortho:
        size = _camera_float(ortho_size)
        lines.append("🎞 Camera view visual")
        lines.append("  Projection: orthographic")
        if size is not None:
            lines.append(f"  Vertical view height: about {_fmt_float(size * 2.0)} world units")
        lines.append("  Orthographic cameras do not use perspective lens compression; objects stay the same size with distance.")
        lines.append("  Visual:")
        lines.append("      ┌───────────────┐")
        lines.append("      │   same scale  │")
        lines.append("      │   near/far    │")
        lines.append("      └───────────────┘")
        return lines

    focal = _camera_float(focal_length)
    sensor = _camera_vec2(sensor_size)
    fov_value = _camera_float(fov)
    shift = _camera_vec2(lens_shift)

    h_fov = v_fov = d_fov = None
    equiv35 = None
    if focal is not None and sensor is not None:
        sw, sh = sensor
        diag = math.sqrt(sw * sw + sh * sh)
        h_fov = _camera_fov_from_focal(sw, focal)
        v_fov = _camera_fov_from_focal(sh, focal)
        d_fov = _camera_fov_from_focal(diag, focal)
        if diag > 0:
            # 35mm/full-frame diagonal is about 43.27mm.
            equiv35 = focal * (43.266615 / diag)
    elif fov_value is not None:
        v_fov = fov_value

    main_fov = h_fov if h_fov is not None else v_fov
    lens_class = _camera_lens_class(equiv35 if equiv35 is not None else focal, main_fov)

    lines.append("🎞 Camera view visual")
    if focal is not None and sensor is not None:
        sw, sh = sensor
        lines.append(f"  Lens: {_fmt_float(focal)} mm on a {_fmt_float(sw)}×{_fmt_float(sh)} mm sensor")
        if h_fov is not None and v_fov is not None:
            lines.append(f"  Approx FOV: horizontal {_fmt_float(h_fov)}°, vertical {_fmt_float(v_fov)}°" + (f", diagonal {_fmt_float(d_fov)}°" if d_fov is not None else ""))
        if equiv35 is not None:
            lines.append(f"  35mm equivalent: about {_fmt_float(equiv35)} mm")
    elif fov_value is not None:
        lines.append(f"  Field of view: about {_fmt_float(fov_value)}°")
    else:
        lines.append("  Field of view: not enough lens data exposed")

    lines.append(f"  Look/feel: {lens_class}")
    if shift is not None and (abs(shift[0]) > 0.0001 or abs(shift[1]) > 0.0001):
        lines.append(f"  Lens shift moves the view window: X {_fmt_float(shift[0])}, Y {_fmt_float(shift[1])}")

    lines.append("  Preview: a CAD-style frustum model is shown in the top preview panel.")
    lines.append("  Rule of thumb: shorter focal length = wider view; longer focal length = narrower, more zoomed/compressed view.")
    return lines



_MISSING = object()


def _nested_get_any(obj: Any, *paths: str, default: Any = None) -> Any:
    """Fetch nested UnityPy/raw fields using dotted paths, tolerating dicts and objects."""
    for path in paths:
        cur = obj
        ok = True
        for part in str(path).split("."):
            cur = _get_any(cur, part, default=_MISSING)
            if cur is _MISSING:
                ok = False
                break
        if ok:
            return cur
    return default


def _field_names(obj: Any) -> list[str]:
    return _anim_object_fields(obj)


def _light_setting_value_text(value: Any, bundle_index: Any | None = None) -> str:
    """Compact formatter for arbitrary lighting/probe settings."""
    if value is None:
        return "-"
    pid = _pptr_path_id(value)
    fid = _pptr_file_id(value)
    if pid not in (None, 0) or fid not in (None, 0):
        return _pptr_text(value, bundle_index)
    if isinstance(value, bool):
        return _bool_text(value)
    if isinstance(value, (int, float, str)):
        return str(value)
    if _vec4_tuple(value, None) is not None:
        return _fmt_vec4(value)
    if _vec3_tuple(value, None) is not None:
        return _fmt_vec3(value)
    if _vec2_tuple(value, None) is not None:
        return _fmt_vec2(value)
    if isinstance(value, (list, tuple)):
        return f"{len(value)} item(s)"
    fields = _field_names(value)
    if fields:
        return f"{type(value).__name__} with {len(fields)} field(s)"
    return str(value)


def _vec3_bounds(values: list[Any]) -> tuple[tuple[float, float, float], tuple[float, float, float]] | None:
    pts: list[tuple[float, float, float]] = []
    for item in values:
        v = _vec3_tuple(item, None)
        if v is None:
            continue
        if all(math.isfinite(x) for x in v):
            pts.append(v)
    if not pts:
        return None
    mins = tuple(min(p[i] for p in pts) for i in range(3))
    maxs = tuple(max(p[i] for p in pts) for i in range(3))
    return mins, maxs


def _append_extra_lighting_fields(lines: list[str], data: Any, known: set[str], bundle_index: Any | None = None, limit: int = 30) -> None:
    fields = [f for f in _field_names(data) if f.startswith("m_") and f not in known]
    if not fields:
        return
    lines.append("")
    lines.append("🧾 Other exposed fields")
    for name in fields[:limit]:
        value = _get_any(data, name, default=None)
        lines.append(f"  {name}: {_light_setting_value_text(value, bundle_index)}")
    if len(fields) > limit:
        lines.append(f"  ... {len(fields) - limit} more field(s)")




def _lod_field(obj: Any, *names: str, default: Any = None) -> Any:
    """Read a field from either UnityPy objects or dict-like serialized data."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
    for name in names:
        if hasattr(obj, name):
            try:
                return getattr(obj, name)
            except Exception:
                pass
    return default


def _lod_float(value: Any, default: float | None = None) -> float | None:
    try:
        f = float(value)
    except Exception:
        return default
    if not math.isfinite(f):
        return default
    return f


def _lod_renderers(lod: Any) -> list[Any]:
    value = _lod_field(lod, "m_Renderers", "renderers", "Renderers", default=None)
    return _as_list(value)


def _mesh_triangle_estimate(mesh_rec: Any | None) -> int | None:
    if mesh_rec is None:
        return None
    data = _read(mesh_rec)
    if data is None:
        return None
    submeshes = _get_any(data, "m_SubMeshes", "sub_meshes", default=None)
    if not isinstance(submeshes, list):
        return None
    total_indices = 0
    for sm in submeshes:
        ic = _get_any(sm, "indexCount", "m_IndexCount", "index_count", default=None)
        try:
            total_indices += int(ic or 0)
        except Exception:
            pass
    return total_indices // 3 if total_indices else None


def _mesh_vertex_count(mesh_rec: Any | None) -> int | None:
    if mesh_rec is None:
        return None
    data = _read(mesh_rec)
    if data is None:
        return None
    value = _get_any(data, "m_VertexCount", "vertex_count", "vertexCount", default=None)
    try:
        return int(value)
    except Exception:
        return None


def _gameobject_name_for_component(component_rec: Any | None, bundle_index: Any | None) -> str:
    if component_rec is None:
        return "-"
    data = _read(component_rec)
    if data is None:
        return "-"
    go = _get_any(data, "m_GameObject", "gameObject", "game_object", default=None)
    rec = _resolve_record(bundle_index, go)
    if rec is not None:
        return rec.name
    return _pptr_text(go, bundle_index)


def _mesh_for_renderer_component(renderer_rec: Any | None, bundle_index: Any | None) -> Any | None:
    if renderer_rec is None:
        return None
    data = _read(renderer_rec)
    if data is None:
        return None

    # SkinnedMeshRenderer stores the mesh directly.
    if getattr(renderer_rec, "type_name", "") == "SkinnedMeshRenderer":
        mesh = _get_any(data, "m_Mesh", "mesh", default=None)
        rec = _resolve_record(bundle_index, mesh)
        return rec if rec is not None and getattr(rec, "type_name", "") == "Mesh" else None

    # MeshRenderer uses a MeshFilter on the same GameObject.
    go = _get_any(data, "m_GameObject", "gameObject", "game_object", default=None)
    go_pid = _pptr_path_id(go)
    for mf in _records_with_gameobject(bundle_index, "MeshFilter", go_pid):
        mf_data = _read(mf)
        mesh = _get_any(mf_data, "m_Mesh", "mesh", default=None) if mf_data is not None else None
        rec = _resolve_record(bundle_index, mesh)
        if rec is not None and getattr(rec, "type_name", "") == "Mesh":
            return rec
    return None


def _lod_renderer_summary(renderer_pptr: Any, bundle_index: Any | None) -> tuple[Any | None, Any | None, int | None, int | None, str]:
    renderer_rec = _resolve_record(bundle_index, renderer_pptr)
    mesh_rec = _mesh_for_renderer_component(renderer_rec, bundle_index)
    tris = _mesh_triangle_estimate(mesh_rec)
    verts = _mesh_vertex_count(mesh_rec)
    go_name = _gameobject_name_for_component(renderer_rec, bundle_index)
    return renderer_rec, mesh_rec, tris, verts, go_name


def _lod_group_numeric_mode(label: str, value: Any, mapping: dict[int, str]) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
        return f"{n} ({mapping.get(n, 'unknown')})"
    except Exception:
        return str(value)



def _particle_mode_text(value: Any, mapping: dict[int, str] | None = None) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
        if mapping:
            return f"{n} ({mapping.get(n, 'unknown')})"
        return str(n)
    except Exception:
        return str(value)


def _particle_value_text(value: Any, bundle_index: Any | None = None) -> str:
    """Compact formatter for ParticleSystem nested MinMaxCurve/Gradient-style values."""
    if value is None:
        return "-"
    pid = _pptr_path_id(value)
    fid = _pptr_file_id(value)
    if pid not in (None, 0) or fid not in (None, 0):
        return _pptr_text(value, bundle_index)
    if isinstance(value, bool):
        return _bool_text(value)
    if isinstance(value, (int, float)):
        return _fmt_float(value)
    if isinstance(value, str):
        return value
    if _vec4_tuple(value, None) is not None:
        return _colour_line(value)
    if _vec3_tuple(value, None) is not None:
        return _fmt_vec3(value)
    if _vec2_tuple(value, None) is not None:
        return _fmt_vec2(value)

    state = _get_any(value, "minMaxState", "m_MinMaxState", "mode", "m_Mode", default=None)
    scalar = _get_any(value, "scalar", "m_Scalar", "constant", "m_Constant", default=None)
    min_scalar = _get_any(value, "minScalar", "m_MinScalar", "constantMin", "m_ConstantMin", default=None)
    max_scalar = _get_any(value, "maxScalar", "m_MaxScalar", "constantMax", "m_ConstantMax", default=None)
    if scalar is not None or min_scalar is not None or max_scalar is not None:
        bits = []
        if state is not None:
            bits.append(f"state {state}")
        if scalar is not None:
            bits.append(f"value {_fmt_float(scalar)}")
        if min_scalar is not None or max_scalar is not None:
            bits.append(f"range {_fmt_float(min_scalar)}–{_fmt_float(max_scalar)}")
        return "; ".join(bits)

    color = _get_any(value, "color", "m_Color", default=None)
    min_color = _get_any(value, "minColor", "m_MinColor", default=None)
    max_color = _get_any(value, "maxColor", "m_MaxColor", default=None)
    if color is not None or min_color is not None or max_color is not None:
        bits = []
        if state is not None:
            bits.append(f"state {state}")
        if color is not None:
            bits.append(f"colour {_colour_line(color)}")
        if min_color is not None or max_color is not None:
            bits.append(f"range {_colour_line(min_color)} → {_colour_line(max_color)}")
        return "; ".join(bits)

    if isinstance(value, (list, tuple)):
        return f"{len(value)} item(s)"
    fields = _field_names(value)
    if fields:
        return f"{type(value).__name__} with {len(fields)} field(s)"
    return str(value)


def _particle_module(data: Any, *names: str) -> Any:
    for name in names:
        value = _get_any(data, name, f"m_{name}", default=None)
        if value is not None:
            return value
    return None


def _particle_module_lines(lines: list[str], title: str, module: Any, fields: list[tuple[str, tuple[str, ...]]], bundle_index: Any | None = None) -> None:
    if module is None:
        return
    lines.append("")
    lines.append(title)
    enabled = _get_any(module, "enabled", "m_Enabled", default=None)
    if enabled is not None:
        lines.append(f"  Enabled: {_bool_text(enabled)}")
    any_field = False
    for label, names in fields:
        value = _get_any(module, *names, default=None)
        if value is not None:
            any_field = True
            lines.append(f"  {label}: {_particle_value_text(value, bundle_index)}")
    if not any_field and enabled is None:
        field_count = len(_field_names(module))
        if field_count:
            lines.append(f"  {field_count} exposed field(s)")


def _particle_shape_type_text(value: Any) -> str:
    mapping = {
        0: "sphere", 1: "sphere shell", 2: "hemisphere", 3: "hemisphere shell",
        4: "cone", 5: "box", 6: "mesh", 7: "cone shell", 8: "cone volume",
        9: "cone volume shell", 10: "circle", 11: "circle edge", 12: "single-sided edge",
        13: "mesh renderer", 14: "skinned mesh renderer", 15: "box shell", 16: "box edge",
        17: "donut", 18: "rectangle", 19: "sprite", 20: "sprite renderer",
    }
    return _particle_mode_text(value, mapping)


def _particle_renderer_mode_text(value: Any) -> str:
    mapping = {0: "billboard", 1: "stretched billboard", 2: "horizontal billboard", 3: "vertical billboard", 4: "mesh", 5: "none"}
    return _particle_mode_text(value, mapping)


def _particle_sort_mode_text(value: Any) -> str:
    mapping = {0: "none", 1: "distance", 2: "oldest in front", 3: "youngest in front"}
    return _particle_mode_text(value, mapping)


def _describe_particle_system(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["✨ ParticleSystem inspector"]
    if data is None:
        lines.append("Unable to read ParticleSystem data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    initial = _particle_module(data, "InitialModule", "initialModule") or data
    emission = _particle_module(data, "EmissionModule", "emissionModule")
    shape = _particle_module(data, "ShapeModule", "shapeModule")

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    if enabled is not None:
        lines.append(f"Enabled: {_bool_text(enabled)}")

    lines.append("")
    lines.append("▶ Playback / lifetime")
    root_fields = [
        ("Duration", ("lengthInSec", "m_LengthInSec", "duration", "m_Duration")),
        ("Looping", ("looping", "m_Looping", "loop", "m_Loop")),
        ("Prewarm", ("prewarm", "m_Prewarm")),
        ("Play on awake", ("playOnAwake", "m_PlayOnAwake")),
        ("Simulation speed", ("simulationSpeed", "m_SimulationSpeed")),
        ("Max particles", ("maxNumParticles", "m_MaxNumParticles", "maxParticles", "m_MaxParticles")),
        ("Random seed", ("randomSeed", "m_RandomSeed")),
        ("Auto random seed", ("autoRandomSeed", "m_AutoRandomSeed")),
    ]
    any_root = False
    for label, names in root_fields:
        value = _get_any(data, *names, default=None)
        if value is None and initial is not data:
            value = _get_any(initial, *names, default=None)
        if value is not None:
            any_root = True
            lines.append(f"  {label}: {_particle_value_text(value, bundle_index)}")
    if not any_root:
        lines.append("  Main playback fields were not exposed by this UnityPy read.")

    _particle_module_lines(lines, "🎬 Start values", initial, [
        ("Start delay", ("startDelay", "m_StartDelay")),
        ("Start lifetime", ("startLifetime", "m_StartLifetime")),
        ("Start speed", ("startSpeed", "m_StartSpeed")),
        ("Start size", ("startSize", "m_StartSize")),
        ("Start size X", ("startSizeX", "m_StartSizeX")),
        ("Start size Y", ("startSizeY", "m_StartSizeY")),
        ("Start size Z", ("startSizeZ", "m_StartSizeZ")),
        ("Start rotation", ("startRotation", "m_StartRotation")),
        ("Start colour", ("startColor", "m_StartColor", "startColour", "m_StartColour")),
        ("Gravity modifier", ("gravityModifier", "m_GravityModifier")),
        ("Simulation space", ("simulationSpace", "m_SimulationSpace")),
        ("Scaling mode", ("scalingMode", "m_ScalingMode")),
    ], bundle_index)

    if emission is not None:
        lines.append("")
        lines.append("🌫 Emission")
        en = _get_any(emission, "enabled", "m_Enabled", default=None)
        if en is not None:
            lines.append(f"  Enabled: {_bool_text(en)}")
        for label, names in [
            ("Rate over time", ("rateOverTime", "m_RateOverTime", "rateOverTimeMultiplier", "m_RateOverTimeMultiplier")),
            ("Rate over distance", ("rateOverDistance", "m_RateOverDistance", "rateOverDistanceMultiplier", "m_RateOverDistanceMultiplier")),
            ("Bursts", ("bursts", "m_Bursts", "burstCount", "m_BurstCount")),
        ]:
            value = _get_any(emission, *names, default=None)
            if value is not None:
                lines.append(f"  {label}: {_particle_value_text(value, bundle_index)}")

    if shape is not None:
        lines.append("")
        lines.append("📐 Shape / emitter")
        en = _get_any(shape, "enabled", "m_Enabled", default=None)
        if en is not None:
            lines.append(f"  Enabled: {_bool_text(en)}")
        shape_type = _get_any(shape, "type", "m_Type", "shapeType", "m_ShapeType", default=None)
        if shape_type is not None:
            lines.append(f"  Type: {_particle_shape_type_text(shape_type)}")
        for label, names in [
            ("Angle", ("angle", "m_Angle")),
            ("Radius", ("radius", "m_Radius")),
            ("Arc", ("arc", "m_Arc")),
            ("Length", ("length", "m_Length")),
            ("Box thickness", ("boxThickness", "m_BoxThickness")),
            ("Scale", ("scale", "m_Scale")),
            ("Position", ("position", "m_Position")),
            ("Rotation", ("rotation", "m_Rotation")),
            ("Mesh", ("mesh", "m_Mesh")),
            ("Mesh renderer", ("meshRenderer", "m_MeshRenderer")),
            ("Skinned mesh renderer", ("skinnedMeshRenderer", "m_SkinnedMeshRenderer")),
            ("Sprite", ("sprite", "m_Sprite")),
        ]:
            value = _get_any(shape, *names, default=None)
            if value is not None:
                lines.append(f"  {label}: {_particle_value_text(value, bundle_index)}")

    _particle_module_lines(lines, "🧭 Velocity / force modules", _particle_module(data, "VelocityModule", "velocityModule"), [
        ("X", ("x", "m_X")), ("Y", ("y", "m_Y")), ("Z", ("z", "m_Z")),
        ("Speed modifier", ("speedModifier", "m_SpeedModifier")), ("Space", ("space", "m_Space")),
    ], bundle_index)
    _particle_module_lines(lines, "🎨 Colour / size over lifetime", _particle_module(data, "ColorModule", "colorModule", "ColorBySpeedModule", "colorBySpeedModule"), [
        ("Colour", ("color", "m_Color", "gradient", "m_Gradient")), ("Range", ("range", "m_Range")),
    ], bundle_index)
    _particle_module_lines(lines, "📏 Size over lifetime", _particle_module(data, "SizeModule", "sizeModule", "SizeBySpeedModule", "sizeBySpeedModule"), [
        ("Size", ("curve", "m_Curve", "size", "m_Size")),
        ("X", ("x", "m_X")), ("Y", ("y", "m_Y")), ("Z", ("z", "m_Z")), ("Range", ("range", "m_Range")),
    ], bundle_index)
    _particle_module_lines(lines, "🧵 Trails", _particle_module(data, "TrailModule", "trailsModule", "TrailsModule", "trailModule"), [
        ("Ratio", ("ratio", "m_Ratio")), ("Lifetime", ("lifetime", "m_Lifetime")),
        ("Width over trail", ("widthOverTrail", "m_WidthOverTrail")),
        ("Colour over trail", ("colorOverTrail", "m_ColorOverTrail", "colourOverTrail", "m_ColourOverTrail")),
    ], bundle_index)

    go_pid = _pptr_path_id(game_object)
    renderers = _records_with_gameobject(bundle_index, "ParticleSystemRenderer", go_pid)
    if renderers:
        lines.append("")
        lines.append("🖼 Renderer on same GameObject")
        for r in renderers[:6]:
            lines.append(f"  ParticleSystemRenderer - {r.name} (PathID {r.path_id})")
        if len(renderers) > 6:
            lines.append(f"  ... {len(renderers) - 6} more renderer(s)")

    known = {"m_GameObject", "m_Enabled", "InitialModule", "m_InitialModule", "EmissionModule", "m_EmissionModule", "ShapeModule", "m_ShapeModule"}
    extra = [f for f in _field_names(data) if f.startswith("m_") and f not in known]
    if extra:
        lines.append("")
        lines.append("🧾 Other exposed ParticleSystem fields")
        for name in extra[:24]:
            value = _get_any(data, name, default=None)
            lines.append(f"  {name}: {_particle_value_text(value, bundle_index)}")
        if len(extra) > 24:
            lines.append(f"  ... {len(extra) - 24} more field(s)")

    lines.append("")
    lines.append("🧠 ParticleSystem insight")
    lines.append("A ParticleSystem is Unity's cheap effect emitter: smoke, dust, sparks, leaves, magic glow, water spray, pollen, fireflies or UI sparkle effects.")
    lines.append("The ParticleSystem controls lifetime, emission and motion. The ParticleSystemRenderer controls how those particles are drawn: billboard sprites, stretched streaks, mesh particles or trail material.")
    lines.append("UBE shows this symbolically rather than simulating every particle, because the exact result also depends on runtime time, random seed, material shader and camera-facing billboard rules.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_particle_system_renderer(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["✨ ParticleSystemRenderer inspector"]
    if data is None:
        lines.append("Unable to read ParticleSystemRenderer data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    render_mode = _get_any(data, "m_RenderMode", "renderMode", default=None)
    sort_mode = _get_any(data, "m_SortMode", "sortMode", default=None)
    alignment = _get_any(data, "m_RenderAlignment", "renderAlignment", default=None)
    materials = _as_list(_get_any(data, "m_Materials", "materials", default=None))
    mesh = _get_any(data, "m_Mesh", "mesh", default=None)
    trail_mat = _get_any(data, "m_TrailMaterial", "trailMaterial", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    if enabled is not None:
        lines.append(f"Enabled: {_bool_text(enabled)}")
    if render_mode is not None:
        lines.append(f"Render mode: {_particle_renderer_mode_text(render_mode)}")
    if sort_mode is not None:
        lines.append(f"Sort mode: {_particle_sort_mode_text(sort_mode)}")
    if alignment is not None:
        lines.append(f"Render alignment: {alignment}")

    lines.append("")
    lines.append("🖼 Draw/material setup")
    if materials:
        lines.append(f"  Materials: {len(materials)}")
        for i, mat in enumerate(materials[:10]):
            lines.append(f"    Slot {i}: {_pptr_text(mat, bundle_index)}")
        if len(materials) > 10:
            lines.append(f"    ... {len(materials) - 10} more material(s)")
    else:
        lines.append("  Materials: none exposed")
    if mesh is not None:
        lines.append(f"  Mesh: {_pptr_text(mesh, bundle_index)}")
    if trail_mat is not None:
        lines.append(f"  Trail material: {_pptr_text(trail_mat, bundle_index)}")

    lines.append("")
    lines.append("📏 Billboard / streak controls")
    for label, names in [
        ("Camera velocity scale", ("m_CameraVelocityScale", "cameraVelocityScale")),
        ("Velocity scale", ("m_VelocityScale", "velocityScale")),
        ("Length scale", ("m_LengthScale", "lengthScale")),
        ("Normal direction", ("m_NormalDirection", "normalDirection")),
        ("Min particle size", ("m_MinParticleSize", "minParticleSize")),
        ("Max particle size", ("m_MaxParticleSize", "maxParticleSize")),
        ("Sorting fudge", ("m_SortingFudge", "sortingFudge")),
        ("Shadow bias", ("m_ShadowBias", "shadowBias")),
        ("Pivot", ("m_Pivot", "pivot")),
    ]:
        value = _get_any(data, *names, default=None)
        if value is not None:
            lines.append(f"  {label}: {_particle_value_text(value, bundle_index)}")

    go_pid = _pptr_path_id(game_object)
    systems = _records_with_gameobject(bundle_index, "ParticleSystem", go_pid)
    if systems:
        lines.append("")
        lines.append("✨ ParticleSystem on same GameObject")
        for ps in systems[:6]:
            lines.append(f"  ParticleSystem - {ps.name} (PathID {ps.path_id})")
        if len(systems) > 6:
            lines.append(f"  ... {len(systems) - 6} more system(s)")

    known = {"m_GameObject", "m_Enabled", "m_RenderMode", "m_SortMode", "m_RenderAlignment", "m_Materials", "m_Mesh", "m_TrailMaterial"}
    extra = [f for f in _field_names(data) if f.startswith("m_") and f not in known]
    if extra:
        lines.append("")
        lines.append("🧾 Other exposed renderer fields")
        for name in extra[:24]:
            value = _get_any(data, name, default=None)
            lines.append(f"  {name}: {_particle_value_text(value, bundle_index)}")
        if len(extra) > 24:
            lines.append(f"  ... {len(extra) - 24} more field(s)")

    lines.append("")
    lines.append("🧠 Particle renderer insight")
    lines.append("The renderer is the visual half of a particle effect. It decides whether particles are camera-facing billboards, stretched streaks, horizontal/vertical cards or real mesh particles, and which material/texture shader draws them.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def _describe_lod_group(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["📉 LODGroup inspector"]
    if data is None:
        lines.append("Unable to read LODGroup data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", "game_object", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    lods = _as_list(_get_any(data, "m_LODs", "lods", "LODs", default=None))
    fade_mode = _get_any(data, "m_FadeMode", "fadeMode", default=None)
    animate_cross = _get_any(data, "m_AnimateCrossFading", "animateCrossFading", default=None)
    last_billboard = _get_any(data, "m_LastLODIsBillboard", "lastLODIsBillboard", default=None)
    size = _get_any(data, "m_Size", "size", "m_ObjectSize", "objectSize", default=None)
    local_ref = _get_any(data, "m_LocalReferencePoint", "localReferencePoint", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    if enabled is not None:
        lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"LOD levels: {len(lods)}")
    if size is not None:
        lines.append(f"Object size/reference size: {_fmt_float(size)}")
    if local_ref is not None:
        lines.append(f"Local reference point: {_fmt_vec3(local_ref)}")
    if fade_mode is not None:
        lines.append(f"Fade mode: {_lod_group_numeric_mode('Fade mode', fade_mode, {0: 'none', 1: 'cross fade', 2: 'speed tree'})}")
    if animate_cross is not None:
        lines.append(f"Animate cross-fading: {_bool_text(animate_cross)}")
    if last_billboard is not None:
        lines.append(f"Last LOD is billboard: {_bool_text(last_billboard)}")

    if lods:
        lines.append("")
        lines.append("📊 LOD levels")
        grand_tris = 0
        grand_tris_known = False
        last_threshold = None
        for i, lod in enumerate(lods):
            threshold = _lod_float(_lod_field(lod, "screenRelativeHeight", "m_ScreenRelativeHeight", "screen_relative_height", default=None), None)
            fade_width = _lod_field(lod, "fadeTransitionWidth", "m_FadeTransitionWidth", "fade_transition_width", default=None)
            renderers = _lod_renderers(lod)
            label = f"LOD{i}"
            if threshold is not None:
                label += f"  screen ≥ {_fmt_float(threshold * 100.0)}%"
            else:
                label += "  screen threshold -"
            if fade_width is not None:
                label += f", fade width {_fmt_float(fade_width)}"
            lines.append(f"  {label}")
            lines.append(f"    Renderers: {len(renderers)}")

            lod_tris = 0
            lod_tris_known = False
            for j, renderer in enumerate(renderers[:18]):
                renderer_rec, mesh_rec, tris, verts, go_name = _lod_renderer_summary(renderer, bundle_index)
                renderer_text = _pptr_text(renderer, bundle_index)
                mesh_text = f"; Mesh: {mesh_rec.name}" if mesh_rec is not None else "; Mesh: -"
                stats = []
                if verts is not None:
                    stats.append(f"{verts:,} verts")
                if tris is not None:
                    stats.append(f"~{tris:,} tris")
                    lod_tris += tris
                    lod_tris_known = True
                stats_text = ("; " + ", ".join(stats)) if stats else ""
                go_text = f"; Object: {go_name}" if go_name and go_name != "-" else ""
                lines.append(f"      {j}: {renderer_text}{go_text}{mesh_text}{stats_text}")
            if len(renderers) > 18:
                lines.append(f"      ... {len(renderers) - 18} more renderer(s)")
            if lod_tris_known:
                lines.append(f"    LOD{i} triangle estimate: ~{lod_tris:,}")
                grand_tris += lod_tris
                grand_tris_known = True

            if last_threshold is not None and threshold is not None and threshold > last_threshold + 1e-6:
                lines.append("    ⚠ Threshold is higher than the previous LOD; Unity normally stores LODs from high to low screen size.")
            last_threshold = threshold if threshold is not None else last_threshold

        if grand_tris_known:
            lines.append("")
            lines.append(f"Total triangle estimate across all listed LOD renderers: ~{grand_tris:,}")
            lines.append("Note: this is not drawn all at once in-game; Unity chooses one LOD level based on screen size/distance.")
    else:
        lines.append("")
        lines.append("No m_LODs array was exposed by this UnityPy read. The raw relationships may still show referenced renderers.")

    known = {"m_GameObject", "m_Enabled", "m_LODs", "m_FadeMode", "m_AnimateCrossFading", "m_LastLODIsBillboard", "m_Size", "m_ObjectSize", "m_LocalReferencePoint"}
    fields = [f for f in _field_names(data) if f.startswith("m_") and f not in known]
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        for name in fields[:24]:
            value = _get_any(data, name, default=None)
            lines.append(f"  {name}: {_light_setting_value_text(value, bundle_index)}")
        if len(fields) > 24:
            lines.append(f"  ... {len(fields) - 24} more field(s)")

    lines.append("")
    lines.append("🧠 LODGroup insight")
    lines.append("LOD means Level Of Detail. Unity can swap between different renderer/mesh sets as an object becomes smaller on screen.")
    lines.append("LOD0 is usually the close, high-detail version. Later LODs are usually cheaper meshes or fewer renderers for distance viewing.")
    lines.append("This is a major VR/mobile optimisation: the nearby object stays detailed, but distant scenery costs far fewer triangles and draw calls.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_light_probe_group(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["💡 Light Probe Group inspector"]
    if data is None:
        lines.append("Unable to read LightProbeGroup data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    probes = _as_list(_get_any(data, "m_ProbePositions", "probePositions", "m_Probes", "probes", default=None))
    dering = _get_any(data, "m_Dering", "dering", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    if enabled is not None:
        lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Probe positions: {len(probes)}")

    if probes:
        bounds = _vec3_bounds(probes)
        if bounds is not None:
            mins, maxs = bounds
            size = (maxs[0] - mins[0], maxs[1] - mins[1], maxs[2] - mins[2])
            lines.append(f"Bounds min: {_fmt_float(mins[0])}, {_fmt_float(mins[1])}, {_fmt_float(mins[2])}")
            lines.append(f"Bounds max: {_fmt_float(maxs[0])}, {_fmt_float(maxs[1])}, {_fmt_float(maxs[2])}")
            lines.append(f"Approx volume size: {_fmt_float(size[0])} × {_fmt_float(size[1])} × {_fmt_float(size[2])}")
        lines.append("")
        lines.append("📍 Probe samples")
        for i, p in enumerate(probes[:10], 1):
            lines.append(f"  {i}: {_fmt_vec3(p)}")
        if len(probes) > 10:
            lines.append(f"  ... {len(probes) - 10} more probe position(s)")

    if dering is not None:
        lines.append("")
        lines.append(f"Dering: {_bool_text(dering)}")

    known = {"m_GameObject", "m_Enabled", "m_ProbePositions", "m_Probes", "m_Dering"}
    _append_extra_lighting_fields(lines, data, known, bundle_index)

    lines.append("")
    lines.append("🧠 Light probe insight")
    lines.append("A Light Probe Group stores sample points for indirect/baked lighting. Moving objects can sample nearby probes so they inherit the colour of the surrounding baked light without using many realtime lights.")
    lines.append("For mobile/VR this is very useful: static walls can use lightmaps, while dynamic objects use probes for cheap ambient/indirect light.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_lighting_settings(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🌗 Lighting Settings inspector"]
    if data is None:
        lines.append("Unable to read LightingSettings data.")
        return lines

    name = _get_any(data, "m_Name", "name", default=getattr(record, "name", ""))
    if name:
        lines.append(f"Name: {name}")

    gi_workflow = _get_any(data, "m_GIWorkflowMode", "giWorkflowMode", default=None)
    lightmapper = _nested_get_any(data, "m_LightmapEditorSettings.m_Lightmapper", "m_LightmapEditorSettings.lightmapper", "m_Lightmapper", default=None)
    mixed_mode = _nested_get_any(data, "m_LightmapEditorSettings.m_MixedBakeMode", "m_LightmapEditorSettings.mixedBakeMode", "m_MixedBakeMode", default=None)
    bake_res = _nested_get_any(data, "m_LightmapEditorSettings.m_BakeResolution", "m_LightmapEditorSettings.m_Resolution", "m_BakeResolution", default=None)
    realtime_res = _nested_get_any(data, "m_LightmapEditorSettings.m_Resolution", "m_RealtimeResolution", default=None)
    atlas = _nested_get_any(data, "m_LightmapEditorSettings.m_AtlasSize", "m_LightmapEditorSettings.m_TextureWidth", "m_AtlasSize", default=None)
    ao = _nested_get_any(data, "m_LightmapEditorSettings.m_AO", "m_LightmapEditorSettings.m_CompAOExponent", "m_AO", default=None)
    baked_enabled = _nested_get_any(data, "m_GISettings.m_EnableBakedLightmaps", "m_EnableBakedLightmaps", default=None)
    realtime_enabled = _nested_get_any(data, "m_GISettings.m_EnableRealtimeLightmaps", "m_EnableRealtimeLightmaps", default=None)
    bounce_scale = _nested_get_any(data, "m_GISettings.m_BounceScale", "m_BounceScale", default=None)
    indirect_scale = _nested_get_any(data, "m_GISettings.m_IndirectOutputScale", "m_IndirectOutputScale", default=None)
    albedo_boost = _nested_get_any(data, "m_GISettings.m_AlbedoBoost", "m_AlbedoBoost", default=None)
    lighting_data = _get_any(data, "m_LightingDataAsset", "lightingDataAsset", default=None)
    lightmap_params = _nested_get_any(data, "m_LightmapEditorSettings.m_LightmapParameters", "m_LightmapParameters", default=None)

    lines.append("")
    lines.append("⚙ Global illumination")
    if gi_workflow is not None:
        lines.append(f"  GI workflow mode: {gi_workflow}")
    if baked_enabled is not None:
        lines.append(f"  Baked lightmaps enabled: {_bool_text(baked_enabled)}")
    if realtime_enabled is not None:
        lines.append(f"  Realtime lightmaps enabled: {_bool_text(realtime_enabled)}")
    if mixed_mode is not None:
        lines.append(f"  Mixed bake mode: {mixed_mode}")
    if lightmapper is not None:
        lines.append(f"  Lightmapper: {lightmapper}")
    if bounce_scale is not None:
        lines.append(f"  Bounce scale: {_fmt_float(bounce_scale)}")
    if indirect_scale is not None:
        lines.append(f"  Indirect output scale: {_fmt_float(indirect_scale)}")
    if albedo_boost is not None:
        lines.append(f"  Albedo boost: {_fmt_float(albedo_boost)}")

    lines.append("")
    lines.append("🗺 Lightmap bake settings")
    if bake_res is not None:
        lines.append(f"  Bake resolution: {_fmt_float(bake_res)} texels/unit")
    if realtime_res is not None:
        lines.append(f"  Realtime resolution: {_fmt_float(realtime_res)} texels/unit")
    if atlas is not None:
        lines.append(f"  Atlas size: {atlas}")
    if ao is not None:
        lines.append(f"  Ambient occlusion setting: {_light_setting_value_text(ao, bundle_index)}")
    if lightmap_params is not None and _pptr_path_id(lightmap_params) not in (None, 0):
        lines.append(f"  Lightmap parameters: {_pptr_text(lightmap_params, bundle_index)}")
    if lighting_data is not None and _pptr_path_id(lighting_data) not in (None, 0):
        lines.append(f"  Lighting data asset: {_pptr_text(lighting_data, bundle_index)}")

    known = {
        "m_Name", "m_ObjectHideFlags", "m_CorrespondingSourceObject", "m_PrefabInstance", "m_PrefabAsset",
        "m_GIWorkflowMode", "m_GISettings", "m_LightmapEditorSettings", "m_LightingDataAsset",
        "m_RuntimeCPUUsage", "m_LightmapSnapshot", "m_UseShadowmask", "m_LightmapParameters",
    }
    _append_extra_lighting_fields(lines, data, known, bundle_index)

    lines.append("")
    lines.append("🧠 Lighting settings insight")
    lines.append("LightingSettings describes how Unity baked or generated the scene lighting: lightmapper choice, lightmap resolution, mixed lighting mode, indirect/bounce multipliers and related bake options.")
    lines.append("In a shipped game this is often useful as provenance/debug data. The actual runtime lighting may already be baked into lightmaps, probes, textures or shader data.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _lightmaps_mode_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
    except Exception:
        return str(value)
    names = {
        0: "0 (Non-directional)",
        1: "1 (Combined directional)",
        2: "2 (Separate directional / legacy)",
    }
    return names.get(n, str(n))


def _describe_lightmap_settings(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🌗 Lightmap Settings inspector"]
    if data is None:
        lines.append("Unable to read LightmapSettings data.")
        return lines

    name = _get_any(data, "m_Name", "name", default=getattr(record, "name", ""))
    if name:
        lines.append(f"Name: {name}")

    lightmaps = _as_list(_get_any(data, "m_Lightmaps", "lightmaps", default=None))
    lightmaps_mode = _get_any(data, "m_LightmapsMode", "lightmapsMode", default=None)
    probes = _get_any(data, "m_LightProbes", "lightProbes", default=None)
    lighting_data = _get_any(data, "m_LightingDataAsset", "lightingDataAsset", default=None)
    baked_color_space = _get_any(data, "m_BakedColorSpace", "bakedColorSpace", default=None)

    lines.append(f"Lightmap entries: {len(lightmaps)}")
    if lightmaps_mode is not None:
        lines.append(f"Lightmaps mode: {_lightmaps_mode_text(lightmaps_mode)}")
    if baked_color_space is not None:
        lines.append(f"Baked colour space: {baked_color_space}")
    if probes is not None and _pptr_path_id(probes) not in (None, 0):
        lines.append(f"Light probes asset: {_pptr_text(probes, bundle_index)}")
    if lighting_data is not None and _pptr_path_id(lighting_data) not in (None, 0):
        lines.append(f"Lighting data asset: {_pptr_text(lighting_data, bundle_index)}")

    if lightmaps:
        lines.append("")
        lines.append("🗺 Lightmap texture references")
        for i, lm in enumerate(lightmaps[:8], 1):
            color = _get_any(lm, "m_Lightmap", "lightmapColor", "color", "m_LightmapColor", default=None)
            direction = _get_any(lm, "m_DirLightmap", "lightmapDir", "direction", "m_LightmapDir", default=None)
            shadow = _get_any(lm, "m_ShadowMask", "shadowMask", "m_ShadowMaskTexture", default=None)
            lines.append(f"  Entry {i}:")
            if color is not None and _pptr_path_id(color) not in (None, 0):
                lines.append(f"    Colour lightmap: {_pptr_text(color, bundle_index)}")
                lines.extend(_pptr_resolution_lines("Colour", color, bundle_index, indent="      "))
            if direction is not None and _pptr_path_id(direction) not in (None, 0):
                lines.append(f"    Direction lightmap: {_pptr_text(direction, bundle_index)}")
                lines.extend(_pptr_resolution_lines("Direction", direction, bundle_index, indent="      "))
            if shadow is not None and _pptr_path_id(shadow) not in (None, 0):
                lines.append(f"    Shadow mask: {_pptr_text(shadow, bundle_index)}")
                lines.extend(_pptr_resolution_lines("Shadow mask", shadow, bundle_index, indent="      "))
        if len(lightmaps) > 8:
            lines.append(f"  ... {len(lightmaps) - 8} more lightmap entrie(s)")

    known = {
        "m_Name", "m_ObjectHideFlags", "m_CorrespondingSourceObject", "m_PrefabInstance", "m_PrefabAsset",
        "m_Lightmaps", "m_LightmapsMode", "m_LightProbes", "m_LightingDataAsset", "m_BakedColorSpace",
        "m_UseDualLightmapsInForward", "m_EnlightenSceneMapping", "m_GISettings", "m_LightmapEditorSettings",
    }
    _append_extra_lighting_fields(lines, data, known, bundle_index)

    lines.append("")
    lines.append("🧠 Lightmap settings insight")
    lines.append("LightmapSettings is the scene-level link between rendered geometry and baked lighting textures. MeshRenderers usually store lightmap index/scale-offset values that point into these lightmap arrays.")
    lines.append("For VR this is a major optimisation: complex static lighting and shadows can be precomputed into textures instead of recalculated every frame.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def _light_type_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
    except Exception:
        return str(value)
    names = {
        0: "0 (Spot)",
        1: "1 (Directional / sun)",
        2: "2 (Point / bulb)",
        3: "3 (Area)",
        4: "4 (Rectangle)",
        5: "5 (Disc)",
    }
    return names.get(n, str(n))


def _light_mode_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
    except Exception:
        return str(value)
    # Unity has changed/extended serialized names here over time. Keep the raw
    # number visible while giving the usual LightmapBakeType meaning.
    names = {
        0: "0 (Realtime / dynamic)",
        1: "1 (Mixed / baked + realtime)",
        2: "2 (Baked)",
        4: "4 (Baked, newer serialized value)",
    }
    return names.get(n, str(n))


def _light_shadow_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
    except Exception:
        return str(value)
    names = {
        0: "0 (No shadows)",
        1: "1 (Hard shadows)",
        2: "2 (Soft shadows)",
    }
    return names.get(n, str(n))


def _light_render_mode_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
    except Exception:
        return str(value)
    names = {
        0: "0 (Auto)",
        1: "1 (Important)",
        2: "2 (Not important)",
    }
    return names.get(n, str(n))


def _describe_light(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["💡 Light inspector"]
    if data is None:
        lines.append("Unable to read Light data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    light_type = _get_any(data, "m_Type", "type", "lightType", default=None)
    colour = _get_any(data, "m_Color", "color", "colour", default=None)
    intensity = _get_any(data, "m_Intensity", "intensity", default=None)
    range_value = _get_any(data, "m_Range", "range", default=None)
    spot_angle = _get_any(data, "m_SpotAngle", "spotAngle", default=None)
    inner_spot_angle = _get_any(data, "m_InnerSpotAngle", "innerSpotAngle", default=None)
    cookie = _get_any(data, "m_Cookie", "cookie", default=None)
    cookie_size = _get_any(data, "m_CookieSize", "cookieSize", default=None)
    shadows = _get_any(data, "m_Shadows", "shadows", default=None)
    shadow_strength = _get_any(data, "m_ShadowStrength", "shadowStrength", default=None)
    shadow_resolution = _get_any(data, "m_ShadowResolution", "shadowResolution", default=None)
    shadow_bias = _get_any(data, "m_ShadowBias", "shadowBias", default=None)
    shadow_normal_bias = _get_any(data, "m_ShadowNormalBias", "shadowNormalBias", default=None)
    render_mode = _get_any(data, "m_RenderMode", "renderMode", default=None)
    lightmapping = _get_any(data, "m_Lightmapping", "lightmapping", "lightmapBakeType", default=None)
    bounce = _get_any(data, "m_BounceIntensity", "bounceIntensity", default=None)
    culling_mask = _get_any(data, "m_CullingMask", "cullingMask", default=None)
    use_temp = _get_any(data, "m_UseColorTemperature", "useColorTemperature", default=None)
    temp = _get_any(data, "m_ColorTemperature", "colorTemperature", default=None)
    flare = _get_any(data, "m_Flare", "flare", default=None)
    draw_halo = _get_any(data, "m_DrawHalo", "drawHalo", default=None)
    shape = _get_any(data, "m_Shape", "shape", default=None)
    area_size = _get_any(data, "m_AreaSize", "areaSize", "m_Size", "size", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Type: {_light_type_text(light_type)}")
    if colour is not None:
        lines.append(f"Colour: {_colour_line(colour)}")
    if intensity is not None:
        lines.append(f"Intensity: {_fmt_float(intensity)}")
    if range_value is not None:
        lines.append(f"Range: {_fmt_float(range_value)}")
    if spot_angle is not None:
        lines.append(f"Spot angle: {_fmt_float(spot_angle)}°")
    if inner_spot_angle is not None:
        lines.append(f"Inner spot angle: {_fmt_float(inner_spot_angle)}°")
    if area_size is not None:
        # Area/rectangle lights may expose Vector2 size or a single scalar.
        v2 = _vec2_tuple(area_size, None)
        lines.append(f"Area size: {_fmt_vec2(area_size) if v2 is not None else _fmt_float(area_size)}")
    if shape is not None:
        lines.append(f"Shape: {shape}")

    lines.append("")
    lines.append("🌗 Shadows / baking")
    lines.append(f"  Light mode: {_light_mode_text(lightmapping)}")
    lines.append(f"  Shadows: {_light_shadow_text(shadows)}")
    if shadow_strength is not None:
        lines.append(f"  Shadow strength: {_fmt_float(shadow_strength)}")
    if shadow_resolution is not None:
        lines.append(f"  Shadow resolution: {shadow_resolution}")
    if shadow_bias is not None:
        lines.append(f"  Shadow bias: {_fmt_float(shadow_bias)}")
    if shadow_normal_bias is not None:
        lines.append(f"  Shadow normal bias: {_fmt_float(shadow_normal_bias)}")
    if bounce is not None:
        lines.append(f"  Bounce / indirect multiplier: {_fmt_float(bounce)}")

    lines.append("")
    lines.append("🖼 Rendering / masks")
    lines.append(f"  Render mode: {_light_render_mode_text(render_mode)}")
    if culling_mask is not None:
        lines.append(f"  Culling mask: {_layer_mask_text(culling_mask)}")
    if cookie is not None and _pptr_path_id(cookie) not in (None, 0):
        lines.append(f"  Cookie texture: {_pptr_text(cookie, bundle_index)}")
    if cookie_size is not None:
        lines.append(f"  Cookie size: {_fmt_float(cookie_size)}")
    if use_temp is not None:
        lines.append(f"  Use colour temperature: {_bool_text(use_temp)}")
    if temp is not None:
        lines.append(f"  Colour temperature: {_fmt_float(temp)} K")
    if flare is not None and _pptr_path_id(flare) not in (None, 0):
        lines.append(f"  Flare: {_pptr_text(flare, bundle_index)}")
    if draw_halo is not None:
        lines.append(f"  Draw halo: {_bool_text(draw_halo)}")

    fields = [f for f in _anim_object_fields(data) if f.startswith("m_")]
    known = {
        "m_GameObject", "m_Enabled", "m_Type", "m_Color", "m_Intensity", "m_Range", "m_SpotAngle",
        "m_InnerSpotAngle", "m_Cookie", "m_CookieSize", "m_Shadows", "m_ShadowStrength",
        "m_ShadowResolution", "m_ShadowBias", "m_ShadowNormalBias", "m_RenderMode", "m_Lightmapping",
        "m_BounceIntensity", "m_CullingMask", "m_UseColorTemperature", "m_ColorTemperature", "m_Flare",
        "m_DrawHalo", "m_Shape", "m_AreaSize", "m_Size",
    }
    extra = [f for f in fields if f not in known]
    if extra:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(extra[:30]) + (" ..." if len(extra) > 30 else ""))

    lines.append("")
    lines.append("🎞 Light influence visual")
    lines.append("  Preview: a symbolic light shape is shown in the top preview panel: sun rays, point range sphere, spot cone, or area panel.")

    lines.append("")
    lines.append("🧠 Light insight")
    lines.append("A Light component describes illumination for the scene. The Transform gives its position/direction; the Light fields give colour, intensity, range, shadows and baking behaviour.")
    lines.append("In mobile/VR games many lights are baked into lightmaps or probes, so a Light record may be authoring/baking data rather than a costly realtime light drawn every frame.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def _describe_camera(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["📷 Camera inspector"]
    if data is None:
        lines.append("Unable to read Camera data.")
        return lines

    game_object = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    clear_flags = _get_any(data, "m_ClearFlags", "clearFlags", default=None)
    bg = _get_any(data, "m_BackGroundColor", "m_BackgroundColor", "backgroundColor", default=None)
    projection = _get_any(data, "m_ProjectionMatrixMode", "projectionMatrixMode", default=None)
    fov = _get_any(data, "field of view", "fieldOfView", "m_FieldOfView", "m_FOV", default=None)
    near_clip = _get_any(data, "near clip plane", "nearClipPlane", "m_NearClipPlane", default=None)
    far_clip = _get_any(data, "far clip plane", "farClipPlane", "m_FarClipPlane", default=None)
    ortho = _get_any(data, "orthographic", "m_Orthographic", default=None)
    ortho_size = _get_any(data, "orthographic size", "orthographicSize", "m_OrthographicSize", default=None)
    depth = _get_any(data, "m_Depth", "depth", default=None)
    viewport = _get_any(data, "m_NormalizedViewPortRect", "normalizedViewPortRect", "rect", default=None)
    culling_mask = _get_any(data, "m_CullingMask", "cullingMask", default=None)
    target_texture = _get_any(data, "m_TargetTexture", "targetTexture", default=None)
    target_display = _get_any(data, "m_TargetDisplay", "targetDisplay", default=None)
    hdr = _get_any(data, "m_HDR", "allowHDR", "allowHdr", default=None)
    msaa = _get_any(data, "m_AllowMSAA", "allowMSAA", default=None)
    occlusion = _get_any(data, "m_OcclusionCulling", "useOcclusionCulling", default=None)

    lines.append(f"Object: {_pptr_text(game_object, bundle_index)}")
    lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Clear flags: {_camera_clear_flags_text(clear_flags)}")
    if bg is not None:
        lines.append(f"Background colour: {_colour_line(bg)}")
    if depth is not None:
        lines.append(f"Depth / render order: {_fmt_float(depth)}")
    if target_display is not None:
        lines.append(f"Target display: {target_display}")
    if target_texture is not None and _pptr_path_id(target_texture) not in (None, 0):
        lines.append(f"Target texture: {_pptr_text(target_texture, bundle_index)}")

    lines.append("")
    lines.append("🎥 Lens / projection")
    lines.append(f"  Orthographic: {_bool_text(ortho)}")
    if ortho:
        if ortho_size is not None:
            lines.append(f"  Orthographic size: {_fmt_float(ortho_size)}")
    else:
        if fov is not None:
            lines.append(f"  Field of view: {_fmt_float(fov)}°")
    if near_clip is not None or far_clip is not None:
        lines.append(f"  Clipping planes: near {_fmt_float(near_clip)}, far {_fmt_float(far_clip)}")
    if projection is not None:
        lines.append(f"  Projection matrix mode: {projection}")

    # Physical-camera/newer fields, shown only when present.
    sensor_size = _get_any(data, "m_SensorSize", "sensorSize", default=None)
    lens_shift = _get_any(data, "m_LensShift", "lensShift", default=None)
    focal_length = _get_any(data, "m_FocalLength", "focalLength", default=None)
    gate_fit = _get_any(data, "m_GateFitMode", "gateFitMode", default=None)
    fov_axis = _get_any(data, "m_FOVAxisMode", "fovAxisMode", default=None)
    if any(v is not None for v in (sensor_size, lens_shift, focal_length, gate_fit, fov_axis)):
        lines.append("")
        lines.append("📸 Physical camera fields")
        if focal_length is not None:
            lines.append(f"  Focal length: {_fmt_float(focal_length)} mm")
        if sensor_size is not None:
            lines.append(f"  Sensor size: {_fmt_vec2(sensor_size)}")
        if lens_shift is not None:
            lines.append(f"  Lens shift: {_fmt_vec2(lens_shift)}")
        if gate_fit is not None:
            lines.append(f"  Gate fit mode: {gate_fit}")
        if fov_axis is not None:
            lines.append(f"  FOV axis mode: {fov_axis}")

    visual = _camera_lens_visual_lines(focal_length, sensor_size, fov, ortho, ortho_size, lens_shift)
    if visual:
        lines.append("")
        lines.extend(visual)

    lines.append("")
    lines.append("🖼 View / layers")
    if viewport is not None:
        lines.append(f"  Normalized viewport: {_rect_text(viewport)}")
    else:
        lines.append("  Normalized viewport: -")
    if culling_mask is not None:
        lines.append(f"  Culling mask: {_layer_mask_text(culling_mask)}")
    if hdr is not None:
        lines.append(f"  HDR: {_bool_text(hdr)}")
    if msaa is not None:
        lines.append(f"  MSAA: {_bool_text(msaa)}")
    if occlusion is not None:
        lines.append(f"  Occlusion culling: {_bool_text(occlusion)}")

    fields = [f for f in _anim_object_fields(data) if f.startswith("m_")]
    known = {
        "m_GameObject", "m_Enabled", "m_ClearFlags", "m_BackGroundColor", "m_BackgroundColor", "m_Depth",
        "m_TargetDisplay", "m_TargetTexture", "m_ProjectionMatrixMode", "m_FieldOfView", "m_FOV",
        "m_NearClipPlane", "m_FarClipPlane", "m_Orthographic", "m_OrthographicSize", "m_NormalizedViewPortRect",
        "m_CullingMask", "m_HDR", "m_AllowMSAA", "m_OcclusionCulling", "m_SensorSize", "m_LensShift",
        "m_FocalLength", "m_GateFitMode", "m_FOVAxisMode",
    }
    extra = [f for f in fields if f not in known]
    if extra:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(extra[:30]) + (" ..." if len(extra) > 30 else ""))

    lines.append("")
    lines.append("🧠 Camera insight")
    lines.append("A Camera is a viewpoint in the Unity scene. It decides what part of the world is rendered, what layers it can see, and how the view is projected.")
    lines.append("In level bundles, cameras are often used for UI render targets, preview views, cut-scene/animation views, minimaps, or fixed scene viewpoints rather than the player's headset camera.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _canvas_render_mode_text(value: Any) -> str:
    try:
        n = int(value)
    except Exception:
        return str(value) if value is not None else "-"
    names = {
        0: "0 (Screen Space - Overlay)",
        1: "1 (Screen Space - Camera)",
        2: "2 (World Space)",
    }
    return names.get(n, str(n))


def _canvas_extra_channels_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
    except Exception:
        return str(value)
    flags = []
    known = [
        (1, "TexCoord1"),
        (2, "TexCoord2"),
        (4, "TexCoord3"),
        (8, "Normal"),
        (16, "Tangent"),
    ]
    for bit, name in known:
        if n & bit:
            flags.append(name)
    return f"{n}" + (f" ({', '.join(flags)})" if flags else "")


def _canvas_sorting_layer_text(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return str(int(value))
    except Exception:
        return str(value)


def _ui_gameobject_component_lines(go_pptr: Any, bundle_index: Any | None, current_type: str = "") -> list[str]:
    """Show likely sibling UI components on the same GameObject."""
    go_pid = _pptr_path_id(go_pptr)
    if bundle_index is None or go_pid in (None, 0):
        return []
    wanted = (
        "RectTransform", "Transform", "Canvas", "CanvasGroup", "CanvasRenderer",
        "SpriteRenderer", "Image", "RawImage", "Text", "TextMeshProUGUI", "Button",
        "Mask", "RectMask2D", "Selectable",
    )
    siblings: list[Any] = []
    seen: set[int] = set()
    for typ in wanted:
        for rec in _records_with_gameobject(bundle_index, typ, go_pid):
            pid = getattr(rec, "path_id", None)
            if pid in seen:
                continue
            seen.add(pid)
            siblings.append(rec)
    if not siblings:
        return []
    lines = ["", "🧩 UI components on same object"]
    for rec in siblings[:24]:
        marker = "  ← this" if rec.type_name == current_type else ""
        lines.append(f"  {friendly_type_name(rec.type_name)} - {rec.name}  (PathID {rec.path_id}){marker}")
    if len(siblings) > 24:
        lines.append(f"  ... {len(siblings) - 24} more components")
    return lines



def _anchor_mode_text(anchor_min: tuple[float, float] | None, anchor_max: tuple[float, float] | None) -> str:
    if anchor_min is None or anchor_max is None:
        return "-"
    ax0, ay0 = anchor_min
    ax1, ay1 = anchor_max
    eps = 0.00001
    stretch_x = abs(ax0 - ax1) > eps
    stretch_y = abs(ay0 - ay1) > eps
    if stretch_x and stretch_y:
        return "stretch both axes"
    if stretch_x:
        return "stretch horizontally"
    if stretch_y:
        return "stretch vertically"
    # Common anchor points.
    x_name = "left" if ax0 <= eps else "right" if abs(ax0 - 1.0) <= eps else "centre" if abs(ax0 - 0.5) <= eps else f"x={_fmt_float(ax0)}"
    y_name = "bottom" if ay0 <= eps else "top" if abs(ay0 - 1.0) <= eps else "middle" if abs(ay0 - 0.5) <= eps else f"y={_fmt_float(ay0)}"
    return f"fixed anchor at {x_name} / {y_name}"


def _describe_rect_transform(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["▭ RectTransform inspector"]
    if data is None:
        lines.append("Unable to read RectTransform data.")
        return lines

    go = _get_any(data, "m_GameObject", "gameObject", default=None)
    father = _get_any(data, "m_Father", "father", "parent", default=None)
    children = _as_list(_get_any(data, "m_Children", "children", default=None))
    root_order = _get_any(data, "m_RootOrder", "rootOrder", default=None)

    local_pos = _vec3_tuple(_get_any(data, "m_LocalPosition", "localPosition", default=None), None)
    local_rot = _vec4_tuple(_get_any(data, "m_LocalRotation", "localRotation", default=None), None)
    local_scale = _vec3_tuple(_get_any(data, "m_LocalScale", "localScale", default=None), None)
    euler_hint = _vec3_tuple(_get_any(data, "m_LocalEulerAnglesHint", "localEulerAnglesHint", default=None), None)

    anchor_min = _vec2_tuple(_get_any(data, "m_AnchorMin", "anchorMin", default=None), None)
    anchor_max = _vec2_tuple(_get_any(data, "m_AnchorMax", "anchorMax", default=None), None)
    anchored_pos = _vec2_tuple(_get_any(data, "m_AnchoredPosition", "anchoredPosition", default=None), None)
    size_delta = _vec2_tuple(_get_any(data, "m_SizeDelta", "sizeDelta", default=None), None)
    pivot = _vec2_tuple(_get_any(data, "m_Pivot", "pivot", default=None), None)

    lines.append(f"Object: {_pptr_text(go, bundle_index)}")
    lines.append(f"Parent transform: {_pptr_text(father, bundle_index)}")
    if root_order is not None:
        lines.append(f"Root/order index: {root_order}")
    lines.append(f"Children: {len(children)}")

    lines.append("")
    lines.append("↔ Local transform")
    lines.append(f"  Position: {_fmt_vec3(local_pos)}")
    lines.append(f"  Rotation quaternion: {_fmt_vec4(local_rot)}")
    if euler_hint is not None:
        lines.append(f"  Euler hint: {_fmt_vec3(euler_hint)}")
    lines.append(f"  Scale: {_fmt_vec3(local_scale)}")

    lines.append("")
    lines.append("📐 UI rectangle / anchors")
    lines.append(f"  Anchor min: {_fmt_vec2(anchor_min)}")
    lines.append(f"  Anchor max: {_fmt_vec2(anchor_max)}")
    lines.append(f"  Anchor mode: {_anchor_mode_text(anchor_min, anchor_max)}")
    lines.append(f"  Anchored position: {_fmt_vec2(anchored_pos)}")
    lines.append(f"  Size delta: {_fmt_vec2(size_delta)}")
    lines.append(f"  Pivot: {_fmt_vec2(pivot)}")

    if anchor_min is not None and anchor_max is not None and size_delta is not None and pivot is not None:
        ax0, ay0 = anchor_min
        ax1, ay1 = anchor_max
        stretch_x = abs(ax0 - ax1) > 0.00001
        stretch_y = abs(ay0 - ay1) > 0.00001
        lines.append("")
        lines.append("🧭 Layout meaning")
        if not stretch_x and not stretch_y:
            w, h = size_delta
            px, py = pivot
            mn = (-px * w, -py * h)
            mx = ((1.0 - px) * w, (1.0 - py) * h)
            lines.append("  This RectTransform has fixed anchors, so Size Delta is approximately the element's local width/height.")
            lines.append(f"  Local rect around pivot: x {_fmt_float(mn[0])} → {_fmt_float(mx[0])}, y {_fmt_float(mn[1])} → {_fmt_float(mx[1])}")
        else:
            parts = []
            if stretch_x:
                parts.append("width follows parent anchor span plus Size Delta X")
            else:
                parts.append("width is mostly Size Delta X")
            if stretch_y:
                parts.append("height follows parent anchor span plus Size Delta Y")
            else:
                parts.append("height is mostly Size Delta Y")
            lines.append("  This RectTransform stretches against its parent: " + "; ".join(parts) + ".")
            lines.append("  Final on-screen size depends on the parent RectTransform/Canvas, not this record alone.")

    lines.extend(_ui_gameobject_component_lines(go, bundle_index, "RectTransform"))

    fields = [f for f in _anim_object_fields(data) if f.startswith("m_")]
    known = {
        "m_GameObject", "m_LocalRotation", "m_LocalPosition", "m_LocalScale", "m_Children", "m_Father", "m_RootOrder",
        "m_LocalEulerAnglesHint", "m_AnchorMin", "m_AnchorMax", "m_AnchoredPosition", "m_SizeDelta", "m_Pivot",
    }
    extra = [f for f in fields if f not in known]
    if extra:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(extra[:24]) + (" ..." if len(extra) > 24 else ""))

    lines.append("")
    lines.append("🧠 RectTransform insight")
    lines.append("A RectTransform is the UI version of Transform. It still has position/rotation/scale, but it also has anchors, pivot and size rules for placing a rectangle inside a Canvas or parent UI panel.")
    lines.append("It is not quite a matrix by itself: Unity combines the local transform with anchor/pivot layout to decide where the UI rectangle appears.")
    lines.append("For UI objects, RectTransform is often the key record to inspect before CanvasRenderer, Image, Text, Button or Sprite-style UI components.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def _describe_canvas(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🖼 Canvas inspector"]
    if data is None:
        lines.append("Unable to read Canvas data.")
        return lines

    go = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    render_mode = _get_any(data, "m_RenderMode", "renderMode", default=None)
    camera = _get_any(data, "m_Camera", "m_WorldCamera", "worldCamera", "eventCamera", default=None)
    plane_distance = _get_any(data, "m_PlaneDistance", "planeDistance", default=None)
    pixel_perfect = _get_any(data, "m_PixelPerfect", "pixelPerfect", default=None)
    receives_events = _get_any(data, "m_ReceivesEvents", "receivesEvents", default=None)
    override_sorting = _get_any(data, "m_OverrideSorting", "overrideSorting", default=None)
    sorting_layer = _get_any(data, "m_SortingLayerID", "sortingLayerID", default=None)
    sorting_order = _get_any(data, "m_SortingOrder", "sortingOrder", default=None)
    target_display = _get_any(data, "m_TargetDisplay", "targetDisplay", default=None)
    shader_channels = _get_any(data, "m_AdditionalShaderChannelsFlag", "m_AdditionalShaderChannels", "additionalShaderChannels", default=None)
    scale_factor = _get_any(data, "m_ScaleFactor", "scaleFactor", default=None)
    ref_ppu = _get_any(data, "m_ReferencePixelsPerUnit", "referencePixelsPerUnit", default=None)
    sorting_bucket_normalized_size = _get_any(data, "m_SortingBucketNormalizedSize", "sortingBucketNormalizedSize", default=None)

    lines.append(f"Object: {_pptr_text(go, bundle_index)}")
    lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Render mode: {_canvas_render_mode_text(render_mode)}")

    if camera is not None and _pptr_path_id(camera) not in (None, 0):
        lines.append(f"Camera: {_pptr_text(camera, bundle_index)}")
    if plane_distance is not None:
        lines.append(f"Plane distance: {_fmt_float(plane_distance)}")
    if target_display is not None:
        lines.append(f"Target display: {target_display}")
    if pixel_perfect is not None:
        lines.append(f"Pixel perfect: {_bool_text(pixel_perfect)}")
    if receives_events is not None:
        lines.append(f"Receives events: {_bool_text(receives_events)}")

    lines.append("")
    lines.append("📐 UI scale / sorting")
    if scale_factor is not None:
        lines.append(f"  Scale factor: {_fmt_float(scale_factor)}")
    if ref_ppu is not None:
        lines.append(f"  Reference pixels per unit: {_fmt_float(ref_ppu)}")
    if override_sorting is not None:
        lines.append(f"  Override sorting: {_bool_text(override_sorting)}")
    if sorting_layer is not None:
        lines.append(f"  Sorting layer ID: {_canvas_sorting_layer_text(sorting_layer)}")
    if sorting_order is not None:
        lines.append(f"  Sorting order: {sorting_order}")
    if sorting_bucket_normalized_size is not None:
        lines.append(f"  Sorting bucket normalized size: {_fmt_float(sorting_bucket_normalized_size)}")
    if shader_channels is not None:
        lines.append(f"  Additional shader channels: {_canvas_extra_channels_text(shader_channels)}")

    lines.extend(_ui_gameobject_component_lines(go, bundle_index, "Canvas"))

    fields = [f for f in _anim_object_fields(data) if f.startswith("m_")]
    known = {
        "m_GameObject", "m_Enabled", "m_RenderMode", "m_Camera", "m_WorldCamera", "m_PlaneDistance",
        "m_PixelPerfect", "m_ReceivesEvents", "m_OverrideSorting", "m_SortingLayerID", "m_SortingOrder",
        "m_TargetDisplay", "m_AdditionalShaderChannelsFlag", "m_AdditionalShaderChannels", "m_ScaleFactor",
        "m_ReferencePixelsPerUnit", "m_SortingBucketNormalizedSize",
    }
    extra = [f for f in fields if f not in known]
    if extra:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(extra[:26]) + (" ..." if len(extra) > 26 else ""))

    lines.append("")
    lines.append("🧠 Canvas insight")
    lines.append("A Canvas is the surface/root that Unity uses to draw UI. It may be screen-space overlay, camera-space UI, or a world-space panel placed in the 3D scene.")
    lines.append("Child UI elements normally use RectTransform + CanvasRenderer plus an Image/Text/Button-style component. The Canvas controls how that UI layer is projected and sorted.")
    if render_mode is not None:
        try:
            rm = int(render_mode)
            if rm == 0:
                lines.append("This one is overlay-style UI: drawn directly over the screen/display.")
            elif rm == 1:
                lines.append("This one is camera-space UI: drawn by/relative to a Camera.")
            elif rm == 2:
                lines.append("This one is world-space UI: a flat UI panel placed inside the 3D world.")
        except Exception:
            pass

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_canvas_group(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🖼 Canvas Group inspector"]
    if data is None:
        lines.append("Unable to read CanvasGroup data.")
        return lines

    go = _get_any(data, "m_GameObject", "gameObject", default=None)
    enabled = _get_any(data, "m_Enabled", "enabled", default=None)
    alpha = _get_any(data, "m_Alpha", "alpha", default=None)
    interactable = _get_any(data, "m_Interactable", "interactable", default=None)
    blocks = _get_any(data, "m_BlocksRaycasts", "blocksRaycasts", default=None)
    ignore_parent = _get_any(data, "m_IgnoreParentGroups", "ignoreParentGroups", default=None)

    lines.append(f"Object: {_pptr_text(go, bundle_index)}")
    if enabled is not None:
        lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"Alpha / opacity: {_fmt_float(alpha)}")
    lines.append(f"Interactable: {_bool_text(interactable)}")
    lines.append(f"Blocks raycasts / clicks: {_bool_text(blocks)}")
    lines.append(f"Ignore parent groups: {_bool_text(ignore_parent)}")

    if alpha is not None:
        try:
            a = float(alpha)
            lines.append("")
            lines.append("👁 Visibility meaning")
            if a <= 0.001:
                lines.append("  Alpha is effectively 0: this group is visually invisible unless another shader/component overrides it.")
            elif a < 0.999:
                lines.append(f"  Alpha is partial: children are faded to about {a * 100:.0f}% opacity.")
            else:
                lines.append("  Alpha is full: this group does not fade its children.")
        except Exception:
            pass

    lines.extend(_ui_gameobject_component_lines(go, bundle_index, "CanvasGroup"))

    fields = [f for f in _anim_object_fields(data) if f.startswith("m_")]
    known = {"m_GameObject", "m_Enabled", "m_Alpha", "m_Interactable", "m_BlocksRaycasts", "m_IgnoreParentGroups"}
    extra = [f for f in fields if f not in known]
    if extra:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(extra[:20]) + (" ..." if len(extra) > 20 else ""))

    lines.append("")
    lines.append("🧠 CanvasGroup insight")
    lines.append("A CanvasGroup controls a whole UI branch. It can fade all child UI, disable interaction, or stop clicks/raycasts without changing every child element individually.")
    lines.append("This is often used for popups, dialogue boxes, menu panels, transitions, disabled UI, or fade-in/fade-out animation.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _canvas_renderer_material_lines(data: Any, bundle_index: Any | None) -> list[str]:
    lines: list[str] = []
    materials = []
    for name in ("m_Materials", "materials"):
        materials.extend(_as_list(_get_any(data, name, default=None)))
    single = _get_any(data, "m_Material", "material", default=None)
    if single is not None and _pptr_path_id(single) not in (None, 0):
        materials.append(single)
    pop_materials = _as_list(_get_any(data, "m_PopMaterials", "popMaterials", default=None))
    material_count = _get_any(data, "m_MaterialCount", "materialCount", default=None)
    pop_count = _get_any(data, "m_PopMaterialCount", "popMaterialCount", default=None)

    if material_count is not None or pop_count is not None or materials or pop_materials:
        lines.append("")
        lines.append("🎨 UI materials")
        if material_count is not None:
            lines.append(f"  Material count: {material_count}")
        if pop_count is not None:
            lines.append(f"  Pop material count: {pop_count}")
        for i, mat in enumerate(materials[:12]):
            lines.append(f"  Slot {i}: {_pptr_text(mat, bundle_index)}")
        if len(materials) > 12:
            lines.append(f"  ... {len(materials) - 12} more materials")
        if pop_materials:
            lines.append(f"  Pop materials: {len(pop_materials)}")
            for i, mat in enumerate(pop_materials[:8]):
                lines.append(f"    Pop {i}: {_pptr_text(mat, bundle_index)}")
    return lines


def _describe_canvas_renderer(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🖼 Canvas Renderer inspector"]
    if data is None:
        lines.append("Unable to read CanvasRenderer data.")
        return lines

    go = _get_any(data, "m_GameObject", "gameObject", default=None)
    cull_transparent = _get_any(data, "m_CullTransparentMesh", "cullTransparentMesh", default=None)
    cull = _get_any(data, "m_Cull", "cull", default=None)
    colour = _get_any(data, "m_Color", "m_Color", "color", default=None)
    alpha_texture = _get_any(data, "m_AlphaTexture", "alphaTexture", default=None)
    has_pop = _get_any(data, "m_HasPopInstruction", "hasPopInstruction", default=None)

    lines.append(f"Object: {_pptr_text(go, bundle_index)}")
    if colour is not None:
        lines.append(f"Colour: {_colour_line(colour)}")
    if cull_transparent is not None:
        lines.append(f"Cull transparent mesh: {_bool_text(cull_transparent)}")
    if cull is not None:
        lines.append(f"Culled: {_bool_text(cull)}")
    if has_pop is not None:
        lines.append(f"Has pop instruction: {_bool_text(has_pop)}")
    if alpha_texture is not None and _pptr_path_id(alpha_texture) not in (None, 0):
        lines.append(f"Alpha texture: {_pptr_text(alpha_texture, bundle_index)}")

    lines.extend(_canvas_renderer_material_lines(data, bundle_index))
    lines.extend(_ui_gameobject_component_lines(go, bundle_index, "CanvasRenderer"))

    fields = [f for f in _anim_object_fields(data) if f.startswith("m_")]
    known = {
        "m_GameObject", "m_Color", "m_CullTransparentMesh", "m_Cull", "m_HasPopInstruction", "m_AlphaTexture",
        "m_Materials", "m_Material", "m_MaterialCount", "m_PopMaterials", "m_PopMaterialCount",
    }
    extra = [f for f in fields if f not in known]
    if extra:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(extra[:24]) + (" ..." if len(extra) > 24 else ""))

    lines.append("")
    lines.append("🧠 CanvasRenderer insight")
    lines.append("CanvasRenderer is the low-level draw component for Unity UI. It usually does not define the artwork by itself; it draws geometry supplied by an Image, Text, RawImage, Mask or another UI Graphic component on the same GameObject.")
    lines.append("If this record looks plain, check the UI components on the same object: that is normally where the sprite, text, button state or image data lives.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


# ---------------------------------------------------------------------------
# MonoBehaviour / custom script field explorer
# ---------------------------------------------------------------------------

def _read_typetree(record: Any) -> Any | None:
    """Best-effort UnityPy typetree read.

    MonoBehaviour is the one Unity type where read() may only expose the Unity
    shell (m_GameObject/m_Script/m_Enabled), while read_typetree() can expose
    the serialized custom script fields when the bundle contains a typetree.
    This helper is deliberately safe: missing script metadata must never break
    the inspector.
    """
    try:
        return record.object.read_typetree()
    except Exception:
        return None


def _mono_is_pptr(value: Any) -> bool:
    return _pptr_path_id(value) is not None and any(
        _get_any(value, n, default=None) is not None
        for n in ("file_id", "fileID", "m_FileID", "FileID", "path_id", "pathID", "m_PathID", "PathID")
    )


def _mono_field_items(obj: Any) -> list[tuple[str, Any]]:
    if obj is None:
        return []
    if isinstance(obj, dict):
        return [(str(k), v) for k, v in obj.items()]
    items: list[tuple[str, Any]] = []
    for name in _anim_object_fields(obj):
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        items.append((name, value))
    return items


def _mono_value_brief(value: Any, bundle_index: Any | None = None, *, depth: int = 0) -> str:
    if value is None:
        return "-"
    if _mono_is_pptr(value):
        return _pptr_text(value, bundle_index)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return _fmt_float(value, 4)
    if isinstance(value, str):
        clean = value.replace("\r", "\\r").replace("\n", "\\n")
        if len(clean) > 140:
            clean = clean[:137] + "..."
        return f'"{clean}"'
    if isinstance(value, (bytes, bytearray)):
        return f"{len(value):,} byte(s)"

    v4 = _vec4_tuple(value, None)
    if v4 is not None:
        hx = _colour_hex(value)
        suffix = f" {hx}" if hx else ""
        return f"{_fmt_float(v4[0])}, {_fmt_float(v4[1])}, {_fmt_float(v4[2])}, {_fmt_float(v4[3])}{suffix}"
    v3 = _vec3_tuple(value, None)
    if v3 is not None:
        return f"{_fmt_float(v3[0])}, {_fmt_float(v3[1])}, {_fmt_float(v3[2])}"
    v2 = _vec2_tuple(value, None)
    if v2 is not None:
        return f"{_fmt_float(v2[0])}, {_fmt_float(v2[1])}"

    if isinstance(value, (list, tuple)):
        n = len(value)
        if n == 0:
            return "List[0]"
        if depth >= 1:
            return f"List[{n}]"
        sample = []
        for item in list(value)[:4]:
            sample.append(_mono_value_brief(item, bundle_index, depth=depth + 1))
        more = f", ... +{n - 4}" if n > 4 else ""
        return f"List[{n}] [{', '.join(sample)}{more}]"

    if isinstance(value, dict):
        return f"Object/dict with {len(value)} field(s)"

    fields = _mono_field_items(value)
    if fields:
        cls = value.__class__.__name__
        return f"{cls} with {len(fields)} field(s)"
    return str(value)


def _mono_collect_refs(obj: Any, bundle_index: Any | None, prefix: str = "", *, max_depth: int = 5, limit: int = 80, _seen: set[int] | None = None) -> list[tuple[str, str]]:
    if obj is None or limit <= 0:
        return []
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return []
    _seen.add(oid)

    if _mono_is_pptr(obj):
        pid = _pptr_path_id(obj)
        if pid not in (None, 0):
            return [(prefix or "reference", _pptr_text(obj, bundle_index))]
        return []

    if max_depth <= 0 or isinstance(obj, (str, bytes, bytearray, int, float, bool)):
        return []

    rows: list[tuple[str, str]] = []
    if isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj[:64]):
            rows.extend(_mono_collect_refs(item, bundle_index, f"{prefix}[{i}]" if prefix else f"[{i}]", max_depth=max_depth - 1, limit=limit - len(rows), _seen=_seen))
            if len(rows) >= limit:
                break
        return rows[:limit]

    for name, value in _mono_field_items(obj):
        if name in ("object", "assets_file") or name.startswith("_"):
            continue
        child_prefix = f"{prefix}.{name}" if prefix else name
        rows.extend(_mono_collect_refs(value, bundle_index, child_prefix, max_depth=max_depth - 1, limit=limit - len(rows), _seen=_seen))
        if len(rows) >= limit:
            break
    return rows[:limit]


def _mono_collect_strings(obj: Any, prefix: str = "", *, max_depth: int = 5, limit: int = 60, _seen: set[int] | None = None) -> list[tuple[str, str]]:
    if obj is None or limit <= 0:
        return []
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return []
    _seen.add(oid)

    if isinstance(obj, str):
        text = obj.strip()
        if text:
            if len(text) > 160:
                text = text[:157] + "..."
            return [(prefix or "string", text.replace("\r", "\\r").replace("\n", "\\n"))]
        return []
    if max_depth <= 0 or isinstance(obj, (bytes, bytearray, int, float, bool)) or _mono_is_pptr(obj):
        return []

    rows: list[tuple[str, str]] = []
    if isinstance(obj, (list, tuple)):
        for i, item in enumerate(obj[:64]):
            rows.extend(_mono_collect_strings(item, f"{prefix}[{i}]" if prefix else f"[{i}]", max_depth=max_depth - 1, limit=limit - len(rows), _seen=_seen))
            if len(rows) >= limit:
                break
        return rows[:limit]

    for name, value in _mono_field_items(obj):
        if name in ("object", "assets_file") or name.startswith("_"):
            continue
        child_prefix = f"{prefix}.{name}" if prefix else name
        rows.extend(_mono_collect_strings(value, child_prefix, max_depth=max_depth - 1, limit=limit - len(rows), _seen=_seen))
        if len(rows) >= limit:
            break
    return rows[:limit]


def _mono_script_details(script_rec: Any | None) -> tuple[str, list[str]]:
    if script_rec is None:
        return "-", []
    data = _read(script_rec)
    if data is None:
        return f"{friendly_type_name(script_rec.type_name)} - {script_rec.name}  (PathID {script_rec.path_id})", []
    class_name = _get_any(data, "m_ClassName", "class_name", "ClassName", default=None)
    namespace = _get_any(data, "m_Namespace", "namespace", "Namespace", default=None)
    assembly = _get_any(data, "m_AssemblyName", "assembly_name", "AssemblyName", default=None)
    exec_order = _get_any(data, "m_ExecutionOrder", "execution_order", default=None)
    props: list[str] = []
    if class_name:
        fq = f"{namespace}.{class_name}" if namespace else str(class_name)
        props.append(f"Class: {fq}")
    if assembly:
        props.append(f"Assembly: {assembly}")
    if exec_order not in (None, 0):
        props.append(f"Execution order: {exec_order}")
    return f"{friendly_type_name(script_rec.type_name)} - {script_rec.name}  (PathID {script_rec.path_id})", props


def _mono_top_source(record: Any, data: Any) -> tuple[str, Any]:
    tree = _read_typetree(record)
    if isinstance(tree, dict) and tree:
        return "typetree", tree
    return "read", data


def _describe_mono_behaviour(record: Any, bundle_index: Any | None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧩 MonoBehaviour / Script inspector"]
    if data is None:
        lines.append("Unable to read MonoBehaviour data.")
        return lines

    source_name, source = _mono_top_source(record, data)
    go = _get_any(source, "m_GameObject", "game_object", default=_get_any(data, "m_GameObject", "game_object", default=None))
    script = _get_any(source, "m_Script", "script", default=_get_any(data, "m_Script", "script", default=None))
    enabled = _get_any(source, "m_Enabled", "enabled", default=_get_any(data, "m_Enabled", "enabled", default=None))
    editor_id = _get_any(source, "m_EditorClassIdentifier", "editor_class_identifier", default=_get_any(data, "m_EditorClassIdentifier", "editor_class_identifier", default=None))

    lines.append(f"Source: {'Unity typetree / serialized fields' if source_name == 'typetree' else 'Unity object shell'}")
    if enabled is not None:
        lines.append(f"Enabled: {_bool_text(enabled)}")
    lines.append(f"GameObject: {_pptr_text(go, bundle_index)}")
    script_rec = _resolve_record(bundle_index, script)
    script_text, script_props = _mono_script_details(script_rec)
    if script_rec is None:
        script_text = _pptr_text(script, bundle_index)
    lines.append(f"Script asset: {script_text}")
    for prop in script_props:
        lines.append(f"  {prop}")
    if editor_id:
        lines.append(f"Editor class identifier: {editor_id}")

    # Top-level fields.  Keep Unity boilerplate visible above, but do not repeat
    # it in the custom field list unless the typetree only contains shell data.
    skip = {"m_GameObject", "game_object", "m_Script", "script", "m_Enabled", "enabled", "m_Name", "name"}
    fields = [(k, v) for k, v in _mono_field_items(source) if k not in skip and not k.startswith("_")]
    custom_fields = [(k, v) for k, v in fields if k != "m_EditorClassIdentifier"]

    lines.append("")
    lines.append(f"🧾 Readable fields ({len(custom_fields)})")
    if not custom_fields:
        lines.append("  No custom fields were exposed by UnityPy for this script.")
        lines.append("  This can happen when the bundle has no typetree or the game stores the script data in a form UnityPy cannot decode yet.")
    else:
        for name, value in custom_fields[:90]:
            lines.append(f"  {name}: {_mono_value_brief(value, bundle_index)}")
        if len(custom_fields) > 90:
            lines.append(f"  ... {len(custom_fields) - 90} more fields")

    refs = _mono_collect_refs(source, bundle_index, limit=90)
    # Avoid duplicating empty owner/script slots too much, but keep useful links.
    filtered_refs = []
    seen_ref = set()
    for path, text in refs:
        key = (path, text)
        if key in seen_ref:
            continue
        seen_ref.add(key)
        if text == "-":
            continue
        filtered_refs.append((path, text))

    if filtered_refs:
        lines.append("")
        lines.append(f"🔗 Object references found ({len(filtered_refs)})")
        for path, text in filtered_refs[:80]:
            lines.append(f"  {path}: {text}")
        if len(filtered_refs) > 80:
            lines.append(f"  ... {len(filtered_refs) - 80} more references")

    strings = _mono_collect_strings(source, limit=80)
    # Keep only meaningful strings and avoid repeating class id noise only.
    useful_strings = []
    seen_strings = set()
    for path, text in strings:
        if not text or (path == "m_EditorClassIdentifier" and len(strings) > 1):
            continue
        key = (path, text)
        if key in seen_strings:
            continue
        seen_strings.add(key)
        useful_strings.append((path, text))
    if useful_strings:
        lines.append("")
        lines.append(f"🔤 String values found ({len(useful_strings)})")
        for path, text in useful_strings[:60]:
            lines.append(f"  {path}: \"{text}\"")
        if len(useful_strings) > 60:
            lines.append(f"  ... {len(useful_strings) - 60} more strings")

    lines.append("")
    lines.append("🧠 MonoBehaviour insight")
    lines.append("MonoBehaviour is a custom Unity script component. The GameObject is the thing in the scene; the MonoBehaviour is extra game-specific behaviour or metadata attached to it.")
    lines.append("When Unity exposes a typetree, UBE can show script fields such as references, flags, numbers, strings, trigger settings, audio/event names, course data or VR interaction settings.")
    lines.append("If only the shell fields appear, the script exists but its custom serialized data was not available in this bundle/UnityPy decode path.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines

def _relationship_lines(record: Any, bundle_index: Any | None, asset_graph: Any | None) -> list[str]:
    if asset_graph is None:
        return []
    lines: list[str] = []
    try:
        refs = asset_graph.references(record, bundle_index)
    except Exception as e:
        return ["", f"⚠ Relationships could not be resolved: {e}"]

    if refs:
        lines.append("")
        lines.append(f"🔗 References ({len(refs)})")
        for rel in refs[:80]:
            status = "" if rel.resolved else "  ⚠ unresolved"
            target_kind = friendly_type_name(rel.target_type)
            src = f" [{getattr(rel, 'target_source_name', '')}]" if getattr(rel, 'target_source_name', '') else ""
            lines.append(f"  {rel.relationship}: {target_kind} - {rel.target_name}{src}{status}")
        if len(refs) > 80:
            lines.append(f"  ... {len(refs) - 80} more references")

    try:
        used_by = asset_graph.used_by(record, bundle_index)
    except Exception:
        used_by = []
    if used_by:
        lines.append("")
        lines.append(f"🔗 Used by ({len(used_by)})")
        for rel in used_by[:80]:
            source_kind = friendly_type_name(rel.source_type)
            src = f" [{getattr(rel, 'source_source_name', '')}]" if getattr(rel, 'source_source_name', '') else ""
            lines.append(f"  {source_kind} - {rel.source_name}{src}  [{rel.relationship}]")
        if len(used_by) > 80:
            lines.append(f"  ... {len(used_by) - 80} more users")
    return lines


# ---------------------------------------------------------------------------
# v1.8w NavMesh inspectors.
# ---------------------------------------------------------------------------

def _nav_list_len(value: Any) -> int | None:
    try:
        if value is None:
            return None
        if isinstance(value, (list, tuple, dict)):
            return len(value)
        if hasattr(value, "__len__") and not isinstance(value, (str, bytes, bytearray)):
            return len(value)
    except Exception:
        pass
    return None


def _nav_bytes_len(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    if isinstance(value, (list, tuple)):
        try:
            sample = list(value[:16])
            if sample and all(isinstance(x, int) and 0 <= int(x) <= 255 for x in sample):
                return len(value)
        except Exception:
            pass
    return None


def _nav_get(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    for name in names:
        value = _get_any(obj, name, default=None)
        if value is not None:
            return value
    return default


def _nav_common_counts(data: Any) -> list[str]:
    lines: list[str] = []
    for label, names in (
        ("Tiles", ("m_NavMeshTiles", "navMeshTiles", "m_Tiles", "tiles")),
        ("NavMesh sources", ("m_Sources", "sources", "m_NavMeshSources", "navMeshSources")),
        ("Off-mesh links", ("m_OffMeshLinks", "offMeshLinks", "m_Links", "links")),
        ("Areas/costs", ("m_Areas", "areas", "m_AreaCosts", "areaCosts", "m_NavMeshAreaCosts", "navMeshAreaCosts")),
        ("Agent/settings", ("m_AgentTypeSettings", "agentTypeSettings", "m_Settings", "settings", "m_BuildSettings", "buildSettings")),
    ):
        value = _nav_get(data, *names, default=None)
        count = _nav_list_len(value)
        if count is not None:
            lines.append(f"{label}: {count:,}")
        elif value is not None:
            size = _nav_bytes_len(value)
            if size is not None:
                lines.append(f"{label}: {human_bytes(size)} raw data")
            else:
                lines.append(f"{label}: present")
    return lines


def _nav_build_settings_lines(settings: Any, indent: str = "  ") -> list[str]:
    if settings is None:
        return []
    lines: list[str] = []
    field_map = (
        ("Agent type ID", ("agentTypeID", "m_AgentTypeID")),
        ("Agent radius", ("agentRadius", "m_AgentRadius")),
        ("Agent height", ("agentHeight", "m_AgentHeight")),
        ("Max slope", ("agentSlope", "m_AgentSlope", "maxSlope", "m_MaxSlope")),
        ("Step / climb", ("agentClimb", "m_AgentClimb", "ledgeDropHeight", "m_LedgeDropHeight")),
        ("Min region area", ("minRegionArea", "m_MinRegionArea")),
        ("Override voxel size", ("overrideVoxelSize", "m_OverrideVoxelSize")),
        ("Voxel size", ("voxelSize", "m_VoxelSize")),
        ("Override tile size", ("overrideTileSize", "m_OverrideTileSize")),
        ("Tile size", ("tileSize", "m_TileSize")),
        ("Build height mesh", ("buildHeightMesh", "m_BuildHeightMesh")),
    )
    for label, names in field_map:
        value = _nav_get(settings, *names, default=None)
        if value is not None:
            if isinstance(value, bool):
                lines.append(f"{indent}{label}: {_bool_text(value)}")
            elif _num_or_none(value) is not None:
                lines.append(f"{indent}{label}: {_fmt_float(value)}")
            else:
                lines.append(f"{indent}{label}: {value}")
    return lines


def _nav_area_lines(data: Any, limit: int = 12) -> list[str]:
    lines: list[str] = []
    names = _nav_get(data, "m_AreaNames", "areaNames", "m_NavMeshAreaNames", default=None)
    costs = _nav_get(data, "m_AreaCosts", "areaCosts", "m_NavMeshAreaCosts", default=None)
    area_list = _as_list(names)
    cost_list = _as_list(costs)
    if area_list:
        lines.append(f"Area names: {len(area_list):,}")
        for i, name in enumerate(area_list[:limit]):
            suffix = ""
            if i < len(cost_list):
                suffix = f"  cost {cost_list[i]}"
            lines.append(f"  {i}: {name}{suffix}")
        if len(area_list) > limit:
            lines.append(f"  ... {len(area_list) - limit} more areas")
    elif cost_list:
        lines.append(f"Area costs: {len(cost_list):,}")
        for i, cost in enumerate(cost_list[:limit]):
            lines.append(f"  {i}: {cost}")
        if len(cost_list) > limit:
            lines.append(f"  ... {len(cost_list) - limit} more costs")
    return lines


def _nav_value_text(value: Any) -> str:
    if value is None:
        return "-"
    vec3 = _vec3_tuple(value, None)
    if vec3 is not None:
        return _fmt_vec3(vec3)
    if isinstance(value, (bytes, bytearray)):
        return f"{human_bytes(len(value))} raw data"
    count = _nav_list_len(value)
    if count is not None and not isinstance(value, (str, bytes, bytearray)):
        return f"{count:,} item(s)"
    return str(value)


def _describe_navmesh_data(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = ["🧭 NavMeshData inspector"]
    if data is None:
        lines.append("Unable to read NavMeshData.")
        return lines

    lines.append("Role: baked navigation/pathfinding surface used by AI agents.")
    for label, names in (
        ("Name", ("m_Name", "name")),
        ("Position", ("m_Position", "position")),
        ("Rotation", ("m_Rotation", "rotation")),
        ("Source bounds", ("m_SourceBounds", "sourceBounds", "m_Bounds", "bounds")),
        ("NavMesh params", ("m_NavMeshParams", "navMeshParams", "m_Params", "params")),
    ):
        value = _nav_get(data, *names, default=None)
        if value is not None:
            lines.append(f"{label}: {_nav_value_text(value)}")

    counts = _nav_common_counts(data)
    if counts:
        lines.append("")
        lines.append("📊 Stored navigation data")
        lines.extend("  " + x for x in counts)

    settings = _nav_get(data, "m_NavMeshBuildSettings", "navMeshBuildSettings", "m_BuildSettings", "buildSettings", default=None)
    settings_lines = _nav_build_settings_lines(settings)
    if settings_lines:
        lines.append("")
        lines.append("🚶 Agent / build settings")
        lines.extend(settings_lines)

    tiles = _as_list(_nav_get(data, "m_NavMeshTiles", "navMeshTiles", "m_Tiles", "tiles", default=None))
    if tiles:
        lines.append("")
        lines.append("🧱 Tile summary")
        for i, tile in enumerate(tiles[:8]):
            raw = _nav_get(tile, "m_TileData", "tileData", "data", "bytes", default=None)
            raw_size = _nav_bytes_len(raw)
            x = _nav_get(tile, "m_X", "x", "tileX", default=None)
            y = _nav_get(tile, "m_Y", "y", "tileY", default=None)
            suffix = []
            if x is not None or y is not None:
                suffix.append(f"tile {x},{y}")
            if raw_size is not None:
                suffix.append(human_bytes(raw_size))
            lines.append(f"  {i}: " + ("  ".join(suffix) if suffix else "tile data present"))
        if len(tiles) > 8:
            lines.append(f"  ... {len(tiles) - 8} more tiles")

    fields = _short_field_list(data, {
        "m_Name", "m_Position", "m_Rotation", "m_SourceBounds", "m_Bounds", "m_NavMeshParams",
        "m_NavMeshBuildSettings", "m_BuildSettings", "m_NavMeshTiles", "m_Tiles",
        "m_Sources", "m_NavMeshSources", "m_OffMeshLinks", "m_Links",
    }, limit=36)
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 NavMeshData insight")
    lines.append("NavMeshData is the baked invisible walking map. AI agents query it to ask where they can stand and how to path from one point to another.")
    lines.append("It is usually a simplified triangulated travel surface, separate from the visible level mesh and separate from colliders.")
    lines.append("UBE's preview is symbolic unless UnityPy exposes enough triangulated data for a future real overlay.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def _describe_navmesh_settings(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None) -> list[str]:
    data = _read(record)
    lines: list[str] = [f"🧭 {friendly_type_name(record.type_name)} inspector"]
    if data is None:
        lines.append("Unable to read NavMesh settings data.")
        return lines

    if record.type_name == "NavMeshProjectSettings":
        lines.append("Role: project-wide navigation settings: agent types, area names/costs and build defaults.")
    else:
        lines.append("Role: scene/source navigation settings that reference or configure NavMeshData.")

    for label, names in (
        ("NavMesh data", ("m_NavMeshData", "navMeshData", "m_NavMeshDataRef", "navMeshDataRef")),
        ("Agent type ID", ("m_AgentTypeID", "agentTypeID")),
        ("Build settings", ("m_BuildSettings", "buildSettings", "m_NavMeshBuildSettings", "navMeshBuildSettings")),
        ("Settings", ("m_Settings", "settings")),
    ):
        value = _nav_get(data, *names, default=None)
        if value is None:
            continue
        if label == "NavMesh data":
            lines.append(f"{label}: {_pptr_text(value, bundle_index)}")
        else:
            lines.append(f"{label}: {_nav_value_text(value)}")

    counts = _nav_common_counts(data)
    if counts:
        lines.append("")
        lines.append("📊 Settings data")
        lines.extend("  " + x for x in counts)

    for field_name in ("m_BuildSettings", "buildSettings", "m_Settings", "settings", "m_AgentTypeSettings", "agentTypeSettings"):
        container = _nav_get(data, field_name, default=None)
        if container is None:
            continue
        items = _as_list(container)
        if items and len(items) > 1:
            lines.append("")
            lines.append(f"🚶 Agent/build settings list: {len(items):,}")
            for i, item in enumerate(items[:8]):
                lines.append(f"  Agent/settings {i}")
                item_lines = _nav_build_settings_lines(item, indent="    ")
                if item_lines:
                    lines.extend(item_lines[:10])
                else:
                    fields = _short_field_list(item, set(), limit=10)
                    lines.append("    fields: " + (", ".join(fields) if fields else "-"))
            if len(items) > 8:
                lines.append(f"  ... {len(items) - 8} more settings")
            break
        else:
            item_lines = _nav_build_settings_lines(container)
            if item_lines:
                lines.append("")
                lines.append("🚶 Agent/build settings")
                lines.extend(item_lines)
                break

    area_lines = _nav_area_lines(data)
    if area_lines:
        lines.append("")
        lines.append("🧭 Areas / costs")
        lines.extend(area_lines)

    fields = _short_field_list(data, {
        "m_NavMeshData", "m_NavMeshDataRef", "m_AgentTypeID", "m_BuildSettings",
        "m_NavMeshBuildSettings", "m_Settings", "m_AgentTypeSettings", "m_AreaNames", "m_AreaCosts"
    }, limit=36)
    if fields:
        lines.append("")
        lines.append("🧾 Other exposed fields")
        lines.append("  " + ", ".join(fields))

    lines.append("")
    lines.append("🧠 NavMesh settings insight")
    lines.append("NavMesh settings tell Unity how navigation was built and how agents interpret it: radius, height, slopes, steps, areas and costs.")
    lines.append("The NavMeshData is the baked walking surface; the settings describe the rules and agent sizes that produced or use that surface.")

    if asset_graph is not None:
        lines.extend(_relationship_lines(record, bundle_index, asset_graph))
    return lines


def describe_record(record: Any, bundle_index: Any | None = None, asset_graph: Any | None = None, include_relationships: bool = True) -> str:
    lines: list[str] = []
    lines.append(f"🏷 Name: {record.name}")
    lines.append(f"🧩 Asset type: {friendly_type_name(record.type_name)}")
    if friendly_type_name(record.type_name) != record.type_name:
        lines.append(f"   Unity type: {record.type_name}")
    lines.append(f"# Path ID: {record.path_id}")

    data = _read(record)
    if data is None:
        lines.append("\nUnable to read object data.")
        return "\n".join(lines)

    lines.append("")

    if record.type_name == "AudioMixerController":
        lines.extend(_describe_audio_mixer_controller(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "AudioMixerGroupController":
        lines.extend(_describe_audio_mixer_group(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "AudioMixerSnapshotController":
        lines.extend(_describe_audio_mixer_snapshot(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "AudioMixerEffectController":
        lines.extend(_describe_audio_mixer_effect(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "AudioSource":
        lines.extend(_describe_audio_source(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "AudioClip":
        lines.extend(_describe_audio(record))
        if include_relationships:
            lines.extend(_relationship_lines(record, bundle_index, asset_graph))
        return "\n".join(lines)

    if record.type_name == "Animation":
        lines.extend(_describe_animation_component(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "AnimationClip":
        lines.extend(_describe_animation_clip(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Animator":
        lines.extend(_describe_animator(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name in ("AnimatorController", "AnimatorOverrideController"):
        lines.extend(_describe_animator_controller(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Cubemap":
        lines.extend(_describe_cubemap(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Texture2DArray":
        lines.extend(_describe_texture_array(record))
        if include_relationships:
            lines.extend(_relationship_lines(record, bundle_index, asset_graph))
        return "\n".join(lines)

    if record.type_name == "Texture2D":
        lines.extend(_describe_texture(record, bundle_index, asset_graph))
        if include_relationships:
            lines.extend(_relationship_lines(record, bundle_index, asset_graph))
        return "\n".join(lines)

    if record.type_name == "Mesh":
        lines.extend(_describe_mesh(record, bundle_index, asset_graph))
        if include_relationships:
            lines.extend(_relationship_lines(record, bundle_index, asset_graph))
        return "\n".join(lines)

    if record.type_name == "Material":
        lines.extend(_describe_material(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Shader":
        lines.extend(_describe_shader(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "GameObject":
        lines.extend(_describe_game_object(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Transform":
        lines.extend(_describe_transform(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "MeshFilter":
        lines.extend(_describe_mesh_filter(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "MeshRenderer":
        lines.extend(_describe_mesh_renderer(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "SkinnedMeshRenderer":
        lines.extend(_describe_skinned_mesh_renderer(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Sprite":
        lines.extend(_describe_sprite(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "SpriteRenderer":
        lines.extend(_describe_sprite_renderer(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)


    if record.type_name == "BoxCollider":
        lines.extend(_describe_box_collider(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "SpriteMask":
        lines.extend(_describe_sprite_mask(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name in ("LineRenderer", "TrailRenderer"):
        lines.extend(_describe_line_or_trail_renderer(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Rigidbody":
        lines.extend(_describe_rigidbody(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name in ("SphereCollider", "CapsuleCollider", "MeshCollider"):
        lines.extend(_describe_physics_collider(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "PhysicMaterial":
        lines.extend(_describe_physic_material(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Avatar":
        lines.extend(_describe_avatar(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name in ("Font", "TMP_FontAsset"):
        lines.extend(_describe_font(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "TextAsset":
        lines.extend(_describe_text_asset(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "PlayableDirector":
        lines.extend(_describe_playable_director(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "NavMeshData":
        lines.extend(_describe_navmesh_data(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name in ("NavMeshSettings", "NavMeshProjectSettings"):
        lines.extend(_describe_navmesh_settings(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Camera":
        lines.extend(_describe_camera(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Light":
        lines.extend(_describe_light(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "ReflectionProbe":
        lines.extend(_describe_reflection_probe(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "LODGroup":
        lines.extend(_describe_lod_group(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "ParticleSystem":
        lines.extend(_describe_particle_system(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "ParticleSystemRenderer":
        lines.extend(_describe_particle_system_renderer(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "LightProbeGroup":
        lines.extend(_describe_light_probe_group(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "LightingSettings":
        lines.extend(_describe_lighting_settings(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "LightmapSettings":
        lines.extend(_describe_lightmap_settings(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "RectTransform":
        lines.extend(_describe_rect_transform(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "Canvas":
        lines.extend(_describe_canvas(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "CanvasGroup":
        lines.extend(_describe_canvas_group(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "CanvasRenderer":
        lines.extend(_describe_canvas_renderer(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    if record.type_name == "MonoBehaviour":
        lines.extend(_describe_mono_behaviour(record, bundle_index, asset_graph if include_relationships else None))
        return "\n".join(lines)

    # Generic useful fields for Unity objects.
    for attr in ("m_GameObject", "m_Mesh", "m_Materials", "m_Enabled", "m_IsActive"):
        value = _get(data, attr, default=None)
        if value is not None:
            lines.append(f"{attr}: {value}")

    if len(lines) <= 4:
        lines.append("No specialised inspector yet for this asset type.")

    return "\n".join(lines)
