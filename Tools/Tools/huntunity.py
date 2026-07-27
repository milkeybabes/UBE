#!/usr/bin/env python3
r"""
huntunity.py

Recursively scan a folder for Android .obb and .apk archives, find UnityFS
bundles inside them, and extract those bundles into a clean destination tree.

Primary Unity player bundle:
    assets/bin/Data/data.unity3d

That primary file is renamed:
    <archive-name>.bundle

Any additional files whose first bytes are "UnityFS" are also extracted while
preserving a safe version of their internal archive path.

Usage:
    python huntunity.py SOURCE DESTINATION

Examples:
    python huntunity.py "G:\Android Games" "G:\Unity Bundles"
    python huntunity.py "G:\Android Games" "G:\Unity Bundles" --primary-only
    python huntunity.py "G:\Android Games" "G:\Unity Bundles" --overwrite
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


UNITYFS_MAGIC = b"UnityFS"
PRIMARY_PATH = "assets/bin/data/data.unity3d"
ARCHIVE_EXTENSIONS = {".obb", ".apk"}

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


@dataclass
class ArchiveResult:
    archive: Path
    extracted: int = 0
    skipped_existing: int = 0
    unityfs_found: int = 0
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively find UnityFS bundles inside Android .obb and .apk "
            "archives and extract them as .bundle files."
        )
    )
    parser.add_argument("source", type=Path, help="Folder containing .obb/.apk files")
    parser.add_argument("destination", type=Path, help="Output root folder")
    parser.add_argument(
        "--primary-only",
        action="store_true",
        help="Only extract assets/bin/Data/data.unity3d",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing extracted files",
    )
    parser.add_argument(
        "--include-non-unity-primary",
        action="store_true",
        help=(
            "Extract data.unity3d even when its header is not UnityFS. "
            "Normally only files beginning with UnityFS are extracted."
        ),
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help=(
            "Put each primary .bundle directly in DESTINATION instead of "
            "creating one folder per archive. Additional bundles still use "
            "an archive-named folder."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show archive entries that are checked or skipped",
    )
    return parser.parse_args()


def sanitize_component(text: str, fallback: str = "unnamed") -> str:
    """Return a Windows-safe filename or directory component."""
    text = text.strip().replace("\x00", "")
    text = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", text)
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(" .")

    if not text:
        text = fallback

    if text.upper() in WINDOWS_RESERVED_NAMES:
        text = f"_{text}"

    # Keep paths manageable on Windows.
    return text[:150].rstrip(" .") or fallback


def clean_archive_name(archive: Path) -> str:
    """
    Clean common Android expansion-file names.

    Examples:
        main.123.com.company.game.obb  -> com.company.game
        patch.456.com.company.game.obb -> com.company.game
        My Game.apk                    -> My Game
    """
    stem = archive.stem

    match = re.match(r"^(?:main|patch)\.\d+\.(.+)$", stem, flags=re.IGNORECASE)
    if match:
        stem = match.group(1)

    # Remove repeated archive-like suffixes occasionally found in filenames.
    stem = re.sub(r"\.(?:apk|obb)$", "", stem, flags=re.IGNORECASE)

    return sanitize_component(stem, fallback="archive")


def normalized_member_name(name: str) -> str:
    return name.replace("\\", "/").strip("/").lower()


def is_primary_member(name: str) -> bool:
    return normalized_member_name(name) == PRIMARY_PATH


def has_unityfs_header(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> bool:
    if info.is_dir() or info.file_size < len(UNITYFS_MAGIC):
        return False

    try:
        with zf.open(info, "r") as src:
            return src.read(len(UNITYFS_MAGIC)) == UNITYFS_MAGIC
    except (RuntimeError, OSError, zipfile.BadZipFile):
        return False


def safe_internal_relative_path(member_name: str) -> Path:
    """
    Convert an archive member path into a safe relative path.

    Parent traversal, drive prefixes, and empty components are discarded.
    """
    posix = PurePosixPath(member_name.replace("\\", "/"))
    safe_parts: list[str] = []

    for part in posix.parts:
        if part in {"", ".", "..", "/"}:
            continue
        if re.fullmatch(r"[A-Za-z]:", part):
            continue
        safe_parts.append(sanitize_component(part))

    if not safe_parts:
        return Path("unnamed.bundle")

    return Path(*safe_parts)


def ensure_bundle_suffix(path: Path) -> Path:
    if path.suffix.lower() == ".bundle":
        return path
    return path.with_name(path.name + ".bundle")


def unique_output_path(path: Path, reserved: set[Path]) -> Path:
    """Choose a unique output path without overwriting existing files."""
    candidate = path
    number = 2

    while candidate in reserved or candidate.exists():
        candidate = path.with_name(f"{path.stem}_{number}{path.suffix}")
        number += 1

    reserved.add(candidate)
    return candidate


def copy_zip_member_atomic(
    zf: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    destination: Path,
    overwrite: bool,
) -> bool:
    """
    Extract one member atomically.

    Returns True when written, False when skipped because it already exists.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not overwrite:
        return False

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=destination.parent,
            prefix=destination.name + ".",
            suffix=".tmp",
        ) as tmp:
            temp_path = Path(tmp.name)
            with zf.open(info, "r") as src:
                shutil.copyfileobj(src, tmp, length=1024 * 1024)

        temp_path.replace(destination)
        return True

    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def scan_archives(source: Path) -> list[Path]:
    archives = [
        path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() in ARCHIVE_EXTENSIONS
    ]
    return sorted(archives, key=lambda p: str(p).lower())


