#!/usr/bin/env python3
"""
Unity AssetBundle quick auditor.

Scans UnityFS .bundle files and outputs useful comparison data:
- Unity engine version used to build the bundle
- bundle format/header details
- file size + SHA256
- compression flags
- contained file nodes, including .assets, .resS, .resource
- basic binary string hits related to textures/shaders/materials

Usage:
  python unity_bundle_audit.py "C:\\Game\\*.bundle" --csv report.csv
  python unity_bundle_audit.py old_folder new_folder --csv report.csv --compare

No Unity install required. Optional: lz4 package allows decoding LZ4 UnityFS directory info.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import lzma
import os
import re
import struct
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Optional

try:
    import lz4.block  # type: ignore
except Exception:  # pragma: no cover
    lz4 = None
else:
    import lz4  # type: ignore

TEXTURE_TERMS = [
    b"Texture2D", b"m_TextureFormat", b"m_CompleteImageSize", b"m_TextureSettings",
    b"m_StreamData", b"resS", b"ASTC", b"ETC", b"ETC1_EXTERNAL_ALPHA",
    b"AlphaClip", b"AlphaCutoff", b"Shader", b"Material", b"_BaseMap", b"_MainTex",
]

@dataclass
class Node:
    path: str
    offset: int
    size: int
    flags: int

@dataclass
class BundleInfo:
    path: str
    name: str
    size: int
    sha256: str
    signature: str = ""
    bundle_format: int | str = ""
    unity_version: str = ""
    unity_revision: str = ""
    total_size_header: int | str = ""
    blocks_info_compressed_size: int | str = ""
    blocks_info_uncompressed_size: int | str = ""
    flags_hex: str = ""
    compression: str = ""
    directory_at_end: bool | str = ""
    block_count: int | str = ""
    node_count: int | str = ""
    nodes_summary: str = ""
    assets_size: int | str = ""
    ress_size: int | str = ""
    resource_size: int | str = ""
    texture_string_hits: str = ""
    error: str = ""


def read_cstring(data: bytes, pos: int) -> tuple[str, int]:
    end = data.find(b"\0", pos)
    if end < 0:
        raise ValueError("unterminated string in header")
    return data[pos:end].decode("utf-8", errors="replace"), end + 1


def compression_name(flags: int) -> str:
    c = flags & 0x3F
    return {0: "none", 1: "lzma", 2: "lz4", 3: "lz4hc"}.get(c, f"unknown({c})")


def decompress(data: bytes, unpacked_size: int, flags: int) -> bytes:
    c = flags & 0x3F
    if c == 0:
        return data
    if c == 1:
        return lzma.decompress(data)
    if c in (2, 3):
        if lz4 is None:
            raise RuntimeError("LZ4 compressed directory; install lz4 with: pip install lz4")
        return lz4.block.decompress(data, uncompressed_size=unpacked_size)
    raise RuntimeError(f"unsupported UnityFS compression type {c}")


def parse_nodes(blocks_info: bytes) -> tuple[int, list[Node]]:
    # Big-endian UnityFS directory layout.
    pos = 16  # hash
    if len(blocks_info) < pos + 4:
        raise ValueError("directory info too small")
    block_count = struct.unpack_from(">i", blocks_info, pos)[0]
    pos += 4
    for _ in range(block_count):
        # uncompressed u32, compressed u32, flags u16
        pos += 4 + 4 + 2
    node_count = struct.unpack_from(">i", blocks_info, pos)[0]
    pos += 4
    nodes: list[Node] = []
    for _ in range(node_count):
        off, size, flags = struct.unpack_from(">qqI", blocks_info, pos)
        pos += 8 + 8 + 4
        path, pos = read_cstring(blocks_info, pos)
        nodes.append(Node(path=path, offset=off, size=size, flags=flags))
    return block_count, nodes


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def count_hits(path: Path, max_scan_mb: int = 256) -> str:
    # Not a real asset parser; this is just useful quick triage.
    limit = max_scan_mb * 1024 * 1024
    with path.open("rb") as f:
        data = f.read(limit)
    hits = []
    for term in TEXTURE_TERMS:
        n = data.count(term)
        if n:
            hits.append(f"{term.decode('ascii', 'ignore')}={n}")
    # Also count plausible CAB names.
    cab_count = len(re.findall(rb"CAB-[0-9a-fA-F]{32}", data))
    if cab_count:
        hits.append(f"CAB_refs={cab_count}")
    return "; ".join(hits)


def audit_bundle(path: Path) -> BundleInfo:
    info = BundleInfo(
        path=str(path),
        name=path.name,
        size=path.stat().st_size,
        sha256=sha256_file(path),
    )
    try:
        with path.open("rb") as f:
            head = f.read(4096)
            sig, pos = read_cstring(head, 0)
            info.signature = sig
            if sig != "UnityFS":
                info.error = "not UnityFS"
                info.texture_string_hits = count_hits(path)
                return info
            fmt = struct.unpack_from(">I", head, pos)[0]
            pos += 4
            unity_version, pos = read_cstring(head, pos)
            unity_revision, pos = read_cstring(head, pos)
            info.bundle_format = fmt
            info.unity_version = unity_version
            info.unity_revision = unity_revision
            if fmt < 6:
                info.error = "old bundle format not fully parsed by this script"
                info.texture_string_hits = count_hits(path)
                return info
            total_size, comp_size, uncomp_size, flags = struct.unpack_from(">QIII", head, pos)
            pos += 8 + 4 + 4 + 4
            info.total_size_header = total_size
            info.blocks_info_compressed_size = comp_size
            info.blocks_info_uncompressed_size = uncomp_size
            info.flags_hex = f"0x{flags:08X}"
            info.compression = compression_name(flags)
            info.directory_at_end = bool(flags & 0x80)

            if flags & 0x80:
                f.seek(info.size - comp_size)
            else:
                # UnityFS bundles with flag 0x200 pad the directory info to a 16-byte boundary.
                start = (pos + 15) & ~15 if (flags & 0x200) else pos
                f.seek(start)
            packed = f.read(comp_size)
            unpacked = decompress(packed, uncomp_size, flags)
            block_count, nodes = parse_nodes(unpacked)
            info.block_count = block_count
            info.node_count = len(nodes)
            info.nodes_summary = " | ".join(f"{n.path}:{n.size}" for n in nodes)
            for n in nodes:
                lower = n.path.lower()
                if lower.endswith(".assets") or "_assets" in lower:
                    info.assets_size = n.size
                if lower.endswith(".ress"):
                    info.ress_size = n.size
                if lower.endswith(".resource"):
                    info.resource_size = n.size
            info.texture_string_hits = count_hits(path)
    except Exception as e:
        info.error = type(e).__name__ + ": " + str(e)
        try:
            info.texture_string_hits = count_hits(path)
        except Exception:
            pass
    return info


def expand_inputs(items: list[str]) -> list[Path]:
    out: list[Path] = []
    for item in items:
        matches = glob.glob(item)
        if not matches and Path(item).exists():
            matches = [item]
        for m in matches:
            p = Path(m)
            if p.is_dir():
                out.extend(sorted(p.rglob("*.bundle")))
            elif p.is_file():
                out.append(p)
    # stable unique list
    seen = set()
    unique = []
    for p in out:
        rp = str(p.resolve())
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    return unique


def write_csv(rows: list[BundleInfo], csv_path: Path) -> None:
    fields = list(asdict(rows[0]).keys()) if rows else list(BundleInfo("","",0,"").__dataclass_fields__.keys())
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(asdict(row))


def print_table(rows: list[BundleInfo]) -> None:
    cols = ["name", "size", "unity_revision", "sha256", "ress_size", "resource_size", "error"]
    print("\t".join(cols))
    for r in rows:
        d = asdict(r)
        vals = []
        for c in cols:
            v = str(d.get(c, ""))
            if c == "sha256":
                v = v[:16]
            vals.append(v)
        print("\t".join(vals))


def compare_by_name(rows: list[BundleInfo]) -> None:
    groups: dict[str, list[BundleInfo]] = {}
    for r in rows:
        groups.setdefault(r.name, []).append(r)
    print("\nCOMPARE BY FILENAME")
    for name, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        print(f"\n{name}")
        base = group[0]
        for r in group:
            same_hash = "SAME" if r.sha256 == base.sha256 else "DIFF"
            print(f"  {same_hash:4} size={r.size} unity={r.unity_revision} sha={r.sha256[:16]} path={r.path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Batch audit UnityFS AssetBundle files")
    ap.add_argument("inputs", nargs="+", help="Files, folders, or wildcards, e.g. *.bundle")
    ap.add_argument("--csv", default="unity_bundle_report.csv", help="CSV output filename")
    ap.add_argument("--compare", action="store_true", help="Print comparison groups by identical filename")
    args = ap.parse_args()

    paths = expand_inputs(args.inputs)
    if not paths:
        print("No .bundle files found.", file=sys.stderr)
        return 2
    rows = [audit_bundle(p) for p in paths]
    print_table(rows)
    write_csv(rows, Path(args.csv))
    print(f"\nWrote: {args.csv}")
    if args.compare:
        compare_by_name(rows)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
