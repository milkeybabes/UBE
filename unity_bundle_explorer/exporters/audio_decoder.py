from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


FREQUENCY_VALUES = {
    1: 8000,
    2: 11000,
    3: 11025,
    4: 16000,
    5: 22050,
    6: 24000,
    7: 32000,
    8: 44100,
    9: 48000,
}

FSB5_FORMAT_NAMES = {
    0: "None",
    1: "PCM8",
    2: "PCM16",
    3: "PCM24",
    4: "PCM32",
    5: "PCM Float",
    6: "GC ADPCM",
    7: "IMA ADPCM",
    8: "VAG",
    9: "HEVAG",
    10: "XMA",
    11: "MPEG",
    12: "CELT",
    13: "ATRAC9",
    14: "XWMA",
    15: "Vorbis",
}


@dataclass(slots=True)
class FSB5SampleInfo:
    index: int
    name: str
    frequency: int | None
    channels: int
    sample_count: int
    data_offset: int

    @property
    def duration_seconds(self) -> float | None:
        if not self.frequency:
            return None
        return self.sample_count / self.frequency


@dataclass(slots=True)
class FSB5Info:
    version: int
    sample_count: int
    sample_headers_size: int
    name_table_size: int
    data_size: int
    mode: int
    format_name: str
    header_size: int
    samples: list[FSB5SampleInfo]


@dataclass(slots=True)
class AudioDecodeResult:
    ok: bool
    output_path: Path | None = None
    decoder_path: Path | None = None
    message: str = ""
    command: tuple[str, ...] = ()


def _bits(value: int, start: int, length: int) -> int:
    return (value >> start) & ((1 << length) - 1)


def inspect_fsb5_bytes(data: bytes) -> FSB5Info:
    """Read enough FSB5 structure for UBE's audio panel and subsong picker.

    This intentionally does not decode audio.  It follows the real 60-byte FSB5
    v1 header (six uint32 fields after ``FSB5``), avoiding the four-byte
    alignment bug present in the earlier standalone player prototype.
    """
    if len(data) < 60 or data[:4] != b"FSB5":
        raise ValueError("Not an FSB5 file")

    header = struct.unpack_from("<4s6I8s16s8s", data, 0)
    version = int(header[1])
    num_samples = int(header[2])
    sample_headers_size = int(header[3])
    name_table_size = int(header[4])
    if num_samples < 0 or num_samples > 1_000_000:
        raise ValueError(f"Unreasonable FSB5 sample count: {num_samples}")
    if sample_headers_size < 0 or name_table_size < 0:
        raise ValueError("Invalid negative FSB5 structural size")
    data_size = int(header[5])
    mode = int(header[6])
    header_size = 60

    # FSB5 version 0 has one additional uint32 after the common header.
    if version == 0:
        if len(data) < 64:
            raise ValueError("Truncated FSB5 v0 header")
        header_size = 64

    sample_headers_end = header_size + sample_headers_size
    name_table_start = sample_headers_end
    name_table_end = name_table_start + name_table_size
    if sample_headers_end > len(data):
        raise ValueError("FSB5 sample-header area extends beyond the file")

    parsed: list[FSB5SampleInfo] = []
    pos = header_size

    for index in range(num_samples):
        if pos + 8 > sample_headers_end:
            raise ValueError(f"FSB5 sample {index} header is truncated")

        raw = struct.unpack_from("<Q", data, pos)[0]
        pos += 8
        has_next_chunk = _bits(raw, 0, 1)
        frequency_index = _bits(raw, 1, 4)
        channels = _bits(raw, 5, 1) + 1
        data_offset = _bits(raw, 6, 28) * 16
        pcm_samples = _bits(raw, 34, 30)
        frequency = FREQUENCY_VALUES.get(frequency_index)

        while has_next_chunk:
            if pos + 4 > sample_headers_end:
                raise ValueError(f"FSB5 sample {index} metadata header is truncated")
            chunk_header = struct.unpack_from("<I", data, pos)[0]
            pos += 4
            has_next_chunk = _bits(chunk_header, 0, 1)
            chunk_size = _bits(chunk_header, 1, 24)
            chunk_type = _bits(chunk_header, 25, 7)
            if pos + chunk_size > sample_headers_end:
                raise ValueError(f"FSB5 sample {index} metadata payload is truncated")

            if chunk_type == 1 and chunk_size >= 1:  # CHANNELS
                channels = data[pos]
            elif chunk_type == 2 and chunk_size >= 4:  # FREQUENCY
                frequency = struct.unpack_from("<I", data, pos)[0]
            pos += chunk_size

        parsed.append(
            FSB5SampleInfo(
                index=index,
                name=f"Sample {index + 1}",
                frequency=frequency,
                channels=channels,
                sample_count=pcm_samples,
                data_offset=data_offset,
            )
        )

    # Names are stored as uint32 offsets relative to the start of the name table.
    if name_table_size and name_table_end <= len(data) and num_samples > 0:
        offsets_size = num_samples * 4
        if offsets_size <= name_table_size:
            offsets = struct.unpack_from(f"<{num_samples}I", data, name_table_start)
            for index, offset in enumerate(offsets):
                absolute = name_table_start + int(offset)
                if not (name_table_start <= absolute < name_table_end):
                    continue
                nul = data.find(b"\x00", absolute, name_table_end)
                if nul < 0:
                    nul = name_table_end
                raw_name = data[absolute:nul]
                if raw_name:
                    parsed[index].name = raw_name.decode("utf-8", errors="replace")

    return FSB5Info(
        version=version,
        sample_count=num_samples,
        sample_headers_size=sample_headers_size,
        name_table_size=name_table_size,
        data_size=data_size,
        mode=mode,
        format_name=FSB5_FORMAT_NAMES.get(mode, f"Format {mode}"),
        header_size=header_size,
        samples=parsed,
    )


