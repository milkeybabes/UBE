from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote


@dataclass(slots=True)
class AudioExportResult:
    ok: bool
    paths: list[Path]
    message: str = ""
    playable_path: Path | None = None
    raw_path: Path | None = None
    metadata_path: Path | None = None
    container: str = ""
    resource_path: Path | None = None


@dataclass(slots=True)
class AudioReadResult:
    data: bytes | None
    message: str = ""
    resource_path: Path | None = None
    source: str = ""
    offset: int = 0
    size: int = 0
    resolver: str = ""


def safe_filename(name: str, fallback: str = "audio") -> str:
    name = (name or "").strip() or fallback
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    return name[:180]


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if obj is None:
            return default
        if hasattr(obj, name):
            try:
                return getattr(obj, name)
            except Exception:
                pass
    return default


def _source_basename(source: str) -> str:
    """Reduce Unity archive/resource references to a normal filename."""
    text = unquote(str(source or "")).strip().replace("\\", "/")
    text = text.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    if not text:
        return ""
    return text.rsplit("/", 1)[-1]


def _resource_aliases(source: str) -> set[str]:
    """Names Unity commonly uses for the same streamed resource store."""
    name = _source_basename(source).lower()
    if not name:
        return set()

    aliases = {name}
    if name.endswith(".assets.ress"):
        base = name[: -len(".assets.ress")]
        aliases.update({f"{base}.resource", f"{base}.ress"})
    elif name.endswith(".resource"):
        base = name[: -len(".resource")]
        aliases.update({f"{base}.ress", f"{base}.assets.ress"})
    elif name.endswith(".ress"):
        base = name[: -len(".ress")]
        aliases.update({f"{base}.resource", f"{base}.assets.ress"})
    return aliases


def _discover_record_resources(record: Any) -> tuple[Path, ...]:
    """Use loader-discovered resources, with a direct folder scan fallback."""
    found: list[Path] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        try:
            path = Path(value).expanduser().resolve()
        except Exception:
            return
        key = str(path).lower()
        if key in seen or not path.is_file():
            return
        lower_name = path.name.lower()
        if not (lower_name.endswith(".resource") or lower_name.endswith(".ress")):
            return
        seen.add(key)
        found.append(path)

    for path in getattr(record, "companion_resource_paths", ()) or ():
        add(path)

    source_file = getattr(record, "source_file", None)
    if source_file:
        try:
            folder = Path(source_file).expanduser().resolve().parent
            for child in folder.iterdir():
                add(child)
        except Exception:
            pass

    found.sort(key=lambda value: value.name.lower())
    return tuple(found)


def _read_file_range(path: Path, offset: int, size: int) -> tuple[bytes | None, str]:
    try:
        file_size = path.stat().st_size
    except Exception as exc:
        return None, f"could not inspect {path.name}: {exc}"

    end = offset + size
    if offset < 0 or size <= 0:
        return None, f"invalid external byte range: offset {offset:,}, size {size:,}"
    if end > file_size:
        return None, (
            f"requested byte range {offset:,}..{end:,} is outside {path.name} "
            f"({file_size:,} bytes)"
        )

    try:
        with path.open("rb") as stream:
            stream.seek(offset)
            data = stream.read(size)
    except Exception as exc:
        return None, f"could not read {path.name}: {exc}"

    if len(data) != size:
        return None, f"short read from {path.name}: expected {size:,} bytes, got {len(data):,}"
    return data, ""


def _looks_like_audio_container(data: bytes) -> bool:
    magic = data[:16]
    return bool(
        magic.startswith((b"FSB5", b"FSB4", b"OggS", b"RIFF"))
        or (len(magic) >= 8 and magic[4:8] == b"ftyp")
    )


