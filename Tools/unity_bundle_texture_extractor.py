#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
Unity Bundle Texture Batch Extractor
====================================

Batch-export Texture2D images from Unity bundle files as PNG.

This is especially useful for folders containing many tiny bundles where each
bundle holds one course logo, menu image, icon, or other single texture.

Requirements
------------
Run this script with the same Python environment used by UBE, or install:

    python -m pip install UnityPy

Examples
--------
Extract every .bundle in one folder and its subfolders:

    python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages"

Choose a custom output folder:

    python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages" ^
        --out "G:\Pico4\Extracted Course Images"

Process only the top folder:

    python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages" ^
        --no-recursive

Process one bundle:

    python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages\logo.bundle"

Overwrite existing PNG files:

    python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages" ^
        --overwrite

Also export Sprite images:

    python unity_bundle_texture_extractor.py "G:\Pico4\CourseImages" ^
        --include-sprites

Notes
-----
* Texture2D is the default because a Sprite usually references the same texture
  and would otherwise create a duplicate image.
* The real Unity asset name is used for the PNG filename.
* Streamed .resS texture data inside the bundle is resolved by UnityPy.
* One failed bundle does not stop the remainder of the batch.
* A TSV report is written after every run.
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


BUNDLE_SUFFIXES = {".bundle", ".unity3d"}
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass
class Counters:
    bundles: int = 0
    exported: int = 0
    skipped: int = 0
    empty: int = 0
    errors: int = 0


def load_unitypy():
    try:
        import UnityPy  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "\nUnityPy is required but was not found in this Python environment.\n\n"
            "Run this script with the same Python used by UBE, or install it with:\n\n"
            "    python -m pip install UnityPy\n"
        ) from exc
    return UnityPy


def clean_filename(value: object, fallback: str = "texture") -> str:
    text = str(value or "").strip().replace("\x00", "")
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(" .")

    if not text:
        text = fallback

    if text.upper() in WINDOWS_RESERVED_NAMES:
        text = "_" + text

    # Leave room for suffixes and the .png extension on Windows.
    return text[:180].rstrip(" .") or fallback


def clean_bundle_fallback(path: Path) -> str:
    stem = path.stem

    # Remove the common trailing Unity hash:
    # filename_0123456789abcdef0123456789abcdef.bundle
    stem = re.sub(r"_[0-9a-fA-F]{32}$", "", stem)

    # For path-like Addressables names, the final useful component is usually
    # after the last "_logos_", "_textures_", or "_assets_" section.
    for marker in ("_logos_", "_textures_", "_images_", "_assets_"):
        if marker in stem.lower():
            index = stem.lower().rfind(marker)
            stem = stem[index + len(marker):]

    # Remove an original source extension embedded in the bundle name.
    stem = re.sub(
        r"\.(?:png|psd|jpg|jpeg|tga|tif|tiff|bmp|exr)$",
        "",
        stem,
        flags=re.IGNORECASE,
    )
    return clean_filename(stem, fallback="texture")


def enum_text(value: object) -> str:
    if value is None:
        return ""
    name = getattr(value, "name", None)
    if name:
        return str(name)
    return str(value)


def parse_unity_object(obj: Any) -> Any:
    modern = getattr(obj, "parse_as_object", None)
    if callable(modern):
        return modern()

    legacy = getattr(obj, "read", None)
    if callable(legacy):
        return legacy()

    raise RuntimeError("The UnityPy object has no supported parse method.")


def object_name(obj: Any, data: Any, bundle: Path) -> str:
    name = getattr(data, "m_Name", None)
    if name:
        return clean_filename(name)

    peek = getattr(obj, "peek_name", None)
    if callable(peek):
        try:
            name = peek()
            if name:
                return clean_filename(name)
        except Exception:
            pass

    return clean_bundle_fallback(bundle)


def object_path_id(obj: Any) -> str:
    for attr in ("path_id", "pathID", "m_PathID"):
        value = getattr(obj, attr, None)
        if value is not None:
            return str(value)
    return ""


def collect_input_paths(values: Iterable[str]) -> list[Path]:
    paths: list[Path] = []

    for raw in values:
        expanded = os.path.expandvars(os.path.expanduser(raw))

        if any(ch in expanded for ch in "*?[]"):
            matches = glob.glob(expanded, recursive=True)
            paths.extend(Path(match) for match in matches)
        else:
            paths.append(Path(expanded))

    return paths


