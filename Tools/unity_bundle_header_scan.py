#!/usr/bin/env python3
"""
unity_bundle_header_scan.py

Fast header inspector for folders of Unity bundles / UnityFS files.

It is designed for the first-pass question:
  "What Unity version was this bundle/file built with?"

It scans files, reads only the header by default, and writes:
  unity_header_scan_YYYYMMDD_HHMMSS.tsv
  unity_header_scan_YYYYMMDD_HHMMSS.txt

Usage examples:
  python unity_bundle_header_scan.py "G:\Pico4\Explorer\AssetBundle"
  python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive
  python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --sha256
  python unity_bundle_header_scan.py "G:\Pico4\Explorer" --recursive --extensions .bundle .unity3d .obb

Notes:
  UnityFS / UnityWeb / UnityRaw headers are parsed for version/revision.
  FSB5, ZIP, OGG, WAV etc. are identified but not parsed as Unity bundles.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
from pathlib import Path
import struct
from typing import BinaryIO


DEFAULT_EXTENSIONS = {
    ".bundle",
    ".unity3d",
    ".obb",
    ".assets",
    ".resource",
    ".resS",
    ".ress",
    ".bytes",
    "",  # allow extensionless Unity files
}


def read_cstr(f: BinaryIO, max_len: int = 4096) -> str:
    data = bytearray()
    for _ in range(max_len):
        b = f.read(1)
        if not b:
            break
        if b == b"\x00":
            break
        data.extend(b)
    return data.decode("utf-8", "replace")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def classify_magic(header: bytes) -> str:
    if header.startswith(b"UnityFS"):
        return "UnityFS"
    if header.startswith(b"UnityWeb"):
        return "UnityWeb"
    if header.startswith(b"UnityRaw"):
        return "UnityRaw"
    if header.startswith(b"FSB5"):
        return "FSB5"
    if header.startswith(b"PK\x03\x04") or header.startswith(b"PK\x05\x06") or header.startswith(b"PK\x07\x08"):
        return "ZIP/PK"
    if header.startswith(b"OggS"):
        return "Ogg/Vorbis"
    if header.startswith(b"RIFF"):
        return "RIFF/WAV"
    if header.startswith(b"fLaC"):
        return "FLAC"
    return "Unknown"


def inspect_file(path: Path, do_sha256: bool = False) -> dict[str, str | int]:
    size = path.stat().st_size

    row: dict[str, str | int] = {
        "file": str(path),
        "name": path.name,
        "extension": path.suffix,
        "size_bytes": size,
        "signature": "",
        "format_version": "",
        "unity_version_string": "",
        "unity_revision": "",
        "bundle_size_header": "",
        "compressed_info_size": "",
        "uncompressed_info_size": "",
        "flags_hex": "",
        "sha256": "",
        "error": "",
    }

    try:
        with path.open("rb") as f:
            header = f.read(32)
            sig = classify_magic(header)
            row["signature"] = sig

            if sig in {"UnityFS", "UnityWeb", "UnityRaw"}:
                f.seek(0)
                signature = read_cstr(f)
                row["signature"] = signature

                raw = f.read(4)
                if len(raw) == 4:
                    row["format_version"] = struct.unpack(">I", raw)[0]

                row["unity_version_string"] = read_cstr(f)
                row["unity_revision"] = read_cstr(f)

                if signature == "UnityFS":
                    raw = f.read(8 + 4 + 4 + 4)
                    if len(raw) == 24:
                        bundle_size, comp_info, uncomp_info, flags = struct.unpack(">QIII", raw)
                        row["bundle_size_header"] = bundle_size
                        row["compressed_info_size"] = comp_info
                        row["uncompressed_info_size"] = uncomp_info
                        row["flags_hex"] = f"0x{flags:08X}"

            if do_sha256:
                row["sha256"] = sha256_file(path)

    except Exception as exc:
        row["error"] = str(exc)

    return row


def iter_files(root: Path, recursive: bool, extensions: set[str], all_files: bool):
    if root.is_file():
        yield root
        return

    pattern_iter = root.rglob("*") if recursive else root.glob("*")
    for p in pattern_iter:
        if not p.is_file():
            continue
        if all_files or p.suffix in extensions:
            yield p


def fmt_size(n: int | str) -> str:
    try:
        n = int(n)
    except Exception:
        return str(n)
    if n >= 1024 * 1024 * 1024:
        return f"{n / (1024**3):.2f} GB"
    if n >= 1024 * 1024:
        return f"{n / (1024**2):.2f} MB"
    if n >= 1024:
        return f"{n / 1024:.2f} KB"
    return f"{n} B"


def main() -> int:
    ap = argparse.ArgumentParser(description="Scan Unity bundle headers and report Unity version/revision.")
    ap.add_argument("path", help="Bundle file or folder to scan")
    ap.add_argument("-r", "--recursive", action="store_true", help="Scan subfolders")
    ap.add_argument("--all", action="store_true", help="Scan all files, ignoring extension filter")
    ap.add_argument("--sha256", action="store_true", help="Calculate SHA256 for each file; slower on big folders")
    ap.add_argument(
        "--extensions",
        nargs="*",
        default=sorted(DEFAULT_EXTENSIONS),
        help="Extensions to scan when PATH is a folder. Default includes .bundle .unity3d .obb .assets .resource .resS .bytes and extensionless.",
    )
    ap.add_argument("--out-dir", default=".", help="Output folder for TSV/TXT reports")
    args = ap.parse_args()

    root = Path(args.path)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    extensions = set()
    for e in args.extensions:
        if e == "":
            extensions.add("")
        elif e.startswith("."):
            extensions.add(e)
        else:
            extensions.add("." + e)

    files = list(iter_files(root, args.recursive, extensions, args.all))
    if not files:
        print("No files matched.")
        return 1

    print(f"Scanning {len(files)} file(s)...")

    rows = []
    for i, path in enumerate(files, 1):
        row = inspect_file(path, do_sha256=args.sha256)
        rows.append(row)

        sig = row.get("signature", "")
        ver = row.get("unity_revision") or row.get("unity_version_string") or "-"
        print(f"[{i:>4}/{len(files)}] {sig:<10} {ver:<18} {path.name}")

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    tsv_path = out_dir / f"unity_header_scan_{stamp}.tsv"
    txt_path = out_dir / f"unity_header_scan_{stamp}.txt"

    fields = [
        "file",
        "name",
        "extension",
        "size_bytes",
        "signature",
        "format_version",
        "unity_version_string",
        "unity_revision",
        "bundle_size_header",
        "compressed_info_size",
        "uncompressed_info_size",
        "flags_hex",
        "sha256",
        "error",
    ]

    with tsv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t")
        w.writeheader()
        for row in rows:
            w.writerow(row)

    unity_rows = [r for r in rows if str(r.get("signature", "")).startswith("Unity")]
    non_unity_rows = [r for r in rows if not str(r.get("signature", "")).startswith("Unity")]

    version_counts: dict[str, int] = {}
    for r in unity_rows:
        version = str(r.get("unity_revision") or r.get("unity_version_string") or "unknown")
        version_counts[version] = version_counts.get(version, 0) + 1

    with txt_path.open("w", encoding="utf-8") as f:
        f.write("Unity Bundle Header Scan\n")
        f.write("========================\n\n")
        f.write(f"Input: {root}\n")
        f.write(f"Files scanned: {len(rows)}\n")
        f.write(f"Unity-like files: {len(unity_rows)}\n")
        f.write(f"Other/unknown files: {len(non_unity_rows)}\n")
        f.write(f"SHA256: {'yes' if args.sha256 else 'no'}\n\n")

        f.write("Unity version counts:\n")
        if version_counts:
            for version, count in sorted(version_counts.items(), key=lambda kv: (-kv[1], kv[0])):
                f.write(f"  {version}: {count}\n")
        else:
            f.write("  none\n")

        f.write("\nFiles:\n")
        for r in rows:
            f.write(f"\nFile: {r.get('file')}\n")
            f.write(f"  Signature: {r.get('signature') or '-'}\n")
            f.write(f"  Format version: {r.get('format_version') or '-'}\n")
            f.write(f"  Unity version string: {r.get('unity_version_string') or '-'}\n")
            f.write(f"  Unity revision: {r.get('unity_revision') or '-'}\n")
            f.write(f"  Size: {fmt_size(r.get('size_bytes', 0))} ({r.get('size_bytes')} bytes)\n")
            if r.get("bundle_size_header"):
                f.write(f"  Bundle size in header: {fmt_size(r.get('bundle_size_header', 0))} ({r.get('bundle_size_header')} bytes)\n")
            if r.get("flags_hex"):
                f.write(f"  Flags: {r.get('flags_hex')}\n")
            if r.get("sha256"):
                f.write(f"  SHA256: {r.get('sha256')}\n")
            if r.get("error"):
                f.write(f"  Error: {r.get('error')}\n")

    print()
    print(f"Wrote TSV: {tsv_path}")
    print(f"Wrote TXT: {txt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