def inspect_fsb5_file(path: str | Path) -> FSB5Info:
    """Inspect only the FSB5 structural area, not the usually much larger audio payload."""
    source = Path(path)
    file_size = source.stat().st_size
    with source.open("rb") as stream:
        common = stream.read(60)
        if len(common) < 60 or common[:4] != b"FSB5":
            raise ValueError("Not an FSB5 file")
        header = struct.unpack_from("<4s6I8s16s8s", common, 0)
        version = int(header[1])
        header_size = 64 if version == 0 else 60
        structural_size = header_size + int(header[3]) + int(header[4])
        if structural_size < header_size or structural_size > file_size:
            raise ValueError("FSB5 structural area extends beyond the file")
        if structural_size > 256 * 1024 * 1024:
            raise ValueError("FSB5 structural area is unreasonably large")
        stream.seek(0)
        structural_data = stream.read(structural_size)
    if len(structural_data) < structural_size:
        raise ValueError("FSB5 structural area is truncated")
    return inspect_fsb5_bytes(structural_data)


def _candidate_roots(extra_roots: Iterable[str | Path] | None = None) -> list[Path]:
    roots: list[Path] = []

    def add(value) -> None:
        if not value:
            return
        try:
            path = Path(value).expanduser().resolve()
        except Exception:
            return
        if path not in roots:
            roots.append(path)

    if extra_roots:
        for value in extra_roots:
            add(value)

    try:
        add(Path(sys.argv[0]).resolve().parent)
    except Exception:
        pass
    try:
        add(Path(sys.executable).resolve().parent)
    except Exception:
        pass
    try:
        add(Path(__file__).resolve().parents[2])
    except Exception:
        pass
    add(Path.cwd())
    add(getattr(sys, "_MEIPASS", None))
    return roots


def _expand_preferred(preferred: str | Path | None) -> list[Path]:
    if not preferred:
        return []
    try:
        path = Path(preferred).expanduser()
    except Exception:
        return []
    if path.is_dir():
        return [path / "vgmstream-cli.exe", path / "vgmstream-cli"]
    return [path]


