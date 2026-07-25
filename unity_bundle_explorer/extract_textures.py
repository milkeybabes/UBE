from __future__ import annotations

import argparse
from pathlib import Path

from .core.bundle_reader import load_bundle
from .exporters.texture_exporter import export_texture_record


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract Texture2D assets from Unity bundles using UnityPy.")
    ap.add_argument("bundle")
    ap.add_argument("--out", default="extracted_textures")
    args = ap.parse_args()

    idx = load_bundle(args.bundle)
    if idx.error:
        print("ERROR:", idx.error)
    textures = idx.objects_by_type.get("Texture2D", [])
    print(f"Found {len(textures)} Texture2D objects")
    ok = 0
    for rec in textures:
        dst = export_texture_record(rec, args.out)
        if dst:
            ok += 1
            print("exported", dst)
    print(f"Done. Exported {ok}/{len(textures)} textures to {Path(args.out).resolve()}")


if __name__ == "__main__":
    main()