def process_archive(
    archive: Path,
    destination_root: Path,
    *,
    primary_only: bool,
    overwrite: bool,
    include_non_unity_primary: bool,
    flat: bool,
    verbose: bool,
) -> ArchiveResult:
    result = ArchiveResult(archive=archive)
    clean_name = clean_archive_name(archive)
    archive_folder = destination_root / clean_name
    primary_output = (
        destination_root / f"{clean_name}.bundle"
        if flat
        else archive_folder / f"{clean_name}.bundle"
    )

    try:
        with zipfile.ZipFile(archive, "r") as zf:
            infos = [info for info in zf.infolist() if not info.is_dir()]
            primary_infos = [info for info in infos if is_primary_member(info.filename)]

            selected: list[tuple[zipfile.ZipInfo, bool]] = []
            selected_names: set[str] = set()

            # The expected Unity player data file always gets first priority.
            for info in primary_infos:
                unityfs = has_unityfs_header(zf, info)
                if unityfs:
                    result.unityfs_found += 1

                if unityfs or include_non_unity_primary:
                    selected.append((info, True))
                    selected_names.add(info.filename)
                elif verbose:
                    print(
                        f"    Primary path found but header is not UnityFS: "
                        f"{info.filename}"
                    )

            # Also find any other genuine UnityFS bundles in the archive.
            if not primary_only:
                for info in infos:
                    if info.filename in selected_names or is_primary_member(info.filename):
                        continue

                    if has_unityfs_header(zf, info):
                        result.unityfs_found += 1
                        selected.append((info, False))
                        selected_names.add(info.filename)
                        if verbose:
                            print(f"    Extra UnityFS: {info.filename}")

            if not selected:
                return result

            reserved_outputs: set[Path] = set()
            primary_number = 0

            for info, is_primary in selected:
                if is_primary:
                    primary_number += 1
                    output = primary_output
                    if primary_number > 1:
                        output = output.with_name(
                            f"{output.stem}_{primary_number}{output.suffix}"
                        )
                else:
                    internal = safe_internal_relative_path(info.filename)
                    internal = ensure_bundle_suffix(internal)
                    output = archive_folder / "extra_bundles" / internal

                # Only add a numeric suffix when two members from this same
                # archive map to the same output name. An output left from a
                # previous run is deliberately skipped unless --overwrite is used.
                if output in reserved_outputs:
                    output = unique_output_path(output, reserved_outputs)
                else:
                    reserved_outputs.add(output)

                written = copy_zip_member_atomic(
                    zf,
                    info,
                    output,
                    overwrite=overwrite,
                )

                if written:
                    result.extracted += 1
                    print(
                        f"    EXTRACTED: {info.filename}\n"
                        f"            -> {output}"
                    )
                else:
                    result.skipped_existing += 1
                    print(f"    EXISTS:    {output}")

    except zipfile.BadZipFile:
        result.error = "Not a valid ZIP-format APK/OBB"
    except PermissionError as exc:
        result.error = f"Permission error: {exc}"
    except OSError as exc:
        result.error = f"File error: {exc}"
    except RuntimeError as exc:
        result.error = f"Archive error: {exc}"

    return result


def main() -> int:
    args = parse_args()

    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()

    if not source.exists():
        print(f"ERROR: Source folder does not exist: {source}", file=sys.stderr)
        return 2

    if not source.is_dir():
        print(f"ERROR: Source is not a folder: {source}", file=sys.stderr)
        return 2

    destination.mkdir(parents=True, exist_ok=True)

    archives = scan_archives(source)
    if not archives:
        print(f"No .obb or .apk files found beneath:\n  {source}")
        return 0

    print(f"Source:      {source}")
    print(f"Destination: {destination}")
    print(f"Archives:    {len(archives)}")
    print()

    results: list[ArchiveResult] = []

    for index, archive in enumerate(archives, start=1):
        print(f"[{index}/{len(archives)}] {archive}")
        result = process_archive(
            archive,
            destination,
            primary_only=args.primary_only,
            overwrite=args.overwrite,
            include_non_unity_primary=args.include_non_unity_primary,
            flat=args.flat,
            verbose=args.verbose,
        )
        results.append(result)

        if result.error:
            print(f"    ERROR: {result.error}")
        elif result.extracted == 0 and result.skipped_existing == 0:
            print("    No matching UnityFS bundle found.")
        print()

    total_extracted = sum(r.extracted for r in results)
    total_existing = sum(r.skipped_existing for r in results)
    total_found = sum(r.unityfs_found for r in results)
    total_errors = sum(r.error is not None for r in results)
    archives_with_bundles = sum(
        (r.extracted + r.skipped_existing) > 0 for r in results
    )

    print("=" * 68)
    print("SUMMARY")
    print(f"Archives scanned:       {len(results)}")
    print(f"Archives with bundles:  {archives_with_bundles}")
    print(f"UnityFS entries found:  {total_found}")
    print(f"Files extracted:        {total_extracted}")
    print(f"Existing files skipped: {total_existing}")
    print(f"Archive errors:         {total_errors}")

    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