def _read_audio_bytes(record: Any, data: Any) -> AudioReadResult:
    direct = _get(data, "m_AudioData", "audio_data", default=None)
    if isinstance(direct, (bytes, bytearray)) and direct:
        return AudioReadResult(bytes(direct), resolver="embedded")
    if isinstance(direct, list) and direct:
        try:
            return AudioReadResult(bytes(direct), resolver="embedded")
        except Exception:
            pass

    resource = _get(data, "m_Resource", "resource", default=None)
    if resource is None:
        return AudioReadResult(
            None,
            "AudioClip has no embedded audio bytes and no external resource reference.",
        )

    source = str(_get(resource, "m_Source", "source", default="") or "")
    try:
        offset = int(_get(resource, "m_Offset", "offset", default=0) or 0)
    except Exception:
        offset = 0
    try:
        size = int(_get(resource, "m_Size", "size", default=0) or 0)
    except Exception:
        size = 0

    if not source or size <= 0:
        return AudioReadResult(
            None,
            "AudioClip has no embedded bytes and its external resource reference is incomplete "
            f"(source: {_source_basename(source) or '-'}, size: {size:,}).",
            source=source,
            offset=offset,
            size=size,
        )

    unitypy_error = ""
    try:
        from UnityPy.helpers.ResourceReader import get_resource_data

        assets_file = getattr(record.object, "assets_file", None)
        resolved = get_resource_data(source, assets_file, offset, size)
        if resolved:
            return AudioReadResult(
                bytes(resolved),
                resource_path=None,
                source=source,
                offset=offset,
                size=size,
                resolver="UnityPy",
            )
    except Exception as exc:
        unitypy_error = str(exc).strip()

    # v2.0u fallback: Unity player-data extractions often leave raw streamed
    # stores beside data.unity3d.  UnityPy.load(main_file) may not register those
    # files, so resolve the source name directly against loader-discovered
    # siblings and read the referenced offset/size range ourselves.
    resources = _discover_record_resources(record)
    aliases = _resource_aliases(source)
    exact = [path for path in resources if path.name.lower() in aliases]

    range_errors: list[str] = []
    for path in exact:
        raw, error = _read_file_range(path, offset, size)
        if raw is not None:
            return AudioReadResult(
                raw,
                resource_path=path,
                source=source,
                offset=offset,
                size=size,
                resolver="sibling resource",
            )
        if error:
            range_errors.append(error)

    # Last-resort name-mismatch recovery.  Only accept an unmatched sibling
    # when the requested range begins with a recognisable audio container.
    for path in resources:
        if path in exact:
            continue
        try:
            file_size = path.stat().st_size
            if offset < 0 or size <= 0 or offset + size > file_size:
                continue
            with path.open("rb") as stream:
                stream.seek(offset)
                probe = stream.read(min(16, size))
        except Exception:
            continue
        if not _looks_like_audio_container(probe):
            continue
        raw, error = _read_file_range(path, offset, size)
        if raw is not None:
            return AudioReadResult(
                raw,
                resource_path=path,
                source=source,
                offset=offset,
                size=size,
                resolver="sibling resource (magic match)",
            )
        if error:
            range_errors.append(error)

    source_name = _source_basename(source) or source
    source_file = getattr(record, "source_file", None)
    folder_text = "the opened Unity file's folder"
    if source_file:
        try:
            folder_text = str(Path(source_file).resolve().parent)
        except Exception:
            pass

    if exact and range_errors:
        message = (
            f"External audio resource was found, but the referenced data range could not be read.\n"
            f"Resource: {source_name}\nOffset: {offset:,}\nSize: {size:,}\n"
            f"Reason: {range_errors[0]}"
        )
    else:
        message = (
            f"Missing external audio resource: {source_name}\n"
            f"This AudioClip stores only metadata in the main Unity file. Its audio bytes are in a "
            f"separate .resource/.resS file. Keep that file beside the main Unity file and reopen it.\n"
            f"Expected folder: {folder_text}\nOffset: {offset:,}\nSize: {size:,}"
        )
        if resources:
            message += "\nSibling resource files found: " + ", ".join(path.name for path in resources[:8])
            if len(resources) > 8:
                message += f" (+{len(resources) - 8} more)"
        else:
            message += "\nNo sibling .resource or .resS files were found."

    if unitypy_error:
        compact = " ".join(unitypy_error.split())
        if len(compact) > 300:
            compact = compact[:297] + "..."
        message += f"\nUnity resource resolver: {compact}"

    return AudioReadResult(
        None,
        message,
        source=source,
        offset=offset,
        size=size,
    )