def find_vgmstream_cli(
    preferred: str | Path | None = None,
    extra_roots: Iterable[str | Path] | None = None,
) -> Path | None:
    """Locate vgmstream without making it a mandatory UBE dependency."""
    candidates: list[Path] = []
    candidates.extend(_expand_preferred(preferred))
    candidates.extend(_expand_preferred(os.environ.get("UBE_VGMSTREAM")))

    for command_name in ("vgmstream-cli.exe", "vgmstream-cli"):
        found = shutil.which(command_name)
        if found:
            candidates.append(Path(found))

    relative_folders = (
        Path("."),
        Path("vgmstream"),
        Path("tools") / "vgmstream",
        Path("Tools") / "vgmstream",
        Path("ExternalTools") / "vgmstream",
        Path("bin"),
    )
    executable_names = ("vgmstream-cli.exe", "vgmstream-cli")
    for root in _candidate_roots(extra_roots):
        for folder in relative_folders:
            for executable_name in executable_names:
                candidates.append(root / folder / executable_name)

    seen: set[str] = set()
    for candidate in candidates:
        try:
            candidate = candidate.expanduser().resolve()
            key = os.path.normcase(str(candidate))
            if key in seen:
                continue
            seen.add(key)
            if candidate.is_file():
                return candidate
        except Exception:
            continue
    return None


def _short_process_error(completed: subprocess.CompletedProcess[str]) -> str:
    text = "\n".join(part.strip() for part in (completed.stdout or "", completed.stderr or "") if part.strip())
    if not text:
        text = f"vgmstream exited with code {completed.returncode}"
    text = text.replace("\r\n", "\n").strip()
    if len(text) > 1800:
        text = text[-1800:]
    return text


def decode_with_vgmstream(
    source_path: str | Path,
    output_path: str | Path,
    *,
    subsong: int = 1,
    decoder_path: str | Path | None = None,
    timeout: float = 180.0,
) -> AudioDecodeResult:
    source = Path(source_path).resolve()
    output = Path(output_path).resolve()
    decoder = find_vgmstream_cli(decoder_path)
    if decoder is None:
        return AudioDecodeResult(
            False,
            message=(
                "vgmstream-cli was not found. Put the complete vgmstream Windows bundle beside UBE, "
                "inside Tools\\vgmstream, on PATH, or choose it with Locate Decoder."
            ),
        )
    if not source.is_file():
        return AudioDecodeResult(False, decoder_path=decoder, message=f"Audio source does not exist: {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    subsong = max(1, int(subsong))

    # Current vgmstream CLI accepts options before the input file.  The second
    # form is retained for compatibility with older builds found in tool packs.
    attempts = [
        [str(decoder), "-s", str(subsong), "-o", str(output), str(source)],
        [str(decoder), str(source), "-s", str(subsong), "-o", str(output)],
    ]
    if subsong == 1:
        attempts.append([str(decoder), "-o", str(output), str(source)])

    last_error = "vgmstream did not create an output WAV"
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    for command in attempts:
        try:
            output.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            completed = subprocess.run(
                command,
                cwd=str(decoder.parent),
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
                check=False,
            )
        except subprocess.TimeoutExpired:
            last_error = f"vgmstream decoding exceeded {timeout:g} seconds"
            continue
        except OSError as exc:
            last_error = f"Could not start vgmstream: {exc}"
            continue

        if completed.returncode == 0 and output.is_file() and output.stat().st_size >= 44:
            try:
                with output.open("rb") as stream:
                    head = stream.read(12)
            except Exception:
                head = b""
            if head.startswith(b"RIFF") and head[8:12] == b"WAVE":
                return AudioDecodeResult(
                    True,
                    output_path=output,
                    decoder_path=decoder,
                    message="Decoded to temporary WAV",
                    command=tuple(command),
                )
            last_error = "vgmstream produced a file, but it was not a RIFF/WAVE file"
        else:
            last_error = _short_process_error(completed)

    try:
        output.unlink(missing_ok=True)
    except Exception:
        pass
    return AudioDecodeResult(
        False,
        decoder_path=decoder,
        message=last_error,
        command=tuple(attempts[-1]),
    )
