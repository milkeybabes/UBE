from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from PIL import Image


def safe_filename(name: str, fallback: str = "texture") -> str:
    name = (name or "").strip() or fallback
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    return name[:180]


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if obj is None:
            return default
        if isinstance(obj, dict) and name in obj:
            return obj.get(name, default)
        if hasattr(obj, name):
            try:
                return getattr(obj, name)
            except Exception:
                pass
    return default


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _texture_format_code(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value)
    if text.lstrip("-").isdigit():
        return int(text)
    # Unity enum strings may look like "TextureFormat.RGB24".
    names = {
        "Alpha8": 1,
        "RGB24": 3,
        "RGBA32": 4,
        "ARGB32": 5,
        "BGRA32": 14,
        "R8": 63,
    }
    for name, code in names.items():
        if name.lower() in text.lower():
            return code
    return None


def export_texture_record(record, out_dir: str | Path) -> Path | None:
    """Export one UnityPy Texture2D record to PNG if possible."""
    root = Path(out_dir)
    out = root / "Textures"
    out.mkdir(parents=True, exist_ok=True)

    try:
        data = record.object.read()
        img = data.image
    except Exception:
        return None

    filename = safe_filename(getattr(data, "name", "") or record.name, f"texture_{record.path_id}") + ".png"
    dst = out / filename
    if dst.exists():
        dst = out / f"{dst.stem}_{record.path_id}.png"
    img.save(dst)
    return dst


# ---------------------------------------------------------
# Texture2DArray support
# ---------------------------------------------------------

def _candidate_array_images(data: Any) -> list[Any]:
    """Return decoded slice images if UnityPy exposes them directly.

    Some UnityPy Texture2DArray builds expose ``images`` as a property that can
    raise when the array data is streamed externally.  This helper must never
    let that property error escape; if decoded images are unavailable we simply
    return [] and let the raw-stream fallback try instead.
    """
    for attr in ("images", "image_list", "slice_images"):
        try:
            values = getattr(data, attr, None)
        except Exception:
            values = None
        if isinstance(values, (list, tuple)) and values:
            return list(values)

    for method_name in ("get_images", "get_image_list", "get_slices"):
        try:
            method = getattr(data, method_name, None)
        except Exception:
            method = None
        if callable(method):
            try:
                values = method()
                if isinstance(values, (list, tuple)) and values:
                    return list(values)
            except Exception:
                pass

    # Some decoders expose one composite image. Save as slice 000 if present.
    try:
        img = getattr(data, "image", None)
        if img is not None:
            return [img]
    except Exception:
        pass

    return []


def _stream_data(data: Any) -> Any:
    return _get(data, "m_StreamData", "stream_data", default=None)


def _read_bytes_from_attr_or_method(data: Any) -> bytes | None:
    for attr in ("image_data", "m_ImageData", "image_data_bytes", "data", "m_Data"):
        value = _get(data, attr, default=None)
        if isinstance(value, (bytes, bytearray)) and value:
            return bytes(value)
        if isinstance(value, list) and value and all(isinstance(x, int) for x in value[:32]):
            try:
                return bytes(value)
            except Exception:
                pass

    for method_name in ("get_image_data", "get_data", "read_data", "get_bytes"):
        method = getattr(data, method_name, None)
        if callable(method):
            try:
                value = method()
                if isinstance(value, (bytes, bytearray)) and value:
                    return bytes(value)
            except Exception:
                pass
    return None


def _reader_bytes_at(reader: Any, offset: int, size: int) -> bytes | None:
    """Read a byte range from UnityPy's in-memory resource readers."""
    if reader is None or size <= 0:
        return None

    # EndianBinaryReader_Memoryview exposes the whole resource as .bytes.
    try:
        data = getattr(reader, "bytes", None)
        if isinstance(data, (bytes, bytearray, memoryview)):
            chunk = bytes(data[offset:offset + size])
            return chunk if chunk else None
    except Exception:
        pass

    # Fallback to seek/read while preserving the old position where possible.
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
    p = stream_path.replace("\\", "/")
    if p.startswith("archive:/"):
        p = p[len("archive:/"):]
    p = p.split("/")[-1].lower()

    return c == p