def _container_from_magic(data: bytes) -> tuple[str, str, bool]:
    magic = data[:16]
    if magic.startswith(b"OggS"):
        return "OGG Vorbis", ".ogg", True
    if magic.startswith(b"RIFF"):
        return "RIFF/WAV", ".wav", True
    if len(magic) >= 8 and magic[4:8] == b"ftyp":
        return "MPEG-4 Audio", ".m4a", True
    if magic.startswith(b"FSB5"):
        return "FMOD FSB5", ".fsb", False
    if magic.startswith(b"FSB4"):
        return "FMOD FSB4", ".fsb", False
    return magic[:4].hex().upper() if magic else "Unknown", ".audio", False


def audio_metadata(
    record: Any,
    data: Any,
    raw_bytes: bytes | None = None,
    read_result: AudioReadResult | None = None,
) -> dict[str, Any]:
    resource = _get(data, "m_Resource", "resource", default=None)
    container, ext, playable = _container_from_magic(raw_bytes or b"") if raw_bytes else ("Unknown", ".audio", False)
    return {
        "name": _get(data, "m_Name", "name", default=record.name) or record.name,
        "path_id": getattr(record, "path_id", None),
        "type": getattr(record, "type_name", "AudioClip"),
        "length_seconds": _get(data, "m_Length", "length", default=None),
        "channels": _get(data, "m_Channels", "channels", default=None),
        "frequency": _get(data, "m_Frequency", "frequency", default=None),
        "bits_per_sample": _get(data, "m_BitsPerSample", "bits_per_sample", default=None),
        "load_type": _get(data, "m_LoadType", "load_type", default=None),
        "compression_format": str(_get(data, "m_CompressionFormat", "compression_format", default="")),
        "raw_size": len(raw_bytes) if raw_bytes else 0,
        "container": container,
        "playable_in_qt": playable,
        "resource": {
            "source": _get(resource, "m_Source", "source", default="") if resource is not None else "",
            "offset": _get(resource, "m_Offset", "offset", default=None) if resource is not None else None,
            "size": _get(resource, "m_Size", "size", default=None) if resource is not None else None,
            "resolved_path": str(read_result.resource_path) if read_result and read_result.resource_path else "",
            "resolver": read_result.resolver if read_result else "",
        },
    }


def export_audio_record(record: Any, out_dir: str | Path) -> AudioExportResult:
    root = Path(out_dir)
    out = root / "Audio"
    out.mkdir(parents=True, exist_ok=True)

    try:
        data = record.object.read()
    except Exception as e:
        return AudioExportResult(False, [], f"AudioClip read failed: {e}")

    read_result = _read_audio_bytes(record, data)
    raw = read_result.data
    if not raw:
        return AudioExportResult(False, [], read_result.message)

    container, ext, playable = _container_from_magic(raw)
    base = safe_filename(_get(data, "m_Name", "name", default=record.name) or record.name, f"audio_{record.path_id}")
    audio_path = out / f"{base}{ext}"
    if audio_path.exists():
        audio_path = out / f"{base}_{record.path_id}{ext}"
    audio_path.write_bytes(raw)

    meta = audio_metadata(record, data, raw, read_result)
    meta_path = out / f"{audio_path.stem}__metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    msg = f"Exported {container} audio"
    if read_result.resource_path is not None:
        msg += f" from {read_result.resource_path.name}"
    if not playable:
        msg += " (raw container; not directly playable by Qt)"
    return AudioExportResult(
        ok=True,
        paths=[audio_path, meta_path],
        message=msg,
        playable_path=audio_path if playable else None,
        raw_path=audio_path,
        metadata_path=meta_path,
        container=container,
        resource_path=read_result.resource_path,
    )


