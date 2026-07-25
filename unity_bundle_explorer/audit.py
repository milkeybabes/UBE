from __future__ import annotations

import argparse
import csv
import glob
from pathlib import Path

from .core.bundle_reader import load_bundle


def expand_inputs(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        p = Path(pat)
        if p.is_dir():
            out.extend(sorted(p.glob("*.bundle")))
        else:
            matches = [Path(x) for x in glob.glob(pat)]
            out.extend(matches if matches else [p])
    return list(dict.fromkeys(out))


def main() -> None:
    ap = argparse.ArgumentParser(description="Quick audit Unity AssetBundle files.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--csv", default="bundle_report.csv")
    args = ap.parse_args()

    rows = []
    for path in expand_inputs(args.inputs):
        idx = load_bundle(path, include_objects=True)
        rows.append({
            "path": str(path),
            "name": path.name,
            "size": path.stat().st_size if path.exists() else "",
            "sha256": idx.sha256 if path.exists() else "",
            "signature": idx.header.signature,
            "format_version": idx.header.format_version,
            "unity_version": idx.header.unity_version,
            "unity_revision": idx.header.unity_revision,
            "object_count": idx.object_count,
            "types": "; ".join(f"{k}:{len(v)}" for k, v in sorted(idx.objects_by_type.items())),
            "error": idx.error,
        })
        print(f"{path.name}: {idx.header.unity_version} objects={idx.object_count} {idx.error}")

    with open(args.csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        if rows:
            w.writeheader()
            w.writerows(rows)
    print("Wrote", args.csv)


if __name__ == "__main__":
    main()