def _read_bytes_from_stream(record: Any, data: Any) -> bytes | None:
    stream = _stream_data(data)
    if stream is None:
        return None

    # UnityPy StreamedResource variants sometimes expose a direct reader method.
    for method_name in ("get_data", "read", "read_data", "get_bytes"):
        method = getattr(stream, method_name, None)
        if callable(method):
            try:
                value = method()
                if isinstance(value, (bytes, bytearray)) and value:
                    return bytes(value)
            except Exception:
                pass

    offset = _int_or_none(_get(stream, "offset", "m_Offset", default=None)) or 0
    size = _int_or_none(_get(stream, "size", "m_Size", default=None))
    path = _get(stream, "path", "m_Path", default="") or ""
    if not path or not size:
        return None

    # First handle normal external .resS files on disk.
    candidates: list[Path] = []
    p = Path(path)
    if p.exists():
        candidates.append(p)

    bundle_path = None
    try:
        bundle_path = Path(getattr(record.object.assets_file, "path", ""))
    except Exception:
        bundle_path = None

    if bundle_path and str(bundle_path):
        bundle_dir = bundle_path.parent
        clean = path
        if clean.startswith("archive:/"):
            clean = clean[len("archive:/"):]
        clean = clean.replace("\\", "/")
        candidates.append(bundle_dir / clean)
        candidates.append(bundle_dir / Path(clean).name)

    for candidate in candidates:
        try:
            if candidate.exists():
                with candidate.open("rb") as f:
                    f.seek(offset)
                    return f.read(size)
        except Exception:
            continue

    # Unity asset bundles often keep archive:/...resS as an in-memory CAB reader
    # inside UnityPy, not as a real file beside the bundle.
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


def _texture_array_raw_bytes(record: Any, data: Any) -> bytes | None:
    raw = _read_bytes_from_attr_or_method(data)
    if raw:
        return raw
    return _read_bytes_from_stream(record, data)