def export_audio_wav_record(
    record: Any,
    out_dir: str | Path,
    *,
    decoder_path: str | Path | None = None,
    subsong: int = 1,
) -> AudioExportResult:
    """Export one AudioClip as a standard decoded WAV.

    The original Unity/FSB container is read exactly as native export would read
    it, but is written only to a temporary file for vgmstream.  The user's
    output folder receives the WAV plus metadata, not a duplicate raw FSB.
    """
    root = Path(out_dir)
    out = root / "Audio"
    out.mkdir(parents=True, exist_ok=True)

    try:
        data = record.object.read()
    except Exception as exc:
        return AudioExportResult(False, [], f"AudioClip read failed: {exc}")

    read_result = _read_audio_bytes(record, data)
    raw = read_result.data
    if not raw:
        return AudioExportResult(False, [], read_result.message)

    source_container, source_ext, _playable = _container_from_magic(raw)
    base = safe_filename(
        _get(data, "m_Name", "name", default=record.name) or record.name,
        f"audio_{record.path_id}",
    )
    subsong = max(1, int(subsong or 1))

    # A multi-subsong FSB bank needs an explicit suffix so exporting a second
    # selection cannot silently overwrite sample 1.
    suffix = f"_sample{subsong:02d}" if subsong > 1 else ""
    wav_path = out / f"{base}{suffix}.wav"
    if wav_path.exists():
        wav_path = out / f"{base}{suffix}_{record.path_id}.wav"

    # Native RIFF/WAVE clips already meet the requested output format.
    if raw.startswith(b"RIFF") and raw[8:12] == b"WAVE":
        try:
            wav_path.write_bytes(raw)
        except Exception as exc:
            return AudioExportResult(False, [], f"Could not write WAV: {exc}")
        decoder_used = "not required (source was already WAV)"
    else:
        from .audio_decoder import decode_with_vgmstream

        try:
            with tempfile.TemporaryDirectory(prefix="ube_audio_wav_export_") as temp_dir:
                temp_root = Path(temp_dir)
                source_path = temp_root / f"source{source_ext}"
                source_path.write_bytes(raw)
                temp_wav = temp_root / "decoded.wav"
                decoded = decode_with_vgmstream(
                    source_path,
                    temp_wav,
                    subsong=subsong,
                    decoder_path=decoder_path,
                    timeout=300.0,
                )
                if not decoded.ok or decoded.output_path is None:
                    return AudioExportResult(
                        False,
                        [],
                        f"WAV conversion failed: {decoded.message}",
                        container=source_container,
                        resource_path=read_result.resource_path,
                    )
                wav_path.write_bytes(decoded.output_path.read_bytes())
                decoder_used = str(decoded.decoder_path or decoder_path or "vgmstream-cli")
        except Exception as exc:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass
            return AudioExportResult(
                False,
                [],
                f"WAV conversion failed: {exc}",
                container=source_container,
                resource_path=read_result.resource_path,
            )

    meta = audio_metadata(record, data, raw, read_result)
    meta["wav_export"] = {
        "decoded_from": source_container,
        "subsong": subsong,
        "decoder": decoder_used,
        "output": wav_path.name,
    }
    meta_path = out / f"{wav_path.stem}__metadata.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    message = f"Exported decoded WAV from {source_container}"
    if subsong > 1:
        message += f" sample {subsong}"
    if read_result.resource_path is not None:
        message += f" via {read_result.resource_path.name}"
    return AudioExportResult(
        True,
        [wav_path, meta_path],
        message=message,
        playable_path=wav_path,
        raw_path=None,
        metadata_path=meta_path,
        container="RIFF/WAV (decoded)",
        resource_path=read_result.resource_path,
    )
