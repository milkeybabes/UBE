from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import struct


def _read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.find(b"\0", pos)
    if end < 0:
        return "", pos
    return data[pos:end].decode("utf-8", "replace"), end + 1


def _read_cstring_from(data: bytes, pos: int, max_len: int = 256) -> str:
    if pos < 0 or pos >= len(data):
        return ""
    end = pos
    limit = min(len(data), pos + max_len)
    while end < limit and data[end] != 0:
        end += 1
    if end == pos:
        return ""
    return data[pos:end].decode("utf-8", "replace")


def _looks_like_unity_version(text: str) -> bool:
    """Detect Unity version strings such as 2021.3.8f1 or 6000.3.9f1."""
    s = str(text or "").strip()
    if not s or len(s) > 64:
        return False
    if s == "5.x.x":
        return True
    return bool(re.match(r"^(20\d{2}|6000)\.\d+\.\d+[abfp]\d+.*$", s))


@dataclass(slots=True)
class UnityFSHeader:
    """Header/source summary used by UBE.

    The historical class name remains UnityFSHeader so existing UI/export code
    does not need to change, but v1.8p also fills it for Unity SerializedFile
    sources such as globalgamemanagers, sharedassets*.assets and resources.assets.
    """

    path: str
    signature: str = ""
    format_version: int | None = None
    unity_version: str = ""
    unity_revision: str = ""
    file_size: int = 0
    note: str = ""

    # v1.8p: Unity SerializedFile / .assets-style header fields.
    source_kind: str = "unknown"  # unityfs_bundle, unity_serialized_file, zip, audio, unknown
    serialized_file_version: int | None = None
    metadata_size: int | None = None
    declared_file_size: int | None = None
    data_offset: int | None = None
    header_layout: str = ""
    sidecar_hint: str = ""


def _read_serialized_file_header(data: bytes, actual_size: int) -> dict | None:
    """Detect a Unity SerializedFile header.

    These are not UnityFS bundles. They are the .assets/globalgamemanagers style
    serialized object database used by many desktop/Steam Unity games.
    """
    if len(data) < 64:
        return None

    try:
        old_meta, old_file_size, version, old_data_offset = struct.unpack(">IIII", data[:16])
    except Exception:
        return None

    if not (6 <= version <= 99):
        return None

    # Unity 2020+/2021+/2022+ SerializedFile v22+ uses 64-bit values after the
    # first 16 bytes and the Unity version string commonly begins at 0x30.
    if version >= 22 and len(data) >= 64:
        try:
            meta64 = struct.unpack(">Q", data[16:24])[0]
            file64 = struct.unpack(">Q", data[24:32])[0]
            data64 = struct.unpack(">Q", data[32:40])[0]
            unity_version = _read_cstring_from(data, 48, 128)
            if _looks_like_unity_version(unity_version):
                note = "Unity SerializedFile (.assets/globalgamemanagers style), not a UnityFS AssetBundle"
                if file64 and file64 > actual_size:
                    note += "; visible file is smaller than declared size, so this may be a split/partial file"
                return {
                    "version": version,
                    "unity_version": unity_version,
                    "metadata_size": int(meta64),
                    "declared_file_size": int(file64),
                    "data_offset": int(data64),
                    "layout": "SerializedFile v22+ 64-bit header",
                    "note": note,
                }
        except Exception:
            pass

    # Older/classic SerializedFile header layout.
    unity_version = _read_cstring_from(data, 20, 128)
    if _looks_like_unity_version(unity_version):
        note = "Unity SerializedFile (.assets/globalgamemanagers style), not a UnityFS AssetBundle"
        if old_file_size and old_file_size > actual_size:
            note += "; visible file is smaller than declared size, so this may be a split/partial file"
        return {
            "version": version,
            "unity_version": unity_version,
            "metadata_size": int(old_meta),
            "declared_file_size": int(old_file_size),
            "data_offset": int(old_data_offset),
            "layout": "SerializedFile classic 32-bit header",
            "note": note,
        }

    # Fallback: version string very near the start with plausible binary header.
    for off in range(16, min(128, len(data))):
        s = _read_cstring_from(data, off, 80)
        if _looks_like_unity_version(s):
            return {
                "version": version,
                "unity_version": s,
                "metadata_size": int(old_meta),
                "declared_file_size": int(old_file_size),
                "data_offset": int(old_data_offset),
                "layout": f"SerializedFile probable header, version string at 0x{off:X}",
                "note": "Unity SerializedFile probable header, not a UnityFS AssetBundle",
            }

    return None


def read_unityfs_header(path: str | Path) -> UnityFSHeader:
    """Read a Unity source header.

    Despite the function name, this now recognises both:
      - UnityFS/UnityWeb/UnityRaw AssetBundle-style containers
      - Unity SerializedFile .assets/globalgamemanagers/sharedassets/resources files
    """
    p = Path(path)
    data = p.read_bytes()[:4096]
    h = UnityFSHeader(path=str(p), file_size=p.stat().st_size)

    if data.startswith(b"UnityFS") or data.startswith(b"UnityWeb") or data.startswith(b"UnityRaw"):
        sig, pos = _read_cstring(data, 0)
        h.signature = sig
        h.source_kind = "unityfs_bundle"
        if pos + 4 <= len(data):
            h.format_version = int.from_bytes(data[pos:pos + 4], "big")
            pos += 4

        h.unity_version, pos = _read_cstring(data, pos)
        h.unity_revision, pos = _read_cstring(data, pos)
        return h

    serialized = _read_serialized_file_header(data, h.file_size)
    if serialized:
        h.signature = "UnitySerializedFile"
        h.source_kind = "unity_serialized_file"
        h.serialized_file_version = serialized.get("version")
        h.unity_version = str(serialized.get("unity_version") or "")
        h.unity_revision = h.unity_version
        h.metadata_size = serialized.get("metadata_size")
        h.declared_file_size = serialized.get("declared_file_size")
        h.data_offset = serialized.get("data_offset")
        h.header_layout = str(serialized.get("layout") or "")
        h.note = str(serialized.get("note") or "")
        h.sidecar_hint = ".resS / .resource sidecar files may be needed for large textures/audio/streamed data"
        return h

    if data.startswith(b"PK"):
        h.signature = "ZIP/PK"
        h.source_kind = "zip"
        h.note = "ZIP-style archive, not a UnityFS bundle or SerializedFile"
        return h

    if data.startswith(b"FSB5"):
        h.signature = "FSB5"
        h.source_kind = "audio"
        h.note = "FMOD FSB5 audio bank/resource, not a Unity object database"
        return h

    sig, _ = _read_cstring(data, 0)
    h.signature = sig
    h.source_kind = "unknown"
    h.note = "Not a recognised UnityFS/UnityWeb/UnityRaw or Unity SerializedFile header"
    return h