def _raw_slices_to_images(raw: bytes, width: int, height: int, depth: int, fmt_code: int) -> list[Image.Image]:
    """Decode simple uncompressed Texture2DArray data into PIL images.

    This intentionally supports the useful easy cases first. Atlantis fish array
    is RGB24, 4x4, 192 slices, so it is handled here without needing full Unity
    shader emulation.
    """
    specs = {
        1: ("L", 1, None),       # Alpha8
        3: ("RGB", 3, None),     # RGB24
        4: ("RGBA", 4, None),    # RGBA32
        5: ("RGBA", 4, "ARGB"), # ARGB32 -> RGBA
        14: ("RGBA", 4, "BGRA"),# BGRA32 -> RGBA
        63: ("L", 1, None),      # R8
    }
    spec = specs.get(fmt_code)
    if not spec:
        return []

    mode, bpp, reorder = spec
    slice_size = width * height * bpp
    if slice_size <= 0:
        return []

    max_slices = min(depth, len(raw) // slice_size)
    images: list[Image.Image] = []

    for i in range(max_slices):
        chunk = raw[i * slice_size:(i + 1) * slice_size]
        if len(chunk) < slice_size:
            break

        if reorder == "ARGB":
            # A,R,G,B -> R,G,B,A
            converted = bytearray()
            for j in range(0, len(chunk), 4):
                a, r, g, b = chunk[j:j+4]
                converted.extend((r, g, b, a))
            chunk = bytes(converted)
        elif reorder == "BGRA":
            # B,G,R,A -> R,G,B,A
            converted = bytearray()
            for j in range(0, len(chunk), 4):
                b, g, r, a = chunk[j:j+4]
                converted.extend((r, g, b, a))
            chunk = bytes(converted)

        try:
            img = Image.frombytes(mode, (width, height), chunk)
            # Match normal texture preview/export orientation.
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            if mode == "L":
                img = img.convert("RGBA")
            images.append(img)
        except Exception:
            continue

    return images


def _texture_array_metadata(data: Any) -> tuple[int | None, int | None, int | None, int | None]:
    width = _int_or_none(_get(data, "m_Width", "width", default=None))
    height = _int_or_none(_get(data, "m_Height", "height", default=None))
    depth = _int_or_none(_get(data, "m_Depth", "depth", "m_Count", "count", "slice_count", "slices", default=None))
    fmt_code = _texture_format_code(_get(data, "m_TextureFormat", "texture_format", "m_Format", "format", default=None))
    return width, height, depth, fmt_code


def _make_contact_sheet(images: list[Image.Image], dst: Path, max_preview: int = 256) -> Path | None:
    if not images:
        return None
    try:
        count = len(images)
        cell_w = max(img.width for img in images)
        cell_h = max(img.height for img in images)
        scale = 1
        if cell_w < 16 and cell_h < 16:
            scale = max(1, min(16, 16 // max(cell_w, cell_h)))
        cell_w *= scale
        cell_h *= scale
        cols = min(16, max(1, int(count ** 0.5) + 1))
        rows = (count + cols - 1) // cols
        sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (32, 32, 32, 255))
        for i, img in enumerate(images):
            cell_img = img.convert("RGBA")
            if scale != 1:
                cell_img = cell_img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)
            x = (i % cols) * cell_w
            y = (i // cols) * cell_h
            sheet.paste(cell_img, (x, y))
        # Keep contact sheet sensible if a future array is huge.
        if sheet.width > max_preview * 8 or sheet.height > max_preview * 8:
            sheet.thumbnail((max_preview * 8, max_preview * 8), Image.Resampling.NEAREST)
        sheet.save(dst)
        return dst
    except Exception:
        return None



def _texture_array_images(record: Any, data: Any) -> tuple[list[Image.Image], int | None, int | None, int | None, int | None]:
    """Decode Texture2DArray images where possible.

    Shared helper for full slice export and one-slice mesh preview export.
    It first tries UnityPy's decoded slice access, then falls back to simple
    uncompressed raw data such as RGB24/RGBA32.
    """
    width, height, depth, fmt_code = _texture_array_metadata(data)
    images = _candidate_array_images(data)

    if not images and width and height and depth and fmt_code is not None:
        raw = _texture_array_raw_bytes(record, data)
        if raw:
            images = _raw_slices_to_images(raw, width, height, depth, fmt_code)

    return images, width, height, depth, fmt_code


def export_texture_array_slice_record(record, out_dir: str | Path, slice_index: int | float | str | None = 0) -> Path | None:
    """Export one Texture2DArray slice as a PNG for mesh preview / MTL use.

    This is intentionally conservative: if the array cannot be decoded, it
    returns None and the mesh preview falls back to material tint/shading.
    """
    root = Path(out_dir)
    out = root / "Textures"
    out.mkdir(parents=True, exist_ok=True)

    try:
        idx = int(float(slice_index if slice_index is not None else 0))
    except Exception:
        idx = 0
    idx = max(0, idx)

    try:
        data = record.object.read()
    except Exception:
        return None

    images, _width, _height, _depth, _fmt_code = _texture_array_images(record, data)
    if not images:
        return None

    if idx >= len(images):
        idx = len(images) - 1

    stem = safe_filename(getattr(data, "name", "") or record.name, f"texture_array_{record.path_id}")
    dst = out / f"{stem}_slice_{idx:03d}.png"
    if dst.exists():
        dst = out / f"{stem}_slice_{idx:03d}__path_{record.path_id}.png"

    try:
        images[idx].save(dst)
        return dst
    except Exception:
        return None

def export_texture_array_record(record, out_dir: str | Path) -> list[Path]:
    """Export Texture2DArray slices when possible.

    First tries UnityPy decoded images. If that is unavailable, handles common
    uncompressed raw formats directly, including RGB24 arrays such as
    atlantisFishArray.
    """
    root = Path(out_dir)
    name = safe_filename(record.name, f"texture_array_{record.path_id}")
    out = root / "TextureArrays" / name
    out.mkdir(parents=True, exist_ok=True)

    try:
        data = record.object.read()
    except Exception:
        return []

    images, width, height, depth, fmt_code = _texture_array_images(record, data)

    saved: list[Path] = []
    stem = safe_filename(getattr(data, "name", "") or record.name, f"texture_array_{record.path_id}")

    for i, img in enumerate(images):
        try:
            dst = out / f"{stem}_slice_{i:03d}.png"
            img.save(dst)
            saved.append(dst)
        except Exception:
            continue

    if saved:
        contact = _make_contact_sheet(images, out / f"{stem}_contact_sheet.png")
        if contact:
            saved.append(contact)
        meta = {
            "name": getattr(data, "name", "") or record.name,
            "path_id": getattr(record, "path_id", None),
            "width": width,
            "height": height,
            "depth": depth,
            "format_code": fmt_code,
            "slices_exported": len(images),
            "note": "Slices exported from UnityPy decoded images or simple uncompressed raw Texture2DArray data.",
        }
        try:
            meta_path = out / f"{stem}_slices.json"
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            saved.append(meta_path)
        except Exception:
            pass

    return saved

# ---------------------------------------------------------
# Sprite crop export
# ---------------------------------------------------------

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


def _resolve_record(bundle_index: Any | None, pptr_or_path_id: Any):
    if bundle_index is None:
        return None
    pid = pptr_or_path_id if isinstance(pptr_or_path_id, int) else _pptr_path_id(pptr_or_path_id)
    if pid is None:
        return None
    rec = getattr(bundle_index, "record_by_path_id", {}).get(pid)
    if rec is not None:
        return rec
    return getattr(bundle_index, "external_record_by_path_id", {}).get(pid)


def _rect_tuple(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    keys = (("x", "y", "width", "height"), ("x", "y", "w", "h"), ("m_X", "m_Y", "m_Width", "m_Height"))
    for names in keys:
        vals = []
        ok = True
        for name in names:
            v = _get(value, name, default=None)
            if v is None:
                ok = False
                break
            vals.append(v)
        if ok:
            try:
                return tuple(float(v) for v in vals)  # type: ignore[return-value]
            except Exception:
                pass
    if isinstance(value, (list, tuple)) and len(value) >= 4:
        try:
            return (float(value[0]), float(value[1]), float(value[2]), float(value[3]))
        except Exception:
            pass
    return None


def _sprite_render_data(data: Any) -> Any | None:
    return _get(data, "m_RD", "rd", "render_data", "m_RenderData", "renderData", default=None)


def _sprite_rect(data: Any) -> tuple[float, float, float, float] | None:
    for attr in ("m_Rect", "rect", "m_TextureRect", "textureRect"):
        r = _rect_tuple(_get(data, attr, default=None))
        if r is not None:
            return r
    rd = _sprite_render_data(data)
    if rd is not None:
        for attr in ("textureRect", "m_TextureRect", "m_Rect", "rect"):
            r = _rect_tuple(_get(rd, attr, default=None))
            if r is not None:
                return r
    return None


def _sprite_texture_pptr(data: Any) -> Any:
    rd = _sprite_render_data(data)
    if rd is not None:
        tex = _get(rd, "texture", "m_Texture", "m_Texture2D", "m_AtlasTexture", default=None)
        if tex is not None:
            return tex
        texs = _get(rd, "textures", "m_Textures", default=None)
        if isinstance(texs, (list, tuple)) and texs:
            return texs[0]
    return _get(data, "m_Texture", "texture", "m_AtlasTexture", default=None)


def _sprite_ppu(data: Any) -> float | None:
    for name in ("m_PixelsToUnits", "m_PixelsPerUnit", "pixelsToUnits", "pixelsPerUnit"):
        v = _get(data, name, default=None)
        if v is not None:
            try:
                return float(v)
            except Exception:
                pass
    return None


def _sprite_pivot(data: Any):
    return _get(data, "m_Pivot", "pivot", default=None)


def _vec2(value: Any) -> tuple[float, float] | None:
    if value is None:
        return None
    if hasattr(value, "x") and hasattr(value, "y"):
        try:
            return (float(value.x), float(value.y))
        except Exception:
            return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return (float(value[0]), float(value[1]))
        except Exception:
            return None
    return None


def _read_texture_image(texture_record: Any):
    if texture_record is None or getattr(texture_record, "object", None) is None:
        return None
    try:
        data = texture_record.object.read()
        return data.image
    except Exception:
        return None


def export_sprite_record(record, out_dir: str | Path, bundle_index: Any | None = None, name_override: str | None = None) -> Path | None:
    """Export one Unity Sprite as a cropped PNG from its backing Texture2D.

    Unity sprite rect Y is bottom-origin; PNG/Pillow crop is top-origin, so this
    converts y with: top = texture_height - (rect_y + rect_h).
    """
    root = Path(out_dir)
    out = root / "Sprites"
    out.mkdir(parents=True, exist_ok=True)

    try:
        data = record.object.read()
    except Exception:
        return None

    tex_rec = _resolve_record(bundle_index, _sprite_texture_pptr(data))
    img = _read_texture_image(tex_rec)
    if img is None:
        return None
    if img.mode not in ("RGBA", "RGB"):
        try:
            img = img.convert("RGBA")
        except Exception:
            pass

    rect = _sprite_rect(data)
    if rect is None:
        crop = img
        rect_info = None
    else:
        x, y, w, h = rect
        left = int(round(x))
        top = int(round(img.height - (y + h)))
        right = int(round(x + w))
        bottom = int(round(img.height - y))
        left = max(0, min(img.width, left))
        right = max(0, min(img.width, right))
        top = max(0, min(img.height, top))
        bottom = max(0, min(img.height, bottom))
        if right <= left or bottom <= top:
            crop = img
            rect_info = None
        else:
            crop = img.crop((left, top, right, bottom))
            rect_info = {"x": x, "y": y, "w": w, "h": h, "crop_left": left, "crop_top": top, "crop_right": right, "crop_bottom": bottom}

    base = safe_filename(name_override or getattr(record, "name", "") or f"sprite_{getattr(record, 'path_id', 'unknown')}", "sprite")
    dst = out / f"{base}.png"
    if dst.exists():
        dst = out / f"{dst.stem}_{getattr(record, 'path_id', 'unknown')}.png"
    crop.save(dst)

    meta = {
        "sprite": {"name": getattr(record, "name", ""), "path_id": getattr(record, "path_id", None)},
        "texture": {"name": getattr(tex_rec, "name", "") if tex_rec is not None else "", "path_id": getattr(tex_rec, "path_id", None) if tex_rec is not None else None, "size": [img.width, img.height]},
        "rect": rect_info,
        "pivot": list(_vec2(_sprite_pivot(data)) or ()) or None,
        "pixels_per_unit": _sprite_ppu(data),
        "output": str(dst),
    }
    try:
        (out / f"{dst.stem}__sprite.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    except Exception:
        pass
    return dst


def export_sprite_renderer_record(record, out_dir: str | Path, bundle_index: Any | None = None) -> Path | None:
    """Export the Sprite used by a SpriteRenderer as a cropped PNG."""
    if record is None or getattr(record, "object", None) is None:
        return None
    try:
        data = record.object.read()
    except Exception:
        return None
    sprite_pptr = _get(data, "m_Sprite", "sprite", default=None)
    sprite_rec = _resolve_record(bundle_index, sprite_pptr)
    if sprite_rec is None or getattr(sprite_rec, "object", None) is None:
        return None
    name = safe_filename(f"{getattr(record, 'name', 'SpriteRenderer')}__{getattr(sprite_rec, 'name', 'Sprite')}")
    return export_sprite_record(sprite_rec, out_dir, bundle_index, name_override=name)