def collect_bundles(
    inputs: Iterable[Path],
    recursive: bool,
    all_files: bool,
) -> list[Path]:
    found: dict[str, Path] = {}

    for input_path in inputs:
        path = input_path.resolve()

        if path.is_file():
            if all_files or path.suffix.lower() in BUNDLE_SUFFIXES:
                found[str(path).casefold()] = path
            continue

        if not path.exists():
            print(f"Warning: input does not exist: {path}", file=sys.stderr)
            continue

        if not path.is_dir():
            print(f"Warning: input is not a file or folder: {path}", file=sys.stderr)
            continue

        iterator = path.rglob("*") if recursive else path.glob("*")
        for candidate in iterator:
            if not candidate.is_file():
                continue
            if all_files or candidate.suffix.lower() in BUNDLE_SUFFIXES:
                resolved = candidate.resolve()
                found[str(resolved).casefold()] = resolved

    return sorted(found.values(), key=lambda item: str(item).casefold())


def choose_folder() -> list[str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        return []

    root = tk.Tk()
    root.withdraw()
    root.update()

    selected = filedialog.askdirectory(
        title="Select folder containing Unity texture bundles"
    )
    root.destroy()

    return [selected] if selected else []


def default_output_root(inputs: list[Path]) -> Path:
    existing = [path.resolve() for path in inputs if path.exists()]
    if not existing:
        return Path.cwd() / "Extracted_Textures"

    if len(existing) == 1:
        source = existing[0]
        parent = source if source.is_dir() else source.parent
        return parent / "Extracted_Textures"

    parent_strings = [
        str(path if path.is_dir() else path.parent)
        for path in existing
    ]
    try:
        common = Path(os.path.commonpath(parent_strings))
    except ValueError:
        common = Path.cwd()

    return common / "Extracted_Textures"


def choose_unique_output(
    folder: Path,
    base_name: str,
    used_paths: set[str],
    overwrite: bool,
) -> tuple[Path, str]:
    """
    Return (path, action).

    action is:
      WRITE     create a new file
      OVERWRITE replace an existing file
      SKIP      keep an existing file from an earlier run
    """
    candidate = folder / f"{base_name}.png"
    key = str(candidate.resolve()).casefold()

    # A same-name collision within this run must never overwrite another asset.
    if key in used_paths:
        number = 2
        while True:
            candidate = folder / f"{base_name}__{number}.png"
            key = str(candidate.resolve()).casefold()
            if key not in used_paths and not candidate.exists():
                used_paths.add(key)
                return candidate, "WRITE"
            number += 1

    used_paths.add(key)

    if candidate.exists():
        return candidate, "OVERWRITE" if overwrite else "SKIP"

    return candidate, "WRITE"


def save_report(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "status",
        "bundle",
        "asset_type",
        "path_id",
        "asset_name",
        "width",
        "height",
        "texture_format",
        "output",
        "message",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
            delimiter="\t",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def extract_bundle(
    UnityPy: Any,
    bundle: Path,
    output_folder: Path,
    include_sprites: bool,
    overwrite: bool,
    dry_run: bool,
    used_paths: set[str],
    rows: list[dict[str, object]],
    counters: Counters,
) -> None:
    counters.bundles += 1
    exported_from_bundle = 0
    target_types = {"Texture2D"}
    if include_sprites:
        target_types.add("Sprite")

    try:
        env = UnityPy.load(str(bundle))
        objects = list(env.objects)
    except Exception as exc:
        counters.errors += 1
        rows.append({
            "status": "ERROR",
            "bundle": str(bundle),
            "message": f"Could not load bundle: {type(exc).__name__}: {exc}",
        })
        print(f"  ERROR loading bundle: {exc}")
        return

    targets = [
        obj for obj in objects
        if getattr(getattr(obj, "type", None), "name", "") in target_types
    ]

    if not targets:
        counters.empty += 1
        rows.append({
            "status": "NO_TEXTURE",
            "bundle": str(bundle),
            "message": "No Texture2D"
            + (" or Sprite" if include_sprites else "")
            + " object was found.",
        })
        print("  No Texture2D objects found")
        return

    for obj in targets:
        asset_type = getattr(getattr(obj, "type", None), "name", "Unknown")
        row: dict[str, object] = {
            "status": "",
            "bundle": str(bundle),
            "asset_type": asset_type,
            "path_id": object_path_id(obj),
            "asset_name": "",
            "width": "",
            "height": "",
            "texture_format": "",
            "output": "",
            "message": "",
        }

        try:
            data = parse_unity_object(obj)
            name = object_name(obj, data, bundle)
            image = data.image

            # Force decoding while the loaded Unity environment and streamed
            # resource data are still available.
            image.load()

            width = getattr(data, "m_Width", None)
            height = getattr(data, "m_Height", None)
            if not width or not height:
                width, height = image.size

            texture_format = enum_text(
                getattr(data, "m_TextureFormat", None)
            )

            output_path, action = choose_unique_output(
                output_folder,
                name,
                used_paths,
                overwrite,
            )

            row.update({
                "asset_name": name,
                "width": width,
                "height": height,
                "texture_format": texture_format,
                "output": str(output_path),
            })

            if action == "SKIP":
                row["status"] = "SKIPPED"
                row["message"] = "Output already exists; use --overwrite to replace it."
                counters.skipped += 1
                print(f"  SKIPPED {name}.png")
            else:
                if not dry_run:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image.save(output_path, format="PNG")

                row["status"] = "DRY_RUN" if dry_run else "EXPORTED"
                row["message"] = (
                    "Would overwrite existing PNG."
                    if dry_run and action == "OVERWRITE"
                    else "Would export PNG."
                    if dry_run
                    else "Existing PNG overwritten."
                    if action == "OVERWRITE"
                    else "PNG exported."
                )

                counters.exported += 1
                exported_from_bundle += 1
                verb = "WOULD EXPORT" if dry_run else "EXPORTED"
                print(f"  {verb} {name}.png  ({width} × {height})")

        except Exception as exc:
            counters.errors += 1
            row["status"] = "ERROR"
            row["message"] = f"{type(exc).__name__}: {exc}"
            print(
                f"  ERROR {asset_type} PathID {row['path_id']}: {exc}"
            )

        rows.append(row)

    if exported_from_bundle == 0 and targets:
        # The targets may all have been skipped or failed, so do not call the
        # bundle empty. This line is intentionally informational only.
        pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-export Texture2D images from Unity .bundle files as PNG."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help=(
            "Bundle file(s), folder(s), or wildcard(s). "
            "Without inputs, a folder picker is shown."
        ),
    )
    parser.add_argument(
        "-o",
        "--out",
        help=(
            "Output folder. Default: an Extracted_Textures folder beside "
            "the selected input."
        ),
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not scan subfolders.",
    )
    parser.add_argument(
        "--same-folder",
        action="store_true",
        help="Write each PNG beside its source bundle.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing same-name PNG files.",
    )
    parser.add_argument(
        "--include-sprites",
        action="store_true",
        help=(
            "Also export Sprite images. This can duplicate the Texture2D "
            "when a bundle contains one Sprite referencing one texture."
        ),
    )
    parser.add_argument(
        "--all-files",
        action="store_true",
        help=(
            "Attempt every file instead of restricting input folders to "
            ".bundle and .unity3d files."
        ),
    )
    parser.add_argument(
        "--report",
        help="Custom TSV report path.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned exports without writing PNG files.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    raw_inputs = args.inputs or choose_folder()
    if not raw_inputs:
        print("No input selected.")
        return 1

    input_paths = collect_input_paths(raw_inputs)
    bundles = collect_bundles(
        input_paths,
        recursive=not args.no_recursive,
        all_files=args.all_files,
    )

    if not bundles:
        print("No matching bundle files were found.")
        return 1

    if args.same_folder:
        base_output = default_output_root(input_paths)
    elif args.out:
        base_output = Path(
            os.path.expandvars(os.path.expanduser(args.out))
        ).resolve()
    else:
        base_output = default_output_root(input_paths).resolve()

    if args.report:
        report_path = Path(
            os.path.expandvars(os.path.expanduser(args.report))
        ).resolve()
    else:
        report_path = base_output / "unity_texture_extract_report.tsv"

    UnityPy = load_unitypy()
    counters = Counters()
    rows: list[dict[str, object]] = []
    used_paths: set[str] = set()

    print(f"Found {len(bundles)} bundle file(s)")
    if args.same_folder:
        print("Output: beside each source bundle")
    else:
        print(f"Output: {base_output}")
    if args.dry_run:
        print("Mode: dry run")

    for index, bundle in enumerate(bundles, 1):
        print(f"\n[{index}/{len(bundles)}] {bundle.name}")

        output_folder = bundle.parent if args.same_folder else base_output

        extract_bundle(
            UnityPy=UnityPy,
            bundle=bundle,
            output_folder=output_folder,
            include_sprites=args.include_sprites,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            used_paths=used_paths,
            rows=rows,
            counters=counters,
        )

    save_report(report_path, rows)

    print("\nDone")
    print(f"  Bundles processed: {counters.bundles}")
    print(f"  Images exported:   {counters.exported}")
    print(f"  Existing skipped:  {counters.skipped}")
    print(f"  No texture found:  {counters.empty}")
    print(f"  Errors:            {counters.errors}")
    print(f"  Report:            {report_path}")

    return 2 if counters.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
